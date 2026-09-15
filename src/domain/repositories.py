"""Abstract repository interfaces - domain layer defines contracts."""

from abc import ABC, abstractmethod

from domain.entities import (
    History,
    Language,
    Setting,
    Stats,
    Translation,
    Word,
    WordStats,
    WOTDHistory,
)


class AbstractWordRepository(ABC):
    """Abstract interface for word operations."""

    @abstractmethod
    def add(self, phrase: str) -> Word:
        """Add a word, return domain entity."""
        pass

    @abstractmethod
    def get_by_phrase(self, phrase: str) -> Word | None:
        """Get word by phrase."""
        pass

    @abstractmethod
    def get_all(
        self,
        search: str | None = None,
        target_lang: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        since: int | None = None,
    ) -> list[Word]:
        """Get all words with stats."""
        pass

    @abstractmethod
    def get_for_review(self, limit: int = 20, target_lang: str | None = None) -> list[Word]:
        """Get next words ordered by fewest reviews, then least recently seen."""
        pass

    @abstractmethod
    def delete(self, phrase: str) -> None:
        """Delete a word."""
        pass

    @abstractmethod
    def add_translation(self, word_id: int, translation: str, target_lang: str = "ru") -> None:
        """Add translation for a word."""
        pass

    @abstractmethod
    def get_translation(self, word_id: int, target_lang: str = "ru") -> Translation | None:
        """Get translation for a word."""
        pass

    @abstractmethod
    def update_word(self, word_id: int, phrase: str) -> None:
        """Update word phrase."""
        pass

    @abstractmethod
    def delete_by_id(self, word_id: int) -> None:
        """Delete a word by ID."""
        pass

    @abstractmethod
    def delete_translation(self, word_id: int, target_lang: str) -> None:
        """Delete translation for a specific language."""
        pass


class AbstractStatsRepository(ABC):
    """Abstract interface for statistics operations."""

    @abstractmethod
    def update_word_stats(
        self, word_id: int
    ) -> None:
        """Update word stats (set last_reviewed to now)."""
        pass

    @abstractmethod
    def get_word_stats(self, word_id: int) -> WordStats | None:
        """Get stats for a word."""
        pass

    @abstractmethod
    def record_review(self, word_id: int) -> History:
        """Record a review in history."""
        pass

    @abstractmethod
    def get_stats(self) -> Stats:
        """Get overall statistics."""
        pass

    @abstractmethod
    def get_language_counts(self) -> dict:
        """Get word count per language."""
        pass


class AbstractSettingsRepository(ABC):
    """Abstract interface for settings operations."""

    @abstractmethod
    def get(self, key: str) -> Setting | None:
        """Get a setting value, or None if not stored."""
        pass

    @abstractmethod
    def get_all(self) -> dict[str, str]:
        """Get all settings as a flat dict."""
        pass

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Set a setting value."""
        pass


class AbstractLanguageRepository(ABC):
    """Abstract interface for language operations."""

    @abstractmethod
    def get_by_code(self, code: str) -> Language | None:
        """Get language by code."""
        pass

    @abstractmethod
    def get_all(self) -> list[Language]:
        """Get all languages."""
        pass

    @abstractmethod
    def init_defaults(self) -> None:
        """Initialize languages table with default data."""
        pass


class AbstractWOTDRepository(ABC):
    """Abstract interface for Word of the Day operations."""

    @abstractmethod
    def mark_shown(self, word: str, level: str) -> None:
        """Record a word as shown for today."""
        pass

    @abstractmethod
    def get_today(self) -> WOTDHistory | None:
        """Get today's WOTD if shown, or None."""
        pass
