"""Unit tests for SettingsService."""


class TestSettingsService:
    """Tests for SettingsService."""

    def test_get_setting_default(self, settings_service):
        """Test getting setting with default value."""
        value = settings_service.get_setting("nonexistent", "default_value")
        assert value == "default_value"

    def test_set_setting(self, settings_service):
        """Test setting a value."""
        settings_service.set_setting("test_key", "test_value")

        value = settings_service.get_setting("test_key")
        assert value == "test_value"

    def test_get_settings_returns_dict(self, settings_service):
        """Test getting all settings."""
        settings = settings_service.get_settings()

        assert isinstance(settings, dict)
        assert "source_lang" in settings
        assert "target_lang" in settings

    def test_save_settings(self, settings_service):
        """Test saving multiple settings."""
        settings = {
            "source_lang": "en",
            "target_lang": "de",
            "review_interval": "3600",
        }
        settings_service.save_settings(settings)

        assert settings_service.get_setting("source_lang") == "en"
        assert settings_service.get_setting("target_lang") == "de"

    def test_get_setting_returns_none_for_missing(self, settings_service):
        """Test that missing setting returns None."""
        value = settings_service.get_setting("missing_key")
        assert value is None

    def test_typed_getters_return_defaults(self, settings_service):
        """Typed getters fall back to config defaults when unset."""
        assert settings_service.get_source_lang() == "en"
        assert settings_service.get_target_lang() == "ru"
        assert settings_service.get_translation_provider() == "mymemory"
        assert settings_service.get_review_interval() == 3600

    def test_typed_getters_return_stored_values(self, settings_service):
        """Typed getters reflect stored settings."""
        settings_service.set_setting("source_lang", "de")
        settings_service.set_setting("target_lang", "fr")
        settings_service.set_setting("translation_provider", "google_deep")
        settings_service.set_setting("review_interval", "7200")

        assert settings_service.get_source_lang() == "de"
        assert settings_service.get_target_lang() == "fr"
        assert settings_service.get_translation_provider() == "google_deep"
        assert settings_service.get_review_interval() == 7200

    def test_get_review_interval_falls_back_on_garbage(self, settings_service):
        """Invalid stored review interval falls back to default instead of raising."""
        settings_service.set_setting("review_interval", "not-a-number")
        assert settings_service.get_review_interval() == 3600

    def test_bulk_settings_use_same_invalid_value_fallback(self, settings_service):
        settings_service.set_setting("review_interval", "invalid")
        assert settings_service.get_settings()["review_interval"] == settings_service.get_review_interval()

    def test_returned_settings_cannot_mutate_service_state(self, settings_service):
        snapshot = settings_service.get_settings()
        snapshot["target_lang"] = "es"
        assert settings_service.get_settings()["target_lang"] == "ru"

    def test_initialize_defaults_preserves_preferences(self, settings_service):
        settings_service.set_setting("target_lang", "es")
        settings_service.initialize_defaults()
        assert settings_service.get_target_lang() == "es"
        assert settings_service.get_setting("review_interval") == "3600"
