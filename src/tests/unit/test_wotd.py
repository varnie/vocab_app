"""Tests for wotd (Word of the Day) module."""

from unittest.mock import MagicMock, mock_open, patch

from application.service_interfaces import CEFR_LEVELS
from application.wotd_service import WOTDService
from domain.entities import Word, WOTDHistory
from infrastructure.word_source import LocalWordSource


class TestWOTDService:
    """WOTD persistence order tests."""

    def test_marks_wotd_only_after_saving_the_word(self):
        from application.wotd_service import WOTDService

        settings = MagicMock()
        settings.get_setting.return_value = "true"
        settings.get_wotd_level.return_value = "A1"
        settings.get_translation_provider.return_value = "mymemory"
        settings.get_source_lang.return_value = "en"
        settings.get_target_lang.return_value = "ru"
        repo = MagicMock()
        repo.get_today.return_value = None
        word_service = MagicMock()
        word_service.add_word.side_effect = RuntimeError("database unavailable")
        translator = MagicMock()
        translator.translate.return_value = "привет"
        source = MagicMock()
        source.get_word.return_value = {"word": "hello", "level": "A1"}

        service = WOTDService(settings, repo, word_service, translator, source)

        assert service.get_word_of_the_day() is None
        repo.mark_shown.assert_not_called()


def _csv_content(rows: list[list[str]]) -> str:
    """Build CSV string from rows (header included)."""
    lines = [",".join(row) for row in rows]
    return "\n".join(lines) + "\n"


class TestGetTodayDisplay:
    """get_today_display() banner data tests."""

    def _service(self, entry, candidates):
        repo = MagicMock()
        repo.get_today.return_value = entry
        word_service = MagicMock()
        word_service.get_words.return_value = candidates
        word_service.get_translation.return_value = candidates[0].translation if candidates else None
        return WOTDService(MagicMock(), repo, word_service, MagicMock(), MagicMock())

    def test_none_when_not_shown_yet(self):
        """No banner before today's word is shown."""
        service = self._service(None, [])
        assert service.get_today_display() is None

    def test_returns_word_translation_level(self):
        """Banner shows word, translation and level."""
        entry = WOTDHistory(word="hello", level="A1", shown_date="2026-01-01")
        candidates = [Word(id=1, phrase="hello", translation="привет")]
        assert self._service(entry, candidates).get_today_display() == (
            "hello",
            "привет",
            "A1",
        )

    def test_translation_none_when_missing(self):
        """Banner still shows the word when translation is absent."""
        entry = WOTDHistory(word="hello", level="B2", shown_date="2026-01-01")
        candidates = [Word(id=1, phrase="hello", translation="")]
        assert self._service(entry, candidates).get_today_display() == (
            "hello",
            None,
            "B2",
        )


class TestCEFRLevels:
    """Tests for CEFR_LEVELS constant."""

    def test_cefr_levels_contains_all_levels(self):
        """Test that CEFR_LEVELS contains all expected levels."""
        assert "A1" in CEFR_LEVELS
        assert "A2" in CEFR_LEVELS
        assert "B1" in CEFR_LEVELS
        assert "B2" in CEFR_LEVELS
        assert "C1" in CEFR_LEVELS
        assert "C2" in CEFR_LEVELS

    def test_cefr_levels_length(self):
        """Test that CEFR_LEVELS has 6 levels."""
        assert len(CEFR_LEVELS) == 6


class TestLocalWordSource:
    """Tests for LocalWordSource."""

    @patch("infrastructure.word_source.LocalWordSource._load_words")
    def test_get_word_returns_dict_with_word_and_level(self, mock_load):
        """Test that get_word returns dict with word and level keys."""
        mock_load.return_value = {"A1": ["hello", "world"]}
        source = LocalWordSource()
        result = source.get_word("A1")
        assert result is not None
        assert "word" in result
        assert "level" in result

    @patch("infrastructure.word_source.LocalWordSource._load_words")
    def test_get_word_returns_none_for_empty_level(self, mock_load):
        """Test that get_word returns None for level with no words."""
        mock_load.return_value = {"A1": []}
        source = LocalWordSource()
        result = source.get_word("A1")
        assert result is None

    @patch("infrastructure.word_source.LocalWordSource._load_words")
    def test_get_word_returns_none_for_missing_level(self, mock_load):
        """Test that get_word returns None for non-existent level."""
        mock_load.return_value = {"A1": ["hello"]}
        source = LocalWordSource()
        result = source.get_word("B2")
        assert result is None

    @patch("infrastructure.word_source.LocalWordSource._load_words")
    def test_get_word_uppercases_level(self, mock_load):
        """Test that get_word uppercases the level parameter."""
        mock_load.return_value = {"A1": ["hello"]}
        source = LocalWordSource()
        result = source.get_word("a1")
        assert result is not None
        assert result["level"] == "A1"

    @patch("infrastructure.word_source.LocalWordSource._load_words")
    def test_get_available_levels(self, mock_load):
        """Test that get_available_levels returns sorted keys."""
        mock_load.return_value = {"B2": [], "A1": [], "C1": []}
        source = LocalWordSource()
        levels = source.get_available_levels()
        assert levels == ["A1", "B2", "C1"]

    def test_load_words_file_not_found(self):
        """Test that _load_words returns empty dict when file not found."""
        with patch("infrastructure.word_source.os.path.join", return_value="/nonexistent/ENGLISH_CERF_WORDS.csv"):
            source = LocalWordSource()
            assert source.words == {}

    def test_load_words_valid_csv(self):
        """Test that _load_words correctly parses CSV."""
        csv_data = _csv_content([
            ["headword", "CEFR"],
            ["hello", "A1"],
            ["world", "A1"],
            ["abandon", "B1"],
        ])
        with (
            patch("builtins.open", mock_open(read_data=csv_data)),
            patch("infrastructure.word_source.os.path.join", return_value="fake_path"),
        ):
            source = LocalWordSource()
            assert source.words == {"A1": ["hello", "world"], "B1": ["abandon"]}

    def test_load_words_deduplicates(self):
        """Test that _load_words deduplicates words within a level."""
        csv_data = _csv_content([
            ["headword", "CEFR"],
            ["about", "A1"],
            ["about", "A1"],
        ])
        with (
            patch("builtins.open", mock_open(read_data=csv_data)),
            patch("infrastructure.word_source.os.path.join", return_value="fake_path"),
        ):
            source = LocalWordSource()
            assert source.words == {"A1": ["about"]}

    def test_load_words_skips_bad_rows(self):
        """Test that _load_words skips rows with missing fields."""
        csv_data = _csv_content([
            ["headword", "CEFR"],
            ["good", "A1"],
            [""],
        ])
        with (
            patch("builtins.open", mock_open(read_data=csv_data)),
            patch("infrastructure.word_source.os.path.join", return_value="fake_path"),
        ):
            source = LocalWordSource()
            assert source.words == {"A1": ["good"]}


def test_wotd_uses_selected_language(word_service, settings_service):
    settings_service.set_setting("target_lang", "ru")
    word_service.add_word("hello", "privet")
    settings_service.set_setting("target_lang", "es")
    settings_service.set_setting("wotd_enabled", "true")
    repo = MagicMock()
    repo.get_today.return_value = None
    translator = MagicMock()
    translator.translate.return_value = "hola"
    source = MagicMock()
    source.get_word.return_value = {"word": "hello", "level": "A1"}
    service = WOTDService(settings_service, repo, word_service, translator, source)

    word = service.get_word_of_the_day()

    assert word.translation == "hola"
    assert word.language_code == "es"
    repo.get_today.return_value = WOTDHistory(word="hello", level="A1")
    assert service.get_today_display() == ("hello", "hola", "A1")
    settings_service.set_setting("target_lang", "ru")
    assert service.get_today_display() == ("hello", "privet", "A1")
