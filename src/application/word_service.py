"""Word management service - handles word CRUD operations."""

import logging

from application.service_interfaces import (
    AbstractSettingsService,
    AbstractTranslationService,
    AbstractWordManagementService,
)
from domain.entities import Word
from domain.exceptions import TranslationError
from domain.repositories import AbstractLanguageRepository, AbstractWordRepository
from domain.time_utils import today_start_ts

logger = logging.getLogger(__name__)


class WordManagementService(AbstractWordManagementService):
    """Service for word CRUD operations."""

    MIN_PHRASE_LENGTH = 1
    MAX_PHRASE_LENGTH = 200

    def __init__(
        self,
        word_repo: AbstractWordRepository,
        language_repo: AbstractLanguageRepository,
        settings_service: AbstractSettingsService,
        translation_service: AbstractTranslationService,
    ) -> None:
        self.word_repo = word_repo
        self.language_repo = language_repo
        self.settings_service = settings_service
        self.translation_service = translation_service

    def _get_target_lang(self) -> str:
        return self.settings_service.get_target_lang()

    def _get_source_lang(self) -> str:
        return self.settings_service.get_source_lang()

    def _normalize_phrase(self, phrase: str) -> str:
        """Strip, lowercase and validate a phrase."""
        if not phrase or not phrase.strip():
            raise ValueError("Phrase cannot be empty")

        phrase = phrase.strip().lower()

        if len(phrase) < self.MIN_PHRASE_LENGTH or len(phrase) > self.MAX_PHRASE_LENGTH:
            raise ValueError(
                f"Phrase length must be {self.MIN_PHRASE_LENGTH}-{self.MAX_PHRASE_LENGTH}"
            )
        return phrase

    def _get_or_create_id(self, phrase: str) -> int:
        """Return the id of an existing word or create it."""
        existing = self.word_repo.get_by_phrase(phrase)
        if existing:
            return existing.id
        return self.word_repo.add(phrase).id

    def add_word(
        self, phrase: str, translation: str | None = None, auto_translate: bool = False
    ) -> Word:
        """Add a new word or add translation to existing word."""
        phrase = self._normalize_phrase(phrase)

        if translation or auto_translate:
            target_lang = self._get_target_lang()
            if translation:
                trans = translation
            else:  # auto_translate
                provider_name = self.settings_service.get_translation_provider()
                source_lang = self._get_source_lang()
                try:
                    trans = self.translation_service.translate(
                        phrase, target_lang, source_lang, provider_name
                    )
                except TranslationError as e:
                    logger.warning("Auto-translate failed for '%s': %s", phrase, e)
                    raise TranslationError(
                        f"Could not translate '{phrase}'. Word was not added. "
                        "Add it with a manual translation or try again later."
                    ) from e
                if not trans:
                    raise TranslationError(
                        f"Auto-translate returned no result for '{phrase}'. "
                        "Word was not added."
                    )

            # We have a translation, so it is safe to persist the word.
            word_id = self._get_or_create_id(phrase)
            self.word_repo.add_translation(word_id, trans, target_lang)
        else:
            # No translation requested: just store the word as-is.
            self._get_or_create_id(phrase)

        result = self.word_repo.get_by_phrase(phrase)
        if result is None:
            msg = f"Word not found after add: {phrase}"
            raise RuntimeError(msg)
        target_lang = self._get_target_lang()
        selected_translation = self.word_repo.get_translation(result.id, target_lang)
        result.translation = selected_translation.translation if selected_translation else ""
        result.language_code = target_lang if selected_translation else ""
        return result

    def get_words(
        self,
        search: str | None = None,
        target_lang: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Word]:
        """Get all words with optional search and language filter."""
        return self.word_repo.get_all(search, target_lang, limit, offset)

    def get_words_added_today(self) -> list[Word]:
        """Get words added today."""
        target_lang = self._get_target_lang()
        return self.word_repo.get_all(target_lang=target_lang, since=today_start_ts())

    def get_translation(self, word_id: int) -> str | None:
        """Get translation for a word."""
        target_lang = self._get_target_lang()
        translation = self.word_repo.get_translation(word_id, target_lang)
        return translation.translation if translation else None

    def get_translation_with_lang(self, word_id: int) -> tuple[str | None, str | None]:
        """Get translation and its language code."""
        target_lang = self._get_target_lang()
        translation = self.word_repo.get_translation(word_id, target_lang)
        return (translation.translation if translation else None), target_lang

    def get_language_abbreviation(self, lang_code: str) -> str:
        """Get language abbreviation for a code."""
        lang = self.language_repo.get_by_code(lang_code)
        return lang.abbreviation if lang else lang_code.upper()

    def update_word(self, word_id: int, phrase: str, translation: str | None = None) -> None:
        """Update word phrase and optionally translation."""
        phrase = self._normalize_phrase(phrase)

        self.word_repo.update_word(word_id, phrase)
        if translation:
            target_lang = self._get_target_lang()
            self.word_repo.add_translation(word_id, translation, target_lang)

    def delete_word(self, phrase: str) -> None:
        """Delete a word."""
        self.word_repo.delete(phrase)

    def delete_word_by_id(self, word_id: int) -> None:
        """Delete a word by ID."""
        self.word_repo.delete_by_id(word_id)

    def delete_translation(self, word_id: int, target_lang: str) -> None:
        """Delete only translation for specific language, not the word."""
        self.word_repo.delete_translation(word_id, target_lang)
