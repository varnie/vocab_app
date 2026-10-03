"""Application services and shared resource lifecycle."""

from dataclasses import dataclass

from application.export_service import ExportService
from application.notification_service import NotificationService
from application.review_service import ReviewService
from application.service_interfaces import AbstractTranslationService, SessionLifecycle
from application.settings_service import SettingsService
from application.word_service import WordManagementService
from application.wotd_service import WOTDService
from domain.entities import Language
from domain.repositories import AbstractLanguageRepository


@dataclass
class VocabService:
    """Expose named services and own their shared database lifecycle."""

    _db: SessionLifecycle
    language_repo: AbstractLanguageRepository
    word_service: WordManagementService
    review_service: ReviewService
    settings_service: SettingsService
    export_service: ExportService
    wotd_service: WOTDService
    notification_service: NotificationService
    _translator: AbstractTranslationService

    def close(self) -> None:
        self._db.close()

    def remove_session(self) -> None:
        self._db.remove_session()

    def get_languages(self) -> list[Language]:
        return self.language_repo.get_all()

    def test_translation_api(
        self,
        source_lang: str | None = None,
        target_lang: str | None = None,
        provider_name: str | None = None,
    ) -> bool:
        """Test either supplied settings or the currently saved settings."""
        source_lang = source_lang or self.settings_service.get_source_lang()
        target_lang = target_lang or self.settings_service.get_target_lang()
        provider_name = provider_name or self.settings_service.get_translation_provider()
        try:
            return bool(self._translator.translate(
                "hello", target_lang, source_lang, provider_name, allow_fallback=False,
            ))
        except Exception:
            return False
