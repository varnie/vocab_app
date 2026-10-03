"""Review service - handles spaced repetition review logic."""
from dataclasses import asdict

from application.settings_service import SettingsService
from domain.entities import Word
from domain.repositories import AbstractStatsRepository, AbstractWordRepository


class ReviewService:
    """Service for review operations."""

    def __init__(
        self,
        word_repo: AbstractWordRepository,
        stats_repo: AbstractStatsRepository,
        settings_service: SettingsService,
    ) -> None:
        self.word_repo = word_repo
        self.stats_repo = stats_repo
        self.settings_service = settings_service

    def get_next_word(self) -> Word | None:
        """Get the next due exposure or a new word; no response is required."""
        target_lang = self.settings_service.get_target_lang()
        words = self.word_repo.get_for_review(limit=1, target_lang=target_lang)
        return words[0] if words else None

    def review_word(self, word_id: int) -> None:
        """Review a word - record review and update last_reviewed."""
        self.stats_repo.record_review(word_id, update_stats=True)

    def next_available_at(self) -> int | None:
        return self.word_repo.next_available_at(self.settings_service.get_target_lang())

    def get_stats(self) -> dict:
        """Get statistics."""
        return asdict(self.stats_repo.get_stats())

    def get_language_counts(self) -> dict:
        """Get word count per language."""
        return self.stats_repo.get_language_counts()
