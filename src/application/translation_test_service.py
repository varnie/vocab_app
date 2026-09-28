"""Translation test service - handles translation API testing."""

from application.service_interfaces import AbstractTranslationService
from config import DEFAULT_SOURCE_LANG, DEFAULT_TARGET_LANG, DEFAULT_TRANSLATION_PROVIDER


class TranslationTestService:
    """Service for testing translation API connectivity."""

    def __init__(self, translation_service: AbstractTranslationService) -> None:
        self._translation_service = translation_service

    def test_connection(
        self,
        source_lang: str = DEFAULT_SOURCE_LANG,
        target_lang: str = DEFAULT_TARGET_LANG,
        provider_name: str = DEFAULT_TRANSLATION_PROVIDER,
    ) -> bool:
        """Test translation API with a simple query."""
        try:
            result = self._translation_service.translate(
                "hello",
                target_lang or DEFAULT_TARGET_LANG,
                source_lang or DEFAULT_SOURCE_LANG,
                provider_name,
                allow_fallback=False,
            )
            return bool(result)
        except Exception:
            return False
