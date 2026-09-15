"""Notification service - handles notification logic."""

from typing import Callable

from application.service_interfaces import (
    AbstractNotificationService,
    AbstractReviewService,
    AbstractWordManagementService,
)
from domain.entities import Word


def format_word_body(phrase: str, translation: str | None, abbrev: str | None) -> str:
    """Build a word notification body."""
    body = f"<b>{phrase}</b>"
    if translation:
        suffix = f" [{abbrev}]" if abbrev else ""
        body += f"\n→ {translation}{suffix}"
    return body


class NotificationService(AbstractNotificationService):
    """Service for notification operations."""

    def __init__(
        self,
        review_service: AbstractReviewService,
        word_service: AbstractWordManagementService,
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

    def build_for_word(self, word: Word) -> str:
        """Build a notification body, track the phrase and mark reviewed."""
        body = self.format_for_word(word)
        self._write_phrase(word.phrase)
        self._review.review_word(word.id)
        return body

    def get_next_word_notification(self) -> str | None:
        """Get next word notification body."""
        word = self._review.get_next_word()
        if not word:
            return None
        return self.build_for_word(word)
