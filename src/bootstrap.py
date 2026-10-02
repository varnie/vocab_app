"""Composition root: wire application services to external adapters."""

import logging
import os

from application.export_service import ExportService
from application.notification_service import NotificationService
from application.review_service import ReviewService
from application.settings_service import SettingsService
from application.translation_test_service import TranslationTestService
from application.vocab_service import VocabService
from application.word_service import WordManagementService
from application.wotd_service import WOTDService
from constants import CONFIG_FILE
from infrastructure.csv_export import write_vocabulary_csv
from infrastructure.current_phrase import write_current_phrase
from infrastructure.data_paths import get_db_path
from infrastructure.translation import TranslationServiceImpl
from infrastructure.word_source import LocalWordSource
from repositories import (
    LanguageRepository,
    SettingsRepository,
    SQLiteDatabase,
    StatsRepository,
    WordRepository,
    WOTDRepository,
)

logger = logging.getLogger(__name__)


def create_vocab_service(
    config_file: str = CONFIG_FILE,
    must_exist: bool = False,
    db_path: str | None = None,
) -> VocabService | None:
    """Create and initialize VocabService with default implementations."""
    final_db_path = get_db_path(config_file) if db_path is None else db_path

    if not os.path.exists(final_db_path):
        if must_exist:
            logger.error("Database not found at %s", final_db_path)
            logger.info("Please run the GUI app first to initialize the database.")
            return None

        db_dir = os.path.dirname(final_db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    db = SQLiteDatabase(final_db_path)
    db.connect()

    word_repo = WordRepository(db)
    stats_repo = StatsRepository(db)
    settings_repo = SettingsRepository(db)
    language_repo = LanguageRepository(db)
    language_repo.init_defaults()
    wotd_repo = WOTDRepository(db)
    translation_service = TranslationServiceImpl()

    settings = SettingsService(settings_repo)
    settings.initialize_defaults()
    words = WordManagementService(word_repo, language_repo, settings, translation_service)
    reviews = ReviewService(word_repo, stats_repo, settings)

    return VocabService(
        _db=db,
        language_repo=language_repo,
        word_service=words,
        review_service=reviews,
        settings_service=settings,
        export_service=ExportService(word_repo, settings, write_vocabulary_csv),
        wotd_service=WOTDService(settings, wotd_repo, words, translation_service, LocalWordSource()),
        notification_service=NotificationService(reviews, words, write_current_phrase),
        translation_test_service=TranslationTestService(translation_service),
    )
