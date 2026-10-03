"""Cadence, wakeups, session cleanup, and concurrent scheduler shutdown."""

import threading
import time
from unittest.mock import MagicMock

import pytest

from application.notification_service import NotificationService
from application.review_scheduler import ReviewScheduler
from domain.entities import Word


@pytest.fixture
def scheduler():
    settings = MagicMock()
    settings.get_setting.return_value = "0"
    settings.get_review_interval.return_value = 75
    settings.is_quiet_time.return_value = False
    review = MagicMock()
    review.get_next_word.return_value = Word(phrase="Hello", translation="bonjour")
    wotd = MagicMock()
    wotd.get_word_of_the_day.return_value = None
    words = MagicMock()
    words.get_translation_with_lang.return_value = ("bonjour", "fr")
    notification = NotificationService(review, words, MagicMock())
    return ReviewScheduler(
        review, wotd, settings, MagicMock(return_value=True), MagicMock(), notification, MagicMock(), MagicMock(),
    )


def test_settings_change_before_wait_is_not_lost(scheduler):
    scheduler.running = True
    generation = scheduler._generation
    scheduler.settings_changed()
    assert not scheduler._wait_until(time.monotonic() + 300, generation)
    scheduler.stop()


def test_startup_delay_ignores_settings_wakeups(scheduler):
    scheduler.running = True
    scheduler.settings_changed()
    before = time.monotonic()
    assert scheduler._wait_until(before + 0.02)
    assert time.monotonic() >= before + 0.02
    scheduler.stop()


def test_start_is_idempotent_and_stop_interrupts_startup(scheduler):
    scheduler.start()
    workers = scheduler._review_thread, scheduler._wotd_thread
    scheduler.start()
    assert workers == (scheduler._review_thread, scheduler._wotd_thread)
    before = time.monotonic()
    scheduler.stop()
    assert time.monotonic() - before < 1
    assert all(not worker.is_alive() for worker in workers)
    assert not scheduler.running
    scheduler.review_service.get_next_word.assert_not_called()
    scheduler.wotd_service.get_word_of_the_day.assert_not_called()
    scheduler.start()
    scheduler.stop()
    assert not scheduler._review_thread.is_alive()
    assert not scheduler._wotd_thread.is_alive()


def test_cadence_uses_seconds_and_recomputes_from_last_show(scheduler, monkeypatch):
    monkeypatch.setattr("application.review_scheduler.REVIEW_INITIAL_DELAY_SECONDS", 0)
    now = [100.0]
    monkeypatch.setattr("application.review_scheduler.time.monotonic", lambda: now[0])
    waits = []
    scheduler.running = True

    def wait(deadline, generation=None):
        if generation is None:
            return True
        # The session must already be released before sleeping.
        assert scheduler._cleanup_session.call_count == len(waits) + 1
        waits.append(deadline)
        if len(waits) == 1:
            now[0] = 110
            scheduler.settings_service.get_review_interval.return_value = 30
            scheduler.settings_changed()
        elif len(waits) == 2:
            now[0] = deadline
        else:
            scheduler.stop()
        return False

    monkeypatch.setattr(scheduler, "_wait_until", wait)
    scheduler._review_loop()
    assert waits == [175, 130, 160]
    assert scheduler._notify.call_count == 2
    assert scheduler.review_service.get_next_word.call_count == 2


@pytest.mark.parametrize("paused", [False, True])
def test_empty_or_paused_queue_releases_session_every_iteration(scheduler, monkeypatch, paused):
    monkeypatch.setattr("application.review_scheduler.REVIEW_INITIAL_DELAY_SECONDS", 0)
    scheduler.running = True
    scheduler.review_service.get_next_word.return_value = None
    scheduler.settings_service.is_quiet_time.return_value = paused
    waits = []

    def wait(deadline, generation=None):
        if generation is None:
            return True
        assert scheduler._cleanup_session.call_count == len(waits) + 1
        waits.append(deadline)
        if len(waits) == 3:
            scheduler.stop()
        return False

    monkeypatch.setattr(scheduler, "_wait_until", wait)
    scheduler._review_loop()
    assert scheduler._cleanup_session.call_count == 3
    if paused:
        scheduler.review_service.get_next_word.assert_not_called()
    scheduler._notify.assert_not_called()


def test_three_errors_stop_workers_and_release_failed_sessions(scheduler, monkeypatch):
    monkeypatch.setattr("application.review_scheduler.REVIEW_INITIAL_DELAY_SECONDS", 0)
    scheduler.running = True
    scheduler.review_service.get_next_word.side_effect = RuntimeError("database failure")
    monkeypatch.setattr(scheduler, "_wait_until", lambda *_: True)
    scheduler._review_loop()
    assert scheduler.review_service.get_next_word.call_count == 3
    assert scheduler._cleanup_session.call_count == 3
    assert not scheduler.running


@pytest.mark.parametrize("failure", [False, OSError("notification service unavailable")])
def test_delivery_recovers_after_more_than_three_failures(
    scheduler, monkeypatch, word_service, review_service, failure,
):
    word = word_service.add_word("hello", "привет")
    write_phrase = MagicMock()
    scheduler.review_service = review_service
    scheduler._notification_service = NotificationService(review_service, word_service, write_phrase)
    scheduler._notify.side_effect = [failure] * 4 + [True]
    scheduler.running = True
    monkeypatch.setattr("application.review_scheduler.REVIEW_INITIAL_DELAY_SECONDS", 0)
    monkeypatch.setattr("application.review_scheduler.time.monotonic", lambda: 100.0)
    waits = []

    def wait(deadline, generation=None):
        if generation is None:
            return True
        assert scheduler.running
        assert scheduler._cleanup_session.call_count == len(waits) + 1
        waits.append(deadline)
        if len(waits) <= 4:
            assert deadline == 160.0
            assert review_service.get_stats()["total_reviews"] == 0
            assert review_service.get_next_word().id == word.id
            write_phrase.assert_not_called()
            scheduler._update_label.assert_not_called()
        else:
            assert deadline == 175.0
            scheduler.stop()
        return True

    monkeypatch.setattr(scheduler, "_wait_until", wait)
    scheduler._review_loop()
    assert len(waits) == 5
    assert review_service.get_stats()["total_reviews"] == 1
    assert review_service.get_next_word() is None
    write_phrase.assert_called_once_with("hello")
    scheduler._update_label.assert_called_once_with("hello")


def test_change_during_selection_discards_stale_word(scheduler):
    scheduler.running = True
    generation = scheduler._generation

    def select():
        scheduler.settings_changed()
        return Word(phrase="stale language")

    scheduler.review_service.get_next_word.side_effect = select
    scheduler._review_once(None, generation)
    scheduler._notification_service._write_phrase.assert_not_called()
    scheduler._notify.assert_not_called()
    scheduler.stop()


def test_manual_show_still_works_during_pause(scheduler):
    scheduler.set_paused(True)
    assert scheduler.on_show_next().phrase == "Hello"
    scheduler._notify.assert_called_once()


def test_failed_pause_save_does_not_change_scheduler(scheduler):
    scheduler.settings_service.set_setting.side_effect = RuntimeError("cannot save")
    with pytest.raises(RuntimeError, match="cannot save"):
        scheduler.set_paused(True)
    assert not scheduler.paused
    assert scheduler._generation == 0


def test_stop_waits_for_inflight_wotd_and_discards_late_notification(scheduler, monkeypatch):
    monkeypatch.setattr("application.review_scheduler.WOTD_INITIAL_DELAY_SECONDS", 0)
    entered, release, stopped = threading.Event(), threading.Event(), threading.Event()

    def get_word():
        entered.set()
        assert release.wait(2)
        return Word(phrase="late word", translation="late translation"), "A1"

    def stop():
        scheduler.stop()
        stopped.set()

    scheduler.wotd_service.get_word_of_the_day.side_effect = get_word
    scheduler.start()
    stopper = threading.Thread(target=stop)
    try:
        assert entered.wait(1)
        stopper.start()
        assert not stopped.wait(0.02)
    finally:
        release.set()
        if stopper.ident is not None:
            stopper.join(2)
        scheduler.stop()
    assert stopped.is_set()
    assert not scheduler._review_thread.is_alive()
    assert not scheduler._wotd_thread.is_alive()
    scheduler._notify.assert_not_called()
    scheduler._write_phrase.assert_not_called()
    scheduler.wotd_service.mark_shown.assert_not_called()
    scheduler._cleanup_session.assert_called_once()


@pytest.mark.parametrize("outcome", [True, False, OSError("delivery failed")])
def test_wotd_consumes_day_only_after_delivery(scheduler, outcome):
    scheduler.running = True
    word = Word(phrase="hello", translation="bonjour")
    scheduler.wotd_service.get_word_of_the_day.return_value = (word, "A1")
    if isinstance(outcome, Exception):
        scheduler._notify.side_effect = outcome
    else:
        scheduler._notify.return_value = outcome
    scheduler._check_wotd()
    if outcome is True:
        scheduler.wotd_service.mark_shown.assert_called_once_with(word, "A1")
        scheduler._write_phrase.assert_called_once_with("hello")
    else:
        scheduler.wotd_service.mark_shown.assert_not_called()
        scheduler._write_phrase.assert_not_called()
    scheduler._cleanup_session.assert_called_once()


def test_settings_change_wakes_wotd_without_waiting_an_hour(scheduler, monkeypatch):
    monkeypatch.setattr("application.review_scheduler.WOTD_INITIAL_DELAY_SECONDS", 0)
    checked, repeated = threading.Event(), threading.Event()
    calls = []

    def get_word():
        calls.append(True)
        (checked if len(calls) == 1 else repeated).set()
        return None

    scheduler.wotd_service.get_word_of_the_day.side_effect = get_word
    scheduler.start()
    try:
        assert checked.wait(1)
        scheduler.settings_changed()
        assert repeated.wait(1)
    finally:
        scheduler.stop()
    assert len(calls) == 2
    assert scheduler._cleanup_session.call_count == 2
