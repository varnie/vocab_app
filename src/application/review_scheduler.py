"""ReviewScheduler - manages the background review loop, pause state, WOTD, and word popup."""

import logging
import threading
import time
from typing import Callable

from application.notification_service import format_word_body
from application.service_interfaces import (
    AbstractNotificationService,
    AbstractReviewService,
    AbstractSettingsService,
    AbstractWOTDService,
)
from config import PAUSED_UNTIL_KEY

logger = logging.getLogger(__name__)

# Staggered delays so WOTD and the first review don't fire at the same moment
# after OS boot. Both satisfy the "at least 5 minutes after launch" requirement.
REVIEW_INITIAL_DELAY_SECONDS = 300  # 5 min — first review
WOTD_INITIAL_DELAY_SECONDS = 360  # 6 min — WOTD, 1 min after review
WOTD_CHECK_INTERVAL_SECONDS = 3600  # Retry hourly; get_today prevents duplicate notifications.


class ReviewScheduler:
    """Manages the background review loop, pause state, WOTD check, and word popup logic."""

    def __init__(
        self,
        review_service: AbstractReviewService,
        wotd_service: AbstractWOTDService,
        settings_service: AbstractSettingsService,
        notify_callback: Callable[..., None],
        label_callback: Callable[[str], None],
        notification_service: AbstractNotificationService,
        write_phrase: Callable[[str], None],
        cleanup_callback: Callable[[], None] | None = None,
    ) -> None:
        self.review_service = review_service
        self.wotd_service = wotd_service
        self.settings_service = settings_service
        self._write_phrase = write_phrase
        self._notify = notify_callback
        self._update_label = label_callback
        self._cleanup_session = cleanup_callback or (lambda: None)
        self._notification_service = notification_service

        self.paused_until = 0.0
        try:
            stored_pause = self.settings_service.get_setting(PAUSED_UNTIL_KEY, "0")
            self.paused_until = float(stored_pause) if isinstance(stored_pause, str) else 0.0
        except ValueError:
            pass
        self.running = False
        self._state_lock = threading.Lock()
        self._settings_changed = threading.Event()
        self._review_thread: threading.Thread | None = None
        self._wotd_timer: threading.Timer | None = None

    def start(self) -> None:
        """Start the review thread and schedule WOTD check."""
        self.running = True
        self._review_thread = threading.Thread(target=self._review_loop, daemon=True)
        self._review_thread.start()
        self._wotd_timer = threading.Timer(WOTD_INITIAL_DELAY_SECONDS, self._check_wotd)
        self._wotd_timer.daemon = True
        self._wotd_timer.start()

    def stop(self) -> None:
        """Signal the review loop to stop."""
        with self._state_lock:
            self.running = False
        self._settings_changed.set()
        if self._wotd_timer is not None:
            self._wotd_timer.cancel()

    def pause_until(self, timestamp: float) -> None:
        with self._state_lock:
            self.paused_until = timestamp
        self.settings_service.set_setting(PAUSED_UNTIL_KEY, str(timestamp))
        self._settings_changed.set()

    def notifications_paused(self) -> bool:
        with self._state_lock:
            paused = self.paused_until > time.time()
        return paused or self.settings_service.is_quiet_time() is True

    def on_show_next(self):
        """Show next word immediately. Returns the Word or None."""
        word = self.review_service.get_next_word()
        if word:
            self._show_word_popup(word)
        return word

    def _show_word_popup(self, word) -> None:
        """Show word notification."""
        if not word:
            return

        body = self._notification_service.build_for_word(word)
        self._notify(body)

    def _check_wotd(self) -> None:
        """Check and show Word of the Day if enabled."""
        try:
            if self.notifications_paused():
                return
            word = self.wotd_service.get_word_of_the_day()
            if word:
                self._write_phrase(word.phrase)
                body = format_word_body(word.phrase, word.translation, None)
                self._notify(body, "Word of the Day")
        except Exception as e:
            logger.exception("WOTD error: %s", e)
        finally:
            self._cleanup_session()
            # The app normally remains open for days.  Keep checking so a new
            # UTC day (or an enabled setting) can produce a WOTD without a restart.
            with self._state_lock:
                should_reschedule = self.running
            if should_reschedule:
                self._wotd_timer = threading.Timer(WOTD_CHECK_INTERVAL_SECONDS, self._check_wotd)
                self._wotd_timer.daemon = True
                self._wotd_timer.start()

    def _review_loop(self) -> None:
        """Background review loop."""
        consecutive_errors = 0
        max_errors = 3
        # Don't show a phrase right after OS boot / app launch. Wait at least
        # REVIEW_INITIAL_DELAY_SECONDS before the first review popup.
        # Poll `running` so stop() can interrupt without being affected by
        # unrelated settings changes.
        deadline = time.monotonic() + REVIEW_INITIAL_DELAY_SECONDS
        while time.monotonic() < deadline:
            with self._state_lock:
                if not self.running:
                    self._cleanup_session()
                    return
            time.sleep(1)
        while True:
            with self._state_lock:
                if not self.running:
                    break
                current_paused = self.paused_until

            try:
                interval = self.settings_service.get_review_interval()

                now = time.time()
                if self.notifications_paused():
                    wait_time = max(current_paused - now, 60)
                    self._settings_changed.wait(min(wait_time, 60))
                    self._settings_changed.clear()
                    continue

                word = self.review_service.get_next_word()
                if word:
                    self._show_word_popup(word)
                    self._update_label(str(word.phrase)[:20])
                    for _ in range(interval // 60):
                        with self._state_lock:
                            if not self.running:
                                break
                        self._settings_changed.wait(60)
                        self._settings_changed.clear()
                else:
                    self._settings_changed.wait(300)
                    self._settings_changed.clear()

                consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                logger.exception(
                    "Review loop error (%d/%d): %s",
                    consecutive_errors,
                    max_errors,
                    e,
                )
                if consecutive_errors >= max_errors:
                    logger.critical("Too many review loop errors, stopping")
                    break
                self._settings_changed.wait(60)

        self._cleanup_session()
