"""WOTD service - handles Word of the Day functionality."""

import logging

from application.service_interfaces import AbstractTranslationService, WordSource
from application.settings_service import SettingsService
from application.word_service import WordManagementService
from config import DEFAULT_WOTD_LEVEL, WOTD_ENABLED_KEY, WOTD_LEVEL_KEY
from domain.entities import Word
from domain.exceptions import TranslationError
from domain.repositories import AbstractWOTDRepository

logger = logging.getLogger(__name__)


class WOTDService:
    """Service for Word of the Day functionality."""

    def __init__(
        self,
        settings_service: SettingsService,
        wotd_repo: AbstractWOTDRepository,
        word_service: WordManagementService,
        translation_service: AbstractTranslationService,
        word_source: WordSource,
    ) -> None:
        self.settings_service = settings_service
        self.wotd_repo = wotd_repo
        self.word_service = word_service
        self.translation_service = translation_service
        self.word_source = word_source

    def is_wotd_enabled(self) -> bool:
        """Check if Word of the Day is enabled."""
        enabled = self.settings_service.get_setting(WOTD_ENABLED_KEY, "false")
        return enabled == "true"

    def get_wotd_level(self) -> str:
        """Get the configured WOTD level."""
        return self.settings_service.get_setting(WOTD_LEVEL_KEY, DEFAULT_WOTD_LEVEL) or DEFAULT_WOTD_LEVEL

    def get_word_of_the_day(self) -> tuple[Word, str] | None:
        """Save today's candidate; consume the day only after notification delivery."""
        if not self.is_wotd_enabled():
            return None

        if self.wotd_repo.get_today():
            return None

        level = self.get_wotd_level()
        word_data = self.word_source.get_word(level)
        if not word_data:
            return None

        word = word_data["word"]
        word_level = word_data["level"]

        provider_name = self.settings_service.get_translation_provider()
        source_lang = "en"  # The CEFR word source contains English vocabulary.
        target_lang = self.settings_service.get_target_lang()

        try:
            translation = self.translation_service.translate(
                word, target_lang, source_lang, provider_name
            )
        except TranslationError:
            logger.warning("WOTD translation failed for '%s', skipping", word)
            return None

        if not translation:
            return None

        word_entity, saved = self.save_wotd_to_vocab(
            word, translation, target_lang=target_lang, source_lang=source_lang
        )
        if not saved or word_entity is None:
            return None

        return word_entity, word_level

    def mark_shown(self, word: Word, level: str) -> None:
        self.wotd_repo.mark_shown(word.phrase, level)

    def get_today_display(self) -> tuple[str, str | None, str] | None:
        """Today's shown word as (word, translation-or-None, level), or None."""
        entry = self.wotd_repo.get_today()
        if entry is None:
            return None
        translation = None
        for candidate in self.word_service.get_words(search=entry.word):
            if candidate.phrase == entry.word:
                translation = self.word_service.get_translation(candidate.id) or None
                break
        return (entry.word, translation, entry.level)

    def save_wotd_to_vocab(
        self, word: str, translation: str | None = None,
        *, target_lang: str | None = None, source_lang: str | None = None,
    ) -> tuple[Word | None, bool]:
        """Save WOTD word to user's vocabulary."""
        try:
            result = self.word_service.add_word(
                word, translation, auto_translate=(translation is None),
                target_lang=target_lang, source_lang=source_lang,
            )
            return result, True
        except Exception as e:
            logger.exception("Failed to save WOTD to vocab: %s", e)
            return None, False
