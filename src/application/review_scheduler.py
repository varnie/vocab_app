"""Background reviews and Word of the Day with interruptible waits."""

import logging
import threading
import time
from collections.abc import Callable

from application.notification_service import NotificationService, format_word_body
from application.review_service import ReviewService
from application.settings_service import SettingsService
from application.wotd_service import WOTDService
from config import PAUSED_KEY
from domain.exceptions import NotificationDeliveryError

logger = logging.getLogger(__name__)

# Keep both first notifications at least five minutes after launch.
REVIEW_INITIAL_DELAY_SECONDS = 300
WOTD_INITIAL_DELAY_SECONDS = 360
WOTD_CHECK_INTERVAL_SECONDS = 3600
EMPTY_QUEUE_CHECK_SECONDS = 300
PAUSE_CHECK_SECONDS = 60
ERROR_RETRY_SECONDS = 60
MAX_CONSECUTIVE_ERRORS = 3
RECOVERY_RETRY_SECONDS = 300


class ReviewScheduler:
    """Own two workers; release their database sessions before every wait."""

    def __init__(
        self,
        review_service: ReviewService,
        wotd_service: WOTDService,
        settings_service: SettingsService,
        notify_callback: Callable[..., bool],
        label_callback: Callable[[str], None],
        notification_service: NotificationService,
        write_phrase: Callable[[str], None],
        cleanup_callback: Callable[[], None] | None = None,
        error_callback: Callable[[], None] | None = None,
    ) -> None:
        self.review_service = review_service
        self.wotd_service = wotd_service
        self.settings_service = settings_service
        self._write_phrase = write_phrase
        self._notify = notify_callback
        self._update_label = label_callback
        self._cleanup_session = cleanup_callback or (lambda: None)
        self._notification_service = notification_service
        self._error_callback = error_callback or (lambda: None)
        self.recovering = False
        self.paused = self.settings_service.get_setting(PAUSED_KEY, "false") == "true"
        self.running = False
        self._state = threading.Condition()
        self._generation = 0
        self._review_thread: threading.Thread | None = None
        self._wotd_thread: threading.Thread | None = None

    def start(self) -> None:
        with self._state:
            if self.running:
                return
            if any(worker and worker.is_alive() for worker in (self._review_thread, self._wotd_thread)):
                raise RuntimeError("Previous scheduler workers have not stopped")
            self.running = True
            self._review_thread = threading.Thread(target=self._review_loop, daemon=True)
            self._wotd_thread = threading.Thread(target=self._wotd_loop, daemon=True)
            self._review_thread.start()
            self._wotd_thread.start()

    def _request_stop(self) -> None:
        with self._state:
            self.running = False
            self._state.notify_all()

    def stop(self) -> None:
        """Wake and join workers before their shared database is closed."""
        self._request_stop()
        current = threading.current_thread()
        if current in (self._review_thread, self._wotd_thread):
            return
        for worker in (self._review_thread, self._wotd_thread):
            if worker is not None:
                worker.join()

    def settings_changed(self) -> None:
        """Wake both workers without losing changes that arrive during work."""
        with self._state:
            self._generation += 1
            self._state.notify_all()

    def _wait_until(self, deadline: float, generation: int | None = None) -> bool:
        """True on deadline; False on stop or a requested settings recheck."""
        with self._state:
            interrupted = self._state.wait_for(
                lambda: not self.running or (generation is not None and generation != self._generation),
                timeout=max(0, deadline - time.monotonic()),
            )
            return not interrupted

    def set_paused(self, paused: bool) -> None:
        self.settings_service.set_setting(PAUSED_KEY, "true" if paused else "false")
        with self._state:
            self.paused = paused
            self.settings_changed()

    def notifications_paused(self) -> bool:
        with self._state:
            paused = self.paused
        return paused or self.settings_service.is_quiet_time() is True

    def on_show_next(self):
        """Show a word on explicit user request, even during a pause."""
        return self._notification_service.show_next(self._notify)

    def _check_wotd(self) -> None:
        try:
            with self._state:
                if not self.running:
                    return
                generation = self._generation
            if self.notifications_paused():
                return
            candidate = self.wotd_service.get_word_of_the_day()
            with self._state:
                if (
                    candidate and self.running and generation == self._generation
                    and not self.notifications_paused()
                ):
                    word, level = candidate
                    if self._notify(format_word_body(word.phrase, word.translation, None), "Word of the Day"):
                        self.wotd_service.mark_shown(word, level)
                        self._write_phrase(word.phrase)
        except Exception:
            logger.exception("WOTD error")
        finally:
            self._cleanup_session()

    def _wotd_loop(self) -> None:
        if not self._wait_until(time.monotonic() + WOTD_INITIAL_DELAY_SECONDS):
            return
        while True:
            with self._state:
                if not self.running:
                    return
                generation = self._generation
            self._check_wotd()
            self._wait_until(time.monotonic() + WOTD_CHECK_INTERVAL_SECONDS, generation)

    def _review_loop(self) -> None:
        if not self._wait_until(time.monotonic() + REVIEW_INITIAL_DELAY_SECONDS):
            return
        consecutive_errors = 0
        last_shown = None
        try:
            while True:
                with self._state:
                    if not self.running:
                        return
                    generation = self._generation
                try:
                    last_shown, deadline = self._review_once(last_shown, generation)
                    consecutive_errors = 0
                    if self.recovering and not self.notifications_paused():
                        self.recovering = False
                        self._error_callback()
                except NotificationDeliveryError:
                    consecutive_errors = 0
                    logger.warning("Notification delivery failed; retrying in %s seconds", ERROR_RETRY_SECONDS,
                                   exc_info=True)
                    deadline = time.monotonic() + ERROR_RETRY_SECONDS
                except Exception:
                    consecutive_errors += 1
                    logger.exception("Review loop error (%d/%d)", consecutive_errors, MAX_CONSECUTIVE_ERRORS)
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        if not self.recovering:
                            self.recovering = True
                            self._error_callback()
                        deadline = time.monotonic() + RECOVERY_RETRY_SECONDS
                    else:
                        deadline = time.monotonic() + ERROR_RETRY_SECONDS
                finally:
                    self._cleanup_session()
                self._wait_until(deadline, generation)
        finally:
            self._request_stop()

    def _review_once(self, last_shown: float | None, generation: int) -> tuple[float | None, float]:
        """Recompute cadence from the last popup, including after settings changes."""
        if self.notifications_paused():
            return last_shown, time.monotonic() + PAUSE_CHECK_SECONDS
        interval = max(1, self.settings_service.get_review_interval())
        due_at = last_shown + interval if last_shown is not None else time.monotonic()
        if time.monotonic() < due_at:
            return last_shown, due_at
        word = self.review_service.get_next_word()
        with self._state:
            if word and self.running and generation == self._generation:
                self._notification_service.show_word(word, self._notify)
                self._update_label(str(word.phrase)[:20])
                last_shown = time.monotonic()
                return last_shown, last_shown + interval
        return last_shown, time.monotonic() + EMPTY_QUEUE_CHECK_SECONDS
