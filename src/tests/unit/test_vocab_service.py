"""Named application services and database lifecycle."""

from unittest.mock import MagicMock

import pytest

from application.vocab_service import VocabService


@pytest.fixture
def app():
    result = VocabService(
        _db=MagicMock(), language_repo=MagicMock(), word_service=MagicMock(),
        review_service=MagicMock(), settings_service=MagicMock(), export_service=MagicMock(),
        wotd_service=MagicMock(), notification_service=MagicMock(), translation_test_service=MagicMock(),
    )
    result.settings_service.get_source_lang.return_value = "en"
    result.settings_service.get_target_lang.return_value = "ru"
    result.settings_service.get_translation_provider.return_value = "google_direct"
    result.translation_test_service.test_connection.return_value = True
    return result


def test_close_calls_db_close(app):
    app.close()
    app._db.close.assert_called_once()


def test_remove_session_calls_db(app):
    app.remove_session()
    app._db.remove_session.assert_called_once()


def test_named_word_service(app):
    app.word_service.add_word.return_value = "added"
    assert app.word_service.add_word("hello") == "added"


def test_unknown_attribute_raises(app):
    with pytest.raises(AttributeError, match="has no attribute 'nonexistent_method'"):
        _ = app.nonexistent_method


def test_get_languages(app):
    app.language_repo.get_all.return_value = ["en", "ru"]
    assert app.get_languages() == ["en", "ru"]
    app.language_repo.get_all.assert_called_once()


def test_translation_api_uses_saved_settings(app):
    assert app.test_translation_api() is True
    app.translation_test_service.test_connection.assert_called_once_with("en", "ru", "google_direct")


def test_translation_api_uses_supplied_settings(app):
    assert app.test_translation_api("de", "fr", "mymemory") is True
    app.translation_test_service.test_connection.assert_called_once_with("de", "fr", "mymemory")
