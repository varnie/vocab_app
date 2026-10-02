"""Settings service - handles application settings."""

from datetime import datetime, time

from application.service_interfaces import AbstractSettingsService
from config import (
    DEFAULT_REVIEW_INTERVAL,
    DEFAULT_SETTINGS,
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    DEFAULT_TRANSLATION_PROVIDER,
    QUIET_END_KEY,
    QUIET_START_KEY,
    REVIEW_INTERVAL_KEY,
    SOURCE_LANG_KEY,
    TARGET_LANG_KEY,
    TRANSLATION_PROVIDER_KEY,
)
from domain.repositories import AbstractSettingsRepository


def parse_quiet_hours(start: str, end: str) -> tuple[time, time] | None:
    """Parse local quiet hours; both empty endpoints disable them."""
    if not start and not end:
        return None
    return datetime.strptime(start, "%H:%M").time(), datetime.strptime(end, "%H:%M").time()


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
        missing = {key: value for key, value in DEFAULT_SETTINGS.items() if self.get_setting(key) is None}
        self.settings_repo.set_many(missing)

    def save_settings(self, settings: dict) -> None:
        """Save app settings."""
        self.settings_repo.set_many({key: str(value) for key, value in settings.items()})

    def get_source_lang(self) -> str:
        return self.get_setting(SOURCE_LANG_KEY, DEFAULT_SOURCE_LANG) or DEFAULT_SOURCE_LANG

    def get_target_lang(self) -> str:
        return self.get_setting(TARGET_LANG_KEY, DEFAULT_TARGET_LANG) or DEFAULT_TARGET_LANG

    def get_translation_provider(self) -> str:
        return (
            self.get_setting(TRANSLATION_PROVIDER_KEY, DEFAULT_TRANSLATION_PROVIDER)
            or DEFAULT_TRANSLATION_PROVIDER
        )

    def get_review_interval(self) -> int:
        """Return seconds, falling back to the default for invalid values."""
        try:
            return int(self.get_setting(REVIEW_INTERVAL_KEY, DEFAULT_REVIEW_INTERVAL) or DEFAULT_REVIEW_INTERVAL)
        except (TypeError, ValueError):
            return int(DEFAULT_REVIEW_INTERVAL)

    def is_quiet_time(self) -> bool:
        """Local recurring quiet hours; equal or empty endpoints disable them."""
        try:
            hours = parse_quiet_hours(
                self.get_setting(QUIET_START_KEY, "") or "",
                self.get_setting(QUIET_END_KEY, "") or "",
            )
        except ValueError:
            return False
        if hours is None:
            return False
        start, end = hours
        now = datetime.now().time()
        if start < end:
            return start <= now < end
        return start != end and (now >= start or now < end)
