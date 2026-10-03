"""Named application services and database lifecycle."""

from unittest.mock import MagicMock

import pytest

from application.vocab_service import VocabService


@pytest.fixture
def app():
    result = VocabService(
        _db=MagicMock(), language_repo=MagicMock(), word_service=MagicMock(),
        review_service=MagicMock(), settings_service=MagicMock(), export_service=MagicMock(),
        wotd_service=MagicMock(), notification_service=MagicMock(), _translator=MagicMock(),
    )
    result.settings_service.get_source_lang.return_value = "en"
    result.settings_service.get_target_lang.return_value = "ru"
    result.settings_service.get_translation_provider.return_value = "google_direct"
    result._translator.translate.return_value = "translation"
    return result


def test_close_calls_db_close(app):
    app.close()
    app._db.close.assert_called_once()


def test_remove_session_calls_db(app):
    app.remove_session()
    app._db.remove_session.assert_called_once()


def test_get_languages(app):
    app.language_repo.get_all.return_value = ["en", "ru"]
    assert app.get_languages() == ["en", "ru"]
    app.language_repo.get_all.assert_called_once()


def test_translation_api_uses_saved_settings(app):
    assert app.test_translation_api() is True
    app._translator.translate.assert_called_once_with("hello", "ru", "en", "google_direct", allow_fallback=False)


def test_translation_api_uses_supplied_settings(app):
    assert app.test_translation_api("de", "fr", "mymemory") is True
    app._translator.translate.assert_called_once_with("hello", "fr", "de", "mymemory", allow_fallback=False)
