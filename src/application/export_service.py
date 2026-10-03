"""Export service - handles all export operations."""

from collections.abc import Callable

from application.settings_service import SettingsService
from domain.entities import Word
from domain.repositories import AbstractWordRepository


class ExportService:
    """Service for exporting words to various formats."""

    def __init__(
        self,
        word_repo: AbstractWordRepository,
        settings_service: SettingsService,
        write_csv: Callable[[str, list[Word], str], None],
    ) -> None:
        self.word_repo = word_repo
        self.settings_service = settings_service
        self._write_csv = write_csv

    def export_csv(self, filepath: str, target_lang: str | None = None) -> None:
        """Export all words to CSV file."""
        words = self.word_repo.get_export_rows(target_lang)
        source_lang = self.settings_service.get_source_lang()
        self._write_csv(filepath, words, source_lang)
