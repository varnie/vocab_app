"""Composition root: wire application services to external adapters."""

import logging
import os

from application.factory import ServiceFactory
from application.vocab_service import VocabService
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

    factory = ServiceFactory(
        word_repo=word_repo,
        stats_repo=stats_repo,
        settings_repo=settings_repo,
        language_repo=language_repo,
        wotd_repo=wotd_repo,
        translation_service=translation_service,
        word_source=LocalWordSource(),
        write_phrase=write_current_phrase,
        write_csv=write_vocabulary_csv,
    )

    factory.settings_service.initialize_defaults()

    return VocabService(
        db=db,
        factory=factory,
    )
