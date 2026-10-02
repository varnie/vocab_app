"""Abstract repository interfaces - domain layer defines contracts."""

from abc import ABC, abstractmethod

from domain.entities import (
    History,
    Language,
    Setting,
    Stats,
    Translation,
    Word,
    WordSnapshot,
    WOTDHistory,
)


class AbstractWordRepository(ABC):
    """Abstract interface for word operations."""

    def save_word(self, phrase: str, translation: str | None, target_lang: str) -> Word:
        raise NotImplementedError

    def delete_with_snapshot(self, word_id: int) -> WordSnapshot:
        raise NotImplementedError

    def restore_snapshot(self, snapshot: WordSnapshot) -> None:
        raise NotImplementedError

    def get_export_rows(self, target_lang: str | None = None) -> list[Word]:
        raise NotImplementedError

    @abstractmethod
    def add(self, phrase: str) -> Word: ...

    @abstractmethod
    def get_by_phrase(self, phrase: str) -> Word | None: ...

    @abstractmethod
    def get_all(
        self,
        search: str | None = None,
        target_lang: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        since: int | None = None,
        sort: str = "phrase",
        descending: bool = False,
        untranslated: bool = False,
        hidden_only: bool = False,
    ) -> list[Word]: ...

    @abstractmethod
    def get_for_review(self, limit: int = 20, target_lang: str | None = None) -> list[Word]:
        """Get due exposures with a limited share of unseen words."""
        pass

    @abstractmethod
    def delete(self, phrase: str) -> None: ...

    @abstractmethod
    def add_translation(self, word_id: int, translation: str, target_lang: str = "ru") -> None: ...

    @abstractmethod
    def get_translation(self, word_id: int, target_lang: str = "ru") -> Translation | None: ...

    @abstractmethod
    def update_word(
        self, word_id: int, phrase: str, translation: str | None = None, target_lang: str = "ru"
    ) -> None: ...

    def snooze_word(self, word_id: int, until: int) -> None:
        raise NotImplementedError

    def next_available_at(self, target_lang: str) -> int | None:
        raise NotImplementedError

    @abstractmethod
    def delete_translation(self, word_id: int, target_lang: str) -> None: ...


class AbstractStatsRepository(ABC):
    """Abstract interface for statistics operations."""

    @abstractmethod
    def record_review(self, word_id: int, update_stats: bool = False) -> History:
        """Record a review in history."""
        pass

    @abstractmethod
    def get_stats(self) -> Stats: ...

    @abstractmethod
    def get_language_counts(self) -> dict: ...


class AbstractSettingsRepository(ABC):
    """Abstract interface for settings operations."""

    @abstractmethod
    def get(self, key: str) -> Setting | None: ...

    @abstractmethod
    def get_all(self) -> dict[str, str]: ...

    @abstractmethod
    def set(self, key: str, value: str) -> None: ...

    @abstractmethod
    def set_many(self, values: dict[str, str]) -> None:
        """Save all values in one transaction, rolling back on failure."""
        pass


class AbstractLanguageRepository(ABC):
    """Abstract interface for language operations."""

    @abstractmethod
    def get_by_code(self, code: str) -> Language | None: ...

    @abstractmethod
    def get_all(self) -> list[Language]: ...

    @abstractmethod
    def init_defaults(self) -> None: ...


class AbstractWOTDRepository(ABC):
    """Abstract interface for Word of the Day operations."""

    @abstractmethod
    def mark_shown(self, word: str, level: str) -> None: ...

    @abstractmethod
    def get_today(self) -> WOTDHistory | None: ...
