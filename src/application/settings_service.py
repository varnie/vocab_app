"""Settings service - handles application settings."""

from application.service_interfaces import AbstractSettingsService
from config import (
    DEFAULT_SETTINGS,
    REVIEW_INTERVAL_KEY,
    SOURCE_LANG_KEY,
    TARGET_LANG_KEY,
    TRANSLATION_PROVIDER_KEY,
)
from domain.repositories import AbstractSettingsRepository


class SettingsService(AbstractSettingsService):
    """Service for managing application settings."""

    def __init__(self, settings_repo: AbstractSettingsRepository) -> None:
        self.settings_repo = settings_repo

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        """Get a single setting."""
        setting = self.settings_repo.get(key)
        return setting.value if setting else default

    def set_setting(self, key: str, value: str) -> None:
        """Set a single setting."""
        self.settings_repo.set(key, value)

    def get_settings(self) -> dict:
        """Return typed values using the same defaults as individual getters."""
        return {
            REVIEW_INTERVAL_KEY: self.get_review_interval(),
            SOURCE_LANG_KEY: self.get_source_lang(),
            TARGET_LANG_KEY: self.get_target_lang(),
            TRANSLATION_PROVIDER_KEY: self.get_translation_provider(),
        }

    def initialize_defaults(self) -> None:
        """Populate missing settings without replacing user preferences."""
        for key, value in DEFAULT_SETTINGS.items():
            if self.get_setting(key) is None:
                self.set_setting(key, value)

    def save_settings(self, settings: dict) -> None:
        """Save app settings."""
        for key, value in settings.items():
            self.set_setting(key, str(value))
