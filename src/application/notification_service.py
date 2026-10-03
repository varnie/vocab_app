"""Notification service - handles notification logic."""

from collections.abc import Callable

from application.review_service import ReviewService
from application.word_service import WordManagementService
from domain.entities import Word
from domain.exceptions import NotificationDeliveryError


def format_word_body(phrase: str, translation: str | None, abbrev: str | None) -> str:
    """Build a word notification body."""
    body = f"<b>{phrase}</b>"
    if translation:
        suffix = f" [{abbrev}]" if abbrev else ""
        body += f"\n→ {translation}{suffix}"
    return body


class NotificationService:
    """Service for notification operations."""

    def __init__(
        self,
        review_service: ReviewService,
        word_service: WordManagementService,
        write_phrase: Callable[[str], None],
    ):
        self._review = review_service
        self._word = word_service
        self._write_phrase = write_phrase

    def format_for_word(self, word: Word) -> str:
        """Build a notification body for a word (no side effects)."""
        translation, trans_lang = self._word.get_translation_with_lang(word.id)
        abbrev = self._word.get_language_abbreviation(trans_lang) if trans_lang else "—"
        return format_word_body(word.phrase, translation, abbrev)

    def show_word(self, word: Word, send: Callable[[str], bool]) -> None:
        """Record an exposure only after the OS accepts the notification."""
        body = self.format_for_word(word)
        try:
            delivered = send(body)
        except Exception as error:
            raise NotificationDeliveryError("Could not send word notification") from error
        if not delivered:
            raise NotificationDeliveryError("Could not send word notification")
        self._review.review_word(word.id)
        self._write_phrase(word.phrase)

    def show_next(self, send: Callable[[str], bool]) -> Word | None:
        """Select and show the next eligible word, or return None for an empty queue."""
        word = self._review.get_next_word()
        if word:
            self.show_word(word, send)
        return word
