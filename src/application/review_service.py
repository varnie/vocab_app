"""Review service - handles spaced repetition review logic."""


from application.service_interfaces import AbstractReviewService, AbstractSettingsService
from domain.entities import Word
from domain.repositories import AbstractStatsRepository, AbstractWordRepository


class ReviewService(AbstractReviewService):
    """Service for review operations."""

    def __init__(
        self,
        word_repo: AbstractWordRepository,
        stats_repo: AbstractStatsRepository,
        settings_service: AbstractSettingsService,
    ) -> None:
        self.word_repo = word_repo
        self.stats_repo = stats_repo
        self.settings_service = settings_service

    def get_next_word(self) -> Word | None:
        """Get next word for review - fewest reviews first, then least recently seen."""
        target_lang = self.settings_service.get_target_lang()
        words = self.word_repo.get_for_review(limit=1, target_lang=target_lang)
        return words[0] if words else None

    def review_word(self, word_id: int) -> None:
        """Review a word - record review and update last_reviewed."""
        self.stats_repo.update_word_stats(word_id)
        self.stats_repo.record_review(word_id)

    def skip_word(self, word_id: int) -> None:
        """Skip word - record review without updating stats."""
        self.stats_repo.record_review(word_id)

    def get_stats(self) -> dict:
        """Get statistics."""
        stats = self.stats_repo.get_stats()
        return {
            "total_words": stats.total_words,
            "today_words": stats.today_words,
            "today_reviews": stats.today_reviews,
            "total_reviews": stats.total_reviews,
            "streak": stats.streak,
        }

    def get_language_counts(self) -> dict:
        """Get word count per language."""
        return self.stats_repo.get_language_counts()
