"""Tests for vocab_cli module."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from infrastructure import current_phrase
from vocab_cli import run_cli


@pytest.fixture(autouse=True)
def isolated_current_phrase_state(monkeypatch, tmp_path):
    """Keep CLI tests independent of the real user's runtime state."""
    state_dir = tmp_path / "state"
    monkeypatch.setattr(current_phrase, "STATE_DIR", str(state_dir))
    monkeypatch.setattr(current_phrase, "CURRENT_PHRASE_FILE", str(state_dir / "current_phrase.json"))


class TestRunCli:
    """Tests for run_cli function."""

    @patch("vocab_cli.create_vocab_service")
    def test_run_cli_no_args_returns_false(self, mock_create):
        """Test that run_cli returns False when no args provided."""
        with patch("sys.argv", ["vocab_cli"]):
            result = run_cli()
            assert result is False
            mock_create.assert_not_called()

    @patch("vocab_cli.create_vocab_service")
    @patch("vocab_cli.send_notification")
    def test_run_cli_save_no_clipboard_text(self, mock_notify, mock_create):
        """Test --save with no clipboard text."""
        mock_create.return_value = MagicMock()
        with patch("sys.argv", ["vocab_cli", "--save"]):
            with patch("vocab_cli.get_clipboard_text", return_value=None):
                result = run_cli()
                assert result is False
                mock_notify.assert_called_once_with("No text selected")
                mock_create.return_value.close.assert_called_once()

    @patch("vocab_cli.create_vocab_service")
    @patch("vocab_cli.send_notification")
    def test_run_cli_save_success(self, mock_notify, mock_create):
        """Test --save with successful word save."""
        mock_service = MagicMock()
        mock_service.add_word.return_value = MagicMock(id=1)
        mock_service.get_translation_with_lang.return_value = ("привет", "ru")
        mock_service.get_language_abbreviation.return_value = "RU"
        mock_create.return_value = mock_service

        with patch("sys.argv", ["vocab_cli", "--save"]):
            with patch("vocab_cli.get_clipboard_text", return_value="Hello"):
                result = run_cli()
                assert result is True
                mock_service.add_word.assert_called_once()

    @patch("vocab_cli.create_vocab_service")
    @patch("vocab_cli.send_notification")
    def test_run_cli_save_success_no_translation(self, mock_notify, mock_create):
        """Test --save when word has no translation."""
        mock_service = MagicMock()
        mock_service.add_word.return_value = MagicMock(id=1)
        mock_service.get_translation_with_lang.return_value = (None, None)  # No translation
        mock_create.return_value = mock_service

        with patch("sys.argv", ["vocab_cli", "--save"]):
            with patch("vocab_cli.get_clipboard_text", return_value="Hello"):
                result = run_cli()
                assert result is True
                mock_service.add_word.assert_called_once()
                # Should notify "Word saved: hello" (lowercase)
                mock_notify.assert_called_once_with("Word saved: hello")

    @patch("vocab_cli.create_vocab_service")
    @patch("vocab_cli.send_notification")
    def test_run_cli_save_value_error(self, mock_notify, mock_create):
        """Test --save with ValueError."""
        mock_service = MagicMock()
        mock_service.add_word.side_effect = ValueError("Invalid input")
        mock_create.return_value = mock_service

        with patch("sys.argv", ["vocab_cli", "--save"]):
            with patch("vocab_cli.get_clipboard_text", return_value="hello"):
                result = run_cli()
                assert result is True  # run_cli returns True even on error
                mock_notify.assert_called_once_with("Invalid input: Invalid input")

    @patch("vocab_cli.create_vocab_service")
    @patch("vocab_cli.send_notification")
    def test_run_cli_delete_no_temp_file(self, mock_notify, mock_create):
        """Test --delete when temp file doesn't exist."""
        mock_service = MagicMock()
        mock_create.return_value = mock_service

        with patch("sys.argv", ["vocab_cli", "--delete"]):
            result = run_cli()
            assert result is True
            mock_service.delete_word.assert_not_called()

    @patch("vocab_cli.create_vocab_service")
    @patch("vocab_cli.send_notification")
    def test_run_cli_delete_with_temp_file(self, mock_notify, mock_create):
        """Test --delete with temp file."""
        mock_service = MagicMock()
        mock_create.return_value = mock_service
        current_phrase.write_current_phrase("hello")

        with patch("sys.argv", ["vocab_cli", "--delete"]):
            with patch("argparse.ArgumentParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser.parse_args.return_value = argparse.Namespace(save=False, delete=True, next=False)
                mock_parser_class.return_value = mock_parser
                result = run_cli()
                assert result is True
                mock_service.delete_word.assert_called_once_with("hello")

    @patch("vocab_cli.create_vocab_service")
    @patch("vocab_cli.send_notification")
    def test_run_cli_save_generic_exception(self, mock_notify, mock_create):
        """Test --save with generic Exception."""
        mock_service = MagicMock()
        mock_service.add_word.side_effect = Exception("Generic error")
        mock_create.return_value = mock_service

        with patch("sys.argv", ["vocab_cli", "--save"]):
            with patch("vocab_cli.get_clipboard_text", return_value="hello"):
                result = run_cli()
                assert result is True  # Returns True even on error
                mock_notify.assert_called_once_with("Error: Generic error")

    @patch("vocab_cli.create_vocab_service")
    @patch("vocab_cli.send_notification")
    def test_run_cli_next_with_word(self, mock_notify, mock_create):
        """Test --next with a word to show."""
        mock_service = MagicMock()
        mock_service.get_next_word_notification.return_value = "Next word: hello"
        mock_create.return_value = mock_service

        with patch("sys.argv", ["vocab_cli", "--next"]):
            result = run_cli()
            assert result is True
            mock_notify.assert_called_once_with("Next word: hello")

    @patch("vocab_cli.create_vocab_service")
    @patch("vocab_cli.send_notification")
    def test_run_cli_next_no_word(self, mock_notify, mock_create):
        """Test --next with no word."""
        mock_service = MagicMock()
        mock_service.get_next_word_notification.return_value = None
        mock_create.return_value = mock_service

        with patch("sys.argv", ["vocab_cli", "--next"]):
            result = run_cli()
            assert result is True
            mock_notify.assert_not_called()

    @patch("vocab_cli.create_vocab_service", return_value=None)
    def test_run_cli_service_creation_fails(self, mock_create):
        """Test when vocab service creation fails."""
        with patch("sys.argv", ["vocab_cli", "--next"]):
            with pytest.raises(SystemExit) as exc_info:
                run_cli()
            assert exc_info.value.code == 1
