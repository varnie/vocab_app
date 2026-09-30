"""Abstract service interfaces - application layer defines contracts."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol

from config import (
    DEFAULT_REVIEW_INTERVAL,
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    DEFAULT_TRANSLATION_PROVIDER,
    QUIET_END_KEY,
    QUIET_START_KEY,
    REVIEW_INTERVAL_KEY,
    SOURCE_LANG_KEY,
    TARGET_LANG_KEY,
    TRANSLATION_PROVIDER_KEY,
)
from domain.entities import Word, WordSnapshot

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


class SessionLifecycle(Protocol):
    """Resource lifecycle required by the application facade."""

    def close(self) -> None: ...

    def remove_session(self) -> None: ...


class WordSource(ABC):
    """Abstract source for Word of the Day words."""

    @abstractmethod
    def get_word(self, level: str) -> dict | None:
        """Get a random word for the given level.

        Returns:
            dict with 'word' and 'level' keys, or None if no word available
        """
        pass


class AbstractTranslationService(ABC):
    """Abstract interface for translation operations."""

    @abstractmethod
    def translate(
        self,
        text: str,
        target_lang: str = DEFAULT_TARGET_LANG,
        source_lang: str = DEFAULT_SOURCE_LANG,
        provider_name: str = DEFAULT_TRANSLATION_PROVIDER,
        *, allow_fallback: bool = True,
    ) -> str:
        """Translate text to target language using specified provider."""
        pass


class AbstractWordManagementService(ABC):
    """Abstract interface for word management operations."""

    @abstractmethod
    def translate_preview(self, phrase: str, target_lang: str, source_lang: str) -> str:
        """Translate a draft without saving it."""
        pass

    @abstractmethod
    def delete_word_with_undo(self, word_id: int) -> WordSnapshot:
        """Delete an entry and retain its complete domain data for undo."""
        pass

    @abstractmethod
    def restore_word(self, snapshot: WordSnapshot) -> None:
        """Restore a deleted entry without overwriting newer data."""
        pass

    @abstractmethod
    def add_word(
        self,
        phrase: str,
        translation: str | None = None,
        auto_translate: bool = False,
        force_translate: bool = False,
        *, target_lang: str | None = None, source_lang: str | None = None,
        persist: bool = True,
    ) -> Word:
        """Add a new word or add translation to existing word."""
        pass

    @abstractmethod
    def get_words(
        self,
        search: str | None = None,
        target_lang: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: str = "phrase",
        descending: bool = False,
        untranslated: bool = False,
        hidden_only: bool = False,
    ) -> list[Word]:
        """Get all words with optional search and language filter."""
        pass

    @abstractmethod
    def get_words_added_today(self) -> list[Word]:
        """Get words added today."""
        pass

    @abstractmethod
    def get_translation(self, word_id: int) -> str | None:
        """Get translation for a word."""
        pass

    @abstractmethod
    def get_translation_with_lang(self, word_id: int) -> tuple[str | None, str | None]:
        """Get translation and its language code."""
        pass

    @abstractmethod
    def get_language_abbreviation(self, lang_code: str) -> str:
        """Get language abbreviation for a code."""
        pass

    @abstractmethod
    def update_word(
        self, word_id: int, phrase: str, translation: str | None = None, target_lang: str | None = None
    ) -> None:
        """Update word phrase and optionally translation."""
        pass

    @abstractmethod
    def delete_word(self, phrase: str) -> None:
        """Delete a word."""
        pass

    @abstractmethod
    def delete_translation(self, word_id: int, target_lang: str) -> None:
        """Delete only translation for specific language, not the word."""
        pass


class AbstractExportService(ABC):
    """Abstract interface for export operations."""

    @abstractmethod
    def export_csv(self, filepath: str, target_lang: str | None = None) -> None:
        """Export words to CSV."""
        pass


class AbstractNotificationService(ABC):
    """Abstract interface for notification body building."""

    @abstractmethod
    def format_for_word(self, word: Word) -> str:
        """Build a notification body for a word (no side effects)."""
        pass

    @abstractmethod
    def build_for_word(self, word: Word) -> str:
        """Build a notification body, track the phrase and mark reviewed."""
        pass

    @abstractmethod
    def get_next_word_notification(self) -> str | None:
        """Get next word notification body."""
        pass


class AbstractReviewService(ABC):
    """Abstract interface for review operations."""

    @abstractmethod
    def get_next_word(self) -> Word | None:
        """Get next word for review with translation in current target language."""
        pass

    @abstractmethod
    def review_word(self, word_id: int) -> None:
        """Record a review and update its last-reviewed timestamp."""
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        """Get statistics."""
        pass

    @abstractmethod
    def get_language_counts(self) -> dict:
        """Get word count per language."""
        pass


class AbstractSettingsService(ABC):
    """Abstract interface for settings operations."""

    @abstractmethod
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        """Get a single setting."""
        pass

    @abstractmethod
    def set_setting(self, key: str, value: str) -> None:
        """Set a single setting."""
        pass

    @abstractmethod
    def get_settings(self) -> dict:
        """Get app settings."""
        pass

    @abstractmethod
    def save_settings(self, settings: dict) -> None:
        """Save app settings."""
        pass

    def get_source_lang(self) -> str:
        """Get configured source language code."""
        return self.get_setting(SOURCE_LANG_KEY, DEFAULT_SOURCE_LANG) or DEFAULT_SOURCE_LANG

    def get_target_lang(self) -> str:
        """Get configured target language code."""
        return self.get_setting(TARGET_LANG_KEY, DEFAULT_TARGET_LANG) or DEFAULT_TARGET_LANG

    def get_translation_provider(self) -> str:
        """Get configured translation provider name."""
        return (
            self.get_setting(TRANSLATION_PROVIDER_KEY, DEFAULT_TRANSLATION_PROVIDER)
            or DEFAULT_TRANSLATION_PROVIDER
        )

    def get_review_interval(self) -> int:
        """Get review interval in seconds (falls back to default on bad values)."""
        try:
            return int(self.get_setting(REVIEW_INTERVAL_KEY, DEFAULT_REVIEW_INTERVAL) or DEFAULT_REVIEW_INTERVAL)
        except (TypeError, ValueError):
            return int(DEFAULT_REVIEW_INTERVAL)

    def is_quiet_time(self) -> bool:
        """Local recurring quiet hours; equal or empty endpoints disable them."""
        try:
            start = datetime.strptime(self.get_setting(QUIET_START_KEY, "") or "", "%H:%M").time()
            end = datetime.strptime(self.get_setting(QUIET_END_KEY, "") or "", "%H:%M").time()
        except ValueError:
            return False
        now = datetime.now().time()
        return start <= now < end if start < end else (start != end and (now >= start or now < end))


class AbstractWOTDService(ABC):
    """Abstract interface for Word of the Day operations."""

    @abstractmethod
    def is_wotd_enabled(self) -> bool:
        """Check if Word of the Day is enabled."""
        pass

    @abstractmethod
    def get_wotd_level(self) -> str:
        """Get the configured WOTD level."""
        pass

    @abstractmethod
    def get_word_of_the_day(self) -> Word | None:
        """Get Word of the Day - adds to vocab and returns Word entity."""
        pass

    @abstractmethod
    def save_wotd_to_vocab(
        self, word: str, translation: str | None = None,
        *, target_lang: str | None = None, source_lang: str | None = None,
    ) -> tuple[Word | None, bool]:
        """Save WOTD word to user's vocabulary."""
        pass

    @abstractmethod
    def get_today_display(self) -> tuple[str, str | None, str] | None:
        """Today's shown word as (word, translation-or-None, level), or None."""
        pass
