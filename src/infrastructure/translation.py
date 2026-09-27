"""Translation providers."""

import json
import logging
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from application.service_interfaces import AbstractTranslationService
from config import DEFAULT_SOURCE_LANG, DEFAULT_TARGET_LANG, DEFAULT_TRANSLATION_PROVIDER
from domain.exceptions import TranslationError

logger = logging.getLogger(__name__)
TRANSLATION_TIMEOUT_SECONDS = 15


def _bounded_translation(provider: str, text: str, source: str, target: str) -> str:
    """Kill and reap an unresponsive library call; never leave orphan workers."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("translation_worker.py"))],
        input=json.dumps([provider, text, source, target]),
        capture_output=True, text=True, timeout=TRANSLATION_TIMEOUT_SECONDS, check=False,
    )
    if result.returncode:
        raise TranslationError(f"{provider} could not translate this phrase")
    return json.loads(result.stdout)


class TranslationProvider(ABC):
    """Abstract base class for translation providers.

    Subclasses implement only the backend call (_do_translate); result
    normalization and error mapping live here (Template Method).
    """

    def translate(
        self,
        text: str,
        target_lang: str = DEFAULT_TARGET_LANG,
        source_lang: str = DEFAULT_SOURCE_LANG,
    ) -> str:
        """Translate text to target language."""
        try:
            result = self._do_translate(text, target_lang, source_lang)
        except Exception as e:
            logger.warning("%s translation failed: %s", self.get_name(), e)
            raise TranslationError(f"{self.get_name()} translation failed: {e}") from e
        if isinstance(result, list):
            result = result[0] if result else ""
        return result.strip() if result else ""

    @abstractmethod
    def _do_translate(self, text: str, target_lang: str, source_lang: str):
        """Perform the backend call; return raw text, list or empty."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return provider display name."""
        pass


class GoogleDirectProvider(TranslationProvider):
    """Google Translate provider using direct HTTP requests."""

    def _do_translate(self, text: str, target_lang: str, source_lang: str):
        """Translate text using Google Translate."""
        return _bounded_translation("google_direct", text, source_lang, target_lang)

    def get_name(self) -> str:
        return "Google Translate (direct)"


class GoogleDeepTranslatorProvider(TranslationProvider):
    """Google Translate provider using deep-translator library."""

    def _do_translate(self, text: str, target_lang: str, source_lang: str):
        """Translate text using Google Translate via deep-translator."""
        return _bounded_translation("google_deep", text, source_lang, target_lang)

    def get_name(self) -> str:
        return "Google Translate (deep-translator)"


class MyMemoryProvider(TranslationProvider):
    """MyMemory Translation API (free, rate-limited)."""

    LANG_MAP: ClassVar[dict[str, str]] = {
        "ru": "ru-RU",
        "en": "en-US",
        "de": "de-DE",
        "fr": "fr-FR",
        "es": "es-ES",
        "it": "it-IT",
        "pt": "pt-PT",
        "uk": "uk-UA",
    }

    def _do_translate(self, text: str, target_lang: str, source_lang: str):
        """Translate text using MyMemory API."""
        src_lang = self.LANG_MAP.get(source_lang, f"{source_lang}-{source_lang.upper()}")
        tgt_lang = self.LANG_MAP.get(target_lang, f"{target_lang}-{target_lang.upper()}")

        return _bounded_translation("mymemory", text, src_lang, tgt_lang)

    def get_name(self) -> str:
        return "MyMemory (free)"


class ProviderRegistry:
    """Registry of translation providers."""

    _providers: ClassVar[dict[str, type[TranslationProvider]]] = {
        "google_direct": GoogleDirectProvider,
        "google_deep": GoogleDeepTranslatorProvider,
        "mymemory": MyMemoryProvider,
    }

    @classmethod
    def get(cls, provider_name: str) -> TranslationProvider:
        """Get provider by name.

        Raises:
            ValueError: If the provider name is unknown.
        """
        provider_class = cls._providers.get(provider_name)
        if provider_class is None:
            raise ValueError(
                f"Unknown translation provider: {provider_name!r}. "
                f"Available: {sorted(cls._providers)}"
            )
        return provider_class()

    @classmethod
    def list_providers(cls) -> list[tuple[str, str]]:
        """List available providers."""
        return [(name, cls.get(name).get_name()) for name in cls._providers]


class TranslationServiceImpl(AbstractTranslationService):
    """Implementation of TranslationService using provider registry."""

    # Fallback order tried when the selected provider fails (429, blocked, etc.).
    # NOTE: "easygoogle" is intentionally excluded — its underlying library
    # touches a local error.txt file on failure and is unreliable.
    FALLBACK_ORDER: ClassVar[tuple[str, ...]] = ("google_deep", DEFAULT_TRANSLATION_PROVIDER)

    def translate(
        self,
        text: str,
        target_lang: str = DEFAULT_TARGET_LANG,
        source_lang: str = DEFAULT_SOURCE_LANG,
        provider_name: str = DEFAULT_TRANSLATION_PROVIDER,
    ) -> str:
        """Translate text using the specified provider.

        If the selected provider fails, other available providers are tried
        in fallback order so translation keeps working even when one backend
        is blocked (e.g. Google returning HTTP 429).
        """
        providers_to_try = [provider_name] + [p for p in self.FALLBACK_ORDER if p != provider_name]

        last_error: Exception | None = None
        for name in providers_to_try:
            try:
                provider = ProviderRegistry.get(name)
                result = provider.translate(text, target_lang, source_lang)
                if result:
                    return result
            except Exception as e:
                logger.warning("Translation via '%s' failed: %s", name, e)
                last_error = e

        if last_error is not None:
            raise TranslationError(f"All translation providers failed: {last_error}") from last_error
        raise TranslationError("All translation providers returned empty results")
