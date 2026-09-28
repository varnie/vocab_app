"""Tests for config module."""

import json
from unittest.mock import mock_open, patch

from config import DEFAULT_SETTINGS
from domain.time_utils import today_start_ts
from infrastructure.config_file import read_config, write_config


class TestReadConfig:
    """Tests for read_config function."""

    def test_read_config_file_not_exists(self):
        """Test that read_config returns empty dict when file doesn't exist."""
        with patch("infrastructure.config_file.os.path.exists", return_value=False):
            result = read_config("/nonexistent/config.json")
            assert result == {}

    def test_read_config_valid_json(self):
        """Test that read_config reads valid JSON."""
        test_data = {"key": "value", "number": 123}
        with patch("infrastructure.config_file.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
                result = read_config("/tmp/config.json")
                assert result == test_data

    def test_read_config_invalid_json(self):
        """Test that read_config returns empty dict on invalid JSON."""
        with patch("infrastructure.config_file.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid json")):
                result = read_config("/tmp/config.json")
                assert result == {}

    def test_read_config_exception_handling(self):
        """Test that read_config handles exceptions gracefully."""
        with patch("infrastructure.config_file.os.path.exists", return_value=True):
            with patch("builtins.open", side_effect=PermissionError("No permission")):
                result = read_config("/tmp/config.json")
                assert result == {}


class TestWriteConfig:
    """Tests for write_config function."""

    def test_write_config_success(self, tmp_path):
        """Test that write_config writes JSON successfully."""
        test_data = {"key": "value"}
        path = tmp_path / "config.json"
        assert write_config(str(path), test_data)
        assert json.loads(path.read_text()) == test_data

    def test_write_config_creates_directory(self, tmp_path):
        """Test that write_config creates directory if needed."""
        test_data = {"key": "value"}
        path = tmp_path / "nested" / "config.json"
        assert write_config(str(path), test_data)
        assert json.loads(path.read_text()) == test_data

    def test_write_config_no_directory(self, tmp_path, monkeypatch):
        """Test write_config when config_file has no directory."""
        test_data = {"key": "value"}
        monkeypatch.chdir(tmp_path)
        assert write_config("config.json", test_data)
        assert json.loads((tmp_path / "config.json").read_text()) == test_data

    def test_write_config_exception_handling(self, tmp_path):
        """Test that write_config handles exceptions gracefully."""
        test_data = {"key": "value"}
        path = tmp_path / "config.json"
        path.write_text('{"original": true}')
        with patch("infrastructure.config_file.os.replace", side_effect=PermissionError("No permission")):
            result = write_config(str(path), test_data)
            assert result is False
        assert json.loads(path.read_text()) == {"original": True}
        assert list(tmp_path.iterdir()) == [path]


class TestDefaultSettings:
    """Tests for DEFAULT_SETTINGS."""

    def test_default_settings_exists(self):
        """Test that DEFAULT_SETTINGS is defined."""
        assert DEFAULT_SETTINGS is not None

    def test_default_settings_has_review_interval(self):
        """Test that DEFAULT_SETTINGS has review_interval."""
        assert "review_interval" in DEFAULT_SETTINGS
        assert DEFAULT_SETTINGS["review_interval"] == "3600"

    def test_default_settings_has_source_lang(self):
        """Test that DEFAULT_SETTINGS has source_lang."""
        assert "source_lang" in DEFAULT_SETTINGS
        assert DEFAULT_SETTINGS["source_lang"] == "en"

    def test_default_settings_has_target_lang(self):
        """Test that DEFAULT_SETTINGS has target_lang."""
        assert "target_lang" in DEFAULT_SETTINGS
        assert DEFAULT_SETTINGS["target_lang"] == "ru"

    def test_default_settings_has_translation_provider(self):
        """Test that DEFAULT_SETTINGS has translation_provider."""
        assert "translation_provider" in DEFAULT_SETTINGS
        assert DEFAULT_SETTINGS["translation_provider"] == "mymemory"


def test_today_start_ts_is_utc_midnight():
    """The timestamp must not shift with the machine's local timezone."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    expected = int(datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp())
    assert today_start_ts() == expected
