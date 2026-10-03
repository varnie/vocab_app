"""Contracts for external adapters used by application services."""

from abc import ABC, abstractmethod
from typing import Protocol

from config import DEFAULT_SOURCE_LANG, DEFAULT_TARGET_LANG, DEFAULT_TRANSLATION_PROVIDER

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


class SessionLifecycle(Protocol):
    def close(self) -> None: ...

    def remove_session(self) -> None: ...


class WordSource(ABC):
    @abstractmethod
    def get_word(self, level: str) -> dict | None:
        """Return an English word with 'word' and 'level' keys, or None."""
        ...


class AbstractTranslationService(ABC):
    @abstractmethod
    def translate(
        self,
        text: str,
        target_lang: str = DEFAULT_TARGET_LANG,
        source_lang: str = DEFAULT_SOURCE_LANG,
        provider_name: str = DEFAULT_TRANSLATION_PROVIDER,
        *, allow_fallback: bool = True,
    ) -> str: ...
