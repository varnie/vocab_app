"""Notification delivery controls exposure history and current-phrase state."""

from unittest.mock import Mock

import pytest

from application.notification_service import NotificationService
from domain.exceptions import NotificationDeliveryError


@pytest.mark.parametrize("outcome", [True, False, OSError("notification command failed")])
def test_notification_records_only_successful_delivery(word_service, review_service, outcome):
    word = word_service.add_word("hello", "hola", target_lang="es")
    word_service.settings_service.set_setting("target_lang", "es")
    write_phrase = Mock()
    service = NotificationService(review_service, word_service, write_phrase)

    def send(body):
        assert body == "<b>hello</b>\n→ hola [ES]"
        assert review_service.get_stats()["total_reviews"] == 0
        write_phrase.assert_not_called()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    if outcome is True:
        assert service.show_next(send).id == word.id
        assert review_service.get_stats()["total_reviews"] == 1
        assert review_service.get_next_word() is None
        write_phrase.assert_called_once_with("hello")
        assert service.show_next(send) is None
    else:
        with pytest.raises(NotificationDeliveryError, match="notification") as raised:
            service.show_next(send)
        if isinstance(outcome, Exception):
            assert raised.value.__cause__ is outcome
        assert review_service.get_stats()["total_reviews"] == 0
        assert review_service.get_next_word().id == word.id
        write_phrase.assert_not_called()


def test_review_failure_is_not_misclassified_as_delivery_failure(word_service, review_service, monkeypatch):
    word_service.add_word("hello", "привет")
    write_phrase = Mock()
    service = NotificationService(review_service, word_service, write_phrase)
    error = RuntimeError("database unavailable")
    monkeypatch.setattr(review_service, "review_word", Mock(side_effect=error))
    send = Mock(return_value=True)

    with pytest.raises(RuntimeError) as raised:
        service.show_next(send)

    assert raised.value is error
    assert not isinstance(raised.value, NotificationDeliveryError)
    send.assert_called_once()
    write_phrase.assert_not_called()
