"""Translation providers with bounded workers and ordered fallback."""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

from application.service_interfaces import AbstractTranslationService
from config import DEFAULT_SOURCE_LANG, DEFAULT_TARGET_LANG, DEFAULT_TRANSLATION_PROVIDER
from domain.exceptions import TranslationError

logger = logging.getLogger(__name__)
TRANSLATION_TIMEOUT_SECONDS = 15
PROVIDERS = {
    "google_direct": "Google Translate (direct)",
    "google_deep": "Google Translate (deep-translator)",
    "mymemory": "MyMemory (free)",
}


def _mymemory_language(code: str) -> str:
    return {
        "en": "en-US", "uk": "uk-UA",
    }.get(code, f"{code}-{code.upper()}")


def _bounded_translation(provider: str, text: str, source: str, target: str) -> str:
    """Kill and reap an unresponsive library call; never leave orphan workers."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown translation provider: {provider!r}")
    if provider == "mymemory":
        source, target = _mymemory_language(source), _mymemory_language(target)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("translation_worker.py"))],
        input=json.dumps([provider, text, source, target]),
        capture_output=True, text=True, timeout=TRANSLATION_TIMEOUT_SECONDS, check=False,
    )
    if result.returncode:
        raise TranslationError(f"{provider} could not translate this phrase")
    value = json.loads(result.stdout)
    if isinstance(value, list):
        value = value[0] if value else ""
    return value.strip() if value else ""


class TranslationServiceImpl(AbstractTranslationService):
    FALLBACK_ORDER: ClassVar[tuple[str, ...]] = ("google_deep", DEFAULT_TRANSLATION_PROVIDER)

    def translate(
        self,
        text: str,
        target_lang: str = DEFAULT_TARGET_LANG,
        source_lang: str = DEFAULT_SOURCE_LANG,
        provider_name: str = DEFAULT_TRANSLATION_PROVIDER,
        *, allow_fallback: bool = True,
    ) -> str:
        providers_to_try = [provider_name]
        if allow_fallback:
            providers_to_try += [p for p in self.FALLBACK_ORDER if p != provider_name]

        last_error: Exception | None = None
        for name in providers_to_try:
            try:
                result = _bounded_translation(name, text, source_lang, target_lang)
                if result:
                    return result
            except Exception as error:
                logger.warning("Translation via '%s' failed: %s", name, error)
                last_error = error

        if last_error is not None:
            raise TranslationError(f"All translation providers failed: {last_error}") from last_error
        raise TranslationError("All translation providers returned empty results")
