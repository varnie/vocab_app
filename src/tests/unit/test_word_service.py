"""Unit tests for WordManagementService."""

import pytest
from sqlalchemy import text

from domain.time_utils import local_today_start_ts


@pytest.mark.parametrize("translation,auto_translate,expected", [
    (None, False, ""),
    (None, True, "тест"),
    ("manual", False, "manual"),
    ("manual", True, "manual"),
])
def test_prepare_word_does_not_persist(word_service, word_repo, translation, auto_translate, expected):
    word = word_service.add_word(
        "  Hello  ", translation, auto_translate=auto_translate,
        target_lang="fr", source_lang="en", persist=False,
    )
    assert word.phrase == "Hello"
    assert word.translation == expected
    assert word.language_code == "fr"
    assert word_repo.get_by_phrase("Hello") is None
    if translation is None and auto_translate:
        word_service.translation_service.translate.assert_called_once_with("Hello", "fr", "en", "mymemory")
    else:
        word_service.translation_service.translate.assert_not_called()


@pytest.mark.parametrize("force_translate", [False, True])
def test_prepare_existing_word_preserves_cached_translation(word_service, word_repo, force_translate):
    original = word_service.add_word("Hello", "cached", target_lang="fr")
    word = word_service.add_word(
        "hello", auto_translate=True, force_translate=force_translate, target_lang="fr", persist=False,
    )
    assert word.translation == ("тест" if force_translate else "cached")
    assert word.language_code == "fr"
    if not force_translate:
        assert word.id == original.id
        assert word.phrase == "Hello"
        word_service.translation_service.translate.assert_not_called()
    assert word_repo.get_translation(original.id, "fr").translation == "cached"


@pytest.mark.parametrize("translation", [None, ""])
def test_empty_auto_translation_does_not_change_existing_word(word_service, word_repo, translation):
    from domain.exceptions import TranslationError

    original = word_service.add_word("Hello", "cached")
    word_service.translation_service.translate.return_value = translation
    with pytest.raises(TranslationError, match="returned no result"):
        word_service.add_word("hello", auto_translate=True, force_translate=True)
    assert word_repo.get_by_phrase("Hello").phrase == "Hello"
    assert word_repo.get_translation(original.id, "ru").translation == "cached"


class TestWordManagementService:
    """Tests for WordManagementService."""

    def test_translation_preview_uses_settings_without_saving(self, word_service, word_repo):
        word_service.settings_service.set_setting("translation_provider", "google_direct")
        result = word_service.translate_preview("  Hello  ", "fr", "en")
        assert result == "тест"
        word_service.translation_service.translate.assert_called_once_with(
            "Hello", "fr", "en", "google_direct"
        )
        assert word_repo.get_by_phrase("Hello") is None

    def test_translation_preview_rejects_empty_draft(self, word_service):
        with pytest.raises(ValueError, match="Phrase cannot be empty"):
            word_service.translate_preview("  ", "fr", "en")
        word_service.translation_service.translate.assert_not_called()

    def test_add_word_success(self, word_service):
        """Test adding a new word successfully."""
        word = word_service.add_word("hello", translation="привет")
        assert word.phrase == "hello"
        assert word.translation == "привет"

    def test_add_word_duplicate_adds_translation(self, word_service):
        """Test adding duplicate word adds translation."""
        word_service.add_word("hello", translation="привет")

        # Add another translation to existing word
        word = word_service.add_word("hello", translation="хай")
        assert word.phrase == "hello"
        assert word.translation == "хай"

    def test_add_word_empty_raises_value_error(self, word_service):
        """Test that empty phrase raises ValueError."""
        with pytest.raises(ValueError, match="Phrase cannot be empty"):
            word_service.add_word("")

    def test_add_word_whitespace_raises(self, word_service):
        """Test that whitespace-only phrase raises ValueError."""
        with pytest.raises(ValueError, match="Phrase cannot be empty"):
            word_service.add_word("   ")

    def test_add_word_auto_translate(self, word_service):
        """Test auto-translate using mock service."""
        word = word_service.add_word("hello", auto_translate=True)
        assert word.phrase == "hello"

    def test_add_word_auto_translate_failure_raises_and_does_not_persist(
        self, word_service, word_repo
    ):
        """If auto-translate fails, the word must NOT be added (no silent save)."""

        from domain.exceptions import TranslationError

        word_service.translation_service.translate.side_effect = TranslationError("boom")

        with pytest.raises(TranslationError):
            word_service.add_word("hello", auto_translate=True)

        assert word_repo.get_by_phrase("hello") is None

    def test_get_words_returns_all(self, word_service):
        """Test getting all words."""
        word_service.add_word("word1", translation="слово1")
        word_service.add_word("word2", translation="слово2")

        words = word_service.get_words()
        assert len(words) >= 2

    def test_get_words_with_search(self, word_service):
        """Test getting words with search filter."""
        word_service.add_word("apple", translation="яблоко")
        word_service.add_word("banana", translation="банан")

        words = word_service.get_words(search="apple")
        assert len(words) >= 1
        assert words[0].phrase == "apple"

    def test_delete_word(self, word_service):
        """Test deleting a word."""
        word_service.add_word("todelete", translation="удалить")
        word_service.delete_word("todelete")

        words = word_service.get_words(search="todelete")
        assert len(words) == 0

    def test_delete_word_with_undo(self, word_service):
        """Test deleting a word through the browser use case."""
        word = word_service.add_word("byid", translation="по id")
        word_service.delete_word_with_undo(word.id)

        words = word_service.get_words(search="byid")
        assert len(words) == 0

    def test_update_word(self, word_service):
        """Test updating word."""
        word = word_service.add_word("old", translation="старый")
        word_service.update_word(word.id, "new", translation="новый")

        updated = word_service.get_words(search="new")
        assert len(updated) == 1
        assert updated[0].translation == "новый"

    def test_get_translation(self, word_service):
        """Test getting translation."""
        word = word_service.add_word("test", translation="тест")
        translation = word_service.get_translation(word.id)
        assert translation == "тест"

    def test_get_words_added_today(self, word_service, test_db):
        """Test getting words added today."""
        word_service.add_word("today_word", translation="сегодня")
        word_service.add_word("yesterday_word", translation="вчера")

        today_start = local_today_start_ts()
        yesterday_start = today_start - 86400

        test_db.session.execute(
            text("UPDATE words SET created_at = :ts WHERE phrase = 'today_word'"),
            {"ts": today_start},
        )
        test_db.session.execute(
            text("UPDATE words SET created_at = :ts WHERE phrase = 'yesterday_word'"),
            {"ts": yesterday_start},
        )
        test_db.commit()

        words = word_service.get_words_added_today()
        phrases = [w.phrase for w in words]
        assert "today_word" in phrases
        assert "yesterday_word" not in phrases

    def test_get_language_abbreviation(self, word_service):
        """Test getting language abbreviation."""
        abbrev = word_service.get_language_abbreviation("ru")
        assert abbrev == "RU"

    def test_add_word_returns_selected_language(self, word_service, settings_service):
        settings_service.set_setting("target_lang", "ru")
        word_service.add_word("hello", "privet")
        settings_service.set_setting("target_lang", "es")

        word = word_service.add_word("hello", "hola")

        assert word.translation == "hola"
        assert word.language_code == "es"
        settings_service.set_setting("target_lang", "ru")
        assert word_service.get_translation(word.id) == "privet"

    def test_add_without_translation_does_not_return_another_language(self, word_service, settings_service):
        settings_service.set_setting("target_lang", "ru")
        word_service.add_word("hello", "privet")
        settings_service.set_setting("target_lang", "es")

        word = word_service.add_word("hello")

        assert word.translation == ""
        assert word.language_code == ""
