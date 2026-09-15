"""Regression tests for the background review loop."""

from unittest.mock import MagicMock, patch

from application.review_scheduler import ReviewScheduler


def test_pause_wait_blocks_again_after_consuming_wakeup():
    scheduler = ReviewScheduler(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
    )
    scheduler.running = True
    scheduler.on_pause()
    wakeups = []
    real_wait = scheduler._settings_changed.wait

    def wait(timeout):
        # Probe the real event without waiting a minute in the test.
        wakeups.append(real_wait(0))
        if len(wakeups) == 3:
            scheduler.stop()

    with (
        patch("application.review_scheduler.REVIEW_INITIAL_DELAY_SECONDS", 0),
        patch.object(scheduler._settings_changed, "wait", side_effect=wait),
    ):
        scheduler._review_loop()

    assert wakeups == [True, False, False]
    scheduler.review_service.get_next_word.assert_not_called()
