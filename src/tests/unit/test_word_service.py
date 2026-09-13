"""Unit tests for WordManagementService."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text


class TestWordManagementService:
    """Tests for WordManagementService."""

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

    def test_delete_word_by_id(self, word_service):
        """Test deleting word by ID."""
        word = word_service.add_word("byid", translation="по id")
        word_service.delete_word_by_id(word.id)

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

        now = datetime.now(timezone.utc)
        today_start = int(datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp())
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
