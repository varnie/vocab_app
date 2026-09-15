"""Service factory - creates services with proper dependency injection."""

from dataclasses import dataclass
from functools import cached_property
from typing import Callable

from application.export_service import ExportService
from application.notification_service import NotificationService
from application.review_service import ReviewService
from application.service_interfaces import (
    AbstractReviewService,
    AbstractTranslationService,
    AbstractWordManagementService,
    WordSource,
)
from application.settings_service import SettingsService
from application.translation_test_service import TranslationTestService
from application.word_service import WordManagementService
from application.wotd_service import WOTDService
from domain.entities import Word
from domain.repositories import (
    AbstractLanguageRepository,
    AbstractSettingsRepository,
    AbstractStatsRepository,
    AbstractWordRepository,
    AbstractWOTDRepository,
)


@dataclass
class ServiceFactory:
    """Factory for creating services with proper DI."""

    word_repo: AbstractWordRepository
    stats_repo: AbstractStatsRepository
    settings_repo: AbstractSettingsRepository
    language_repo: AbstractLanguageRepository
    wotd_repo: AbstractWOTDRepository
    translation_service: AbstractTranslationService

    word_source: WordSource
    write_phrase: Callable[[str], None]
    write_csv: Callable[[str, list[Word], str], None]

    @cached_property
    def settings_service(self) -> SettingsService:
        return SettingsService(self.settings_repo)

    def create_word_service(self) -> WordManagementService:
        """Create word management service."""
        return WordManagementService(
            word_repo=self.word_repo,
            language_repo=self.language_repo,
            settings_service=self.settings_service,
            translation_service=self.translation_service,
        )

    def create_review_service(self) -> ReviewService:
        """Create review service."""
        return ReviewService(
            word_repo=self.word_repo,
            stats_repo=self.stats_repo,
            settings_service=self.settings_service,
        )

    def create_wotd_service(self, word_service: AbstractWordManagementService) -> WOTDService:
        """Create WOTD service."""
        return WOTDService(
            settings_service=self.settings_service,
            wotd_repo=self.wotd_repo,
            word_service=word_service,
            translation_service=self.translation_service,
            word_source=self.word_source,
        )

    def create_export_service(self) -> ExportService:
        """Create export service."""
        return ExportService(self.word_repo, self.settings_service, self.write_csv)

    def create_notification_service(
        self,
        review_service: AbstractReviewService,
        word_service: AbstractWordManagementService,
    ) -> NotificationService:
        """Create notification service."""
        return NotificationService(
            review_service=review_service,
            write_phrase=self.write_phrase,
            word_service=word_service,
        )

    def create_translation_test_service(self) -> TranslationTestService:
        """Create translation test service."""
        return TranslationTestService(self.translation_service)
