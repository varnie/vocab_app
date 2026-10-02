"""Abstract service interfaces - application layer defines contracts."""

from abc import ABC, abstractmethod
from typing import Protocol

from config import (
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    DEFAULT_TRANSLATION_PROVIDER,
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
    ) -> str: ...


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
    def restore_translation(self, word_id: int, translation: str, target_lang: str) -> None:
        """Restore a deleted translation without overwriting newer data."""
        pass

    @abstractmethod
    def snooze_word(self, word_id: int, until: int) -> None:
        """Hide a word from the review queue until the given timestamp."""
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
    ) -> Word: ...

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
    ) -> list[Word]: ...

    @abstractmethod
    def get_words_added_today(self) -> list[Word]: ...

    @abstractmethod
    def get_translation(self, word_id: int) -> str | None: ...

    @abstractmethod
    def get_translation_with_lang(self, word_id: int) -> tuple[str | None, str | None]: ...

    @abstractmethod
    def get_language_abbreviation(self, lang_code: str) -> str: ...

    @abstractmethod
    def update_word(
        self, word_id: int, phrase: str, translation: str | None = None, target_lang: str | None = None
    ) -> None: ...

    @abstractmethod
    def delete_word(self, phrase: str) -> None: ...

    @abstractmethod
    def delete_translation(self, word_id: int, target_lang: str) -> None: ...


class AbstractExportService(ABC):
    """Abstract interface for export operations."""

    @abstractmethod
    def export_csv(self, filepath: str, target_lang: str | None = None) -> None: ...


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
    def get_next_word_notification(self) -> str | None: ...


class AbstractReviewService(ABC):
    """Abstract interface for review operations."""

    @abstractmethod
    def get_next_word(self) -> Word | None:
        """Get next word for review with translation in current target language."""
        pass

    @abstractmethod
    def next_available_at(self) -> int | None:
        """Return earliest word eligibility in the configured language."""
        pass

    @abstractmethod
    def review_word(self, word_id: int) -> None:
        """Record a review and update its last-reviewed timestamp."""
        pass

    @abstractmethod
    def get_stats(self) -> dict: ...

    @abstractmethod
    def get_language_counts(self) -> dict: ...


class AbstractSettingsService(ABC):
    """Abstract interface for settings operations."""

    @abstractmethod
    def get_setting(self, key: str, default: str | None = None) -> str | None: ...

    @abstractmethod
    def set_setting(self, key: str, value: str) -> None: ...

    @abstractmethod
    def get_settings(self) -> dict: ...

    @abstractmethod
    def save_settings(self, settings: dict) -> None: ...

    @abstractmethod
    def get_source_lang(self) -> str: ...

    @abstractmethod
    def get_target_lang(self) -> str: ...

    @abstractmethod
    def get_translation_provider(self) -> str: ...

    @abstractmethod
    def get_review_interval(self) -> int:
        """Get review interval in seconds (falls back to default on bad values)."""
        pass

    @abstractmethod
    def is_quiet_time(self) -> bool:
        """Local recurring quiet hours; equal or empty endpoints disable them."""
        pass


class AbstractWOTDService(ABC):
    """Abstract interface for Word of the Day operations."""

    @abstractmethod
    def is_wotd_enabled(self) -> bool: ...

    @abstractmethod
    def get_wotd_level(self) -> str: ...

    @abstractmethod
    def get_word_of_the_day(self) -> Word | None:
        """Get Word of the Day - adds to vocab and returns Word entity."""
        pass

    @abstractmethod
    def save_wotd_to_vocab(
        self, word: str, translation: str | None = None,
        *, target_lang: str | None = None, source_lang: str | None = None,
    ) -> tuple[Word | None, bool]: ...

    @abstractmethod
    def get_today_display(self) -> tuple[str, str | None, str] | None:
        """Today's shown word as (word, translation-or-None, level), or None."""
        pass
