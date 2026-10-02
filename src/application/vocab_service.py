"""Application services and shared resource lifecycle."""

from dataclasses import dataclass

from application.service_interfaces import (
    AbstractExportService,
    AbstractNotificationService,
    AbstractReviewService,
    AbstractSettingsService,
    AbstractWordManagementService,
    AbstractWOTDService,
    SessionLifecycle,
)
from application.translation_test_service import TranslationTestService
from domain.entities import Language
from domain.repositories import AbstractLanguageRepository


@dataclass
class VocabService:
    """Expose named services and own their shared database lifecycle."""

    _db: SessionLifecycle
    language_repo: AbstractLanguageRepository
    word_service: AbstractWordManagementService
    review_service: AbstractReviewService
    settings_service: AbstractSettingsService
    export_service: AbstractExportService
    wotd_service: AbstractWOTDService
    notification_service: AbstractNotificationService
    translation_test_service: TranslationTestService

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
        return self.translation_test_service.test_connection(
            source_lang, target_lang, provider_name
        )
