"""Notification orchestration works with injected state storage."""

from unittest.mock import MagicMock

from application.notification_service import NotificationService
from domain.entities import Word


def test_notification_records_phrase_and_review_once():
    review = MagicMock()
    words = MagicMock()
    words.get_translation_with_lang.return_value = ("hola", "es")
    words.get_language_abbreviation.return_value = "ES"
    write_phrase = MagicMock()
    service = NotificationService(review, words, write_phrase)

    assert service.build_for_word(Word(id=7, phrase="hello")) == "<b>hello</b>\n→ hola [ES]"
    write_phrase.assert_called_once_with("hello")
    review.review_word.assert_called_once_with(7)
