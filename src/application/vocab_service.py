"""Vocabulary service - thin facade with auto-delegation."""

from typing import Any

from application.factory import ServiceFactory
from application.service_interfaces import SessionLifecycle
from domain.entities import Language


class VocabService:
    """Vocabulary service - thin facade with auto-delegation.

    Uses ServiceFactory to create services.
    Most methods auto-delegate to appropriate service via __getattr__.
    """

    def __init__(
        self,
        db: SessionLifecycle,
        factory: ServiceFactory,
    ) -> None:
        self._db = db

        self.language_repo = factory.language_repo

        self.word_service = factory.create_word_service()
        self.review_service = factory.create_review_service()
        self.settings_service = factory.settings_service
        self.export_service = factory.create_export_service()
        self.wotd_service = factory.create_wotd_service(self.word_service)
        self.notification_service = factory.create_notification_service(
            review_service=self.review_service,
            word_service=self.word_service,
        )
        self.translation_test_service = factory.create_translation_test_service()

    def __getattr__(self, name: str) -> Any:
        """Auto-delegate to services."""
        for svc in [
            self.word_service,
            self.review_service,
            self.settings_service,
            self.wotd_service,
            self.notification_service,
            self.export_service,
            self.translation_test_service,
        ]:
            if hasattr(svc, name):
                return getattr(svc, name)
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

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
