"""Export service - handles all export operations."""

from typing import Callable

from application.service_interfaces import AbstractExportService, AbstractSettingsService
from domain.entities import Word
from domain.repositories import AbstractWordRepository


class ExportService(AbstractExportService):
    """Service for exporting words to various formats."""

    def __init__(
        self,
        word_repo: AbstractWordRepository,
        settings_service: AbstractSettingsService,
        write_csv: Callable[[str, list[Word], str], None],
    ) -> None:
        self.word_repo = word_repo
        self.settings_service = settings_service
        self._write_csv = write_csv

    def export_csv(self, filepath: str) -> None:
        """Export all words to CSV file."""
        words = self.word_repo.get_all()
        source_lang = self.settings_service.get_source_lang()
        self._write_csv(filepath, words, source_lang)
