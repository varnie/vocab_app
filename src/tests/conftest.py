"""Test fixtures and configuration."""

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from infrastructure.csv_export import write_vocabulary_csv
from repositories.sqlite import SQLiteDatabase


@pytest.fixture
def test_db(tmp_path):
    """Use production connection settings and transactions in an isolated database."""
    db = SQLiteDatabase(str(tmp_path / "vocab.db"))
    db.connect()
    yield db
    db.close()


@pytest.fixture
def word_repo(test_db):
    """Create WordRepository with test database."""
    from repositories.word_repository import WordRepository

    return WordRepository(test_db)


@pytest.fixture
def settings_repo(test_db):
    """Create SettingsRepository with test database."""
    from repositories.settings_repository import SettingsRepository

    return SettingsRepository(test_db)


@pytest.fixture
def stats_repo(test_db):
    """Create StatsRepository with test database."""
    from repositories.stats_repository import StatsRepository

    return StatsRepository(test_db)


@pytest.fixture
def language_repo(test_db):
    """Create LanguageRepository with test database."""
    from repositories.language_repository import LanguageRepository

    repo = LanguageRepository(test_db)
    repo.init_defaults()
    return repo


@pytest.fixture
def mock_translation_service():
    """Create mock translation service."""
    mock = MagicMock()
    mock.translate.return_value = "тест"
    return mock


@pytest.fixture
def vocab_service(
    test_db,
    language_repo,
    mock_translation_service,
    word_service,
    review_service,
    settings_service,
    export_service,
):
    """Create VocabService with all test dependencies."""
    from application.notification_service import NotificationService
    from application.vocab_service import VocabService
    from application.wotd_service import WOTDService

    return VocabService(
        _db=test_db,
        language_repo=language_repo,
        word_service=word_service,
        review_service=review_service,
        settings_service=settings_service,
        export_service=export_service,
        wotd_service=WOTDService(
            settings_service, MagicMock(), word_service, mock_translation_service, MagicMock(),
        ),
        notification_service=NotificationService(review_service, word_service, MagicMock()),
        _translator=mock_translation_service,
    )


@pytest.fixture
def word_service(
    word_repo,
    language_repo,
    settings_service,
    mock_translation_service,
):
    """Create WordManagementService for unit testing."""
    from application.word_service import WordManagementService

    return WordManagementService(
        word_repo=word_repo,
        language_repo=language_repo,
        settings_service=settings_service,
        translation_service=mock_translation_service,
    )


@pytest.fixture
def review_service(word_repo, stats_repo, settings_service):
    """Create ReviewService for unit testing."""
    from application.review_service import ReviewService

    return ReviewService(
        word_repo=word_repo,
        stats_repo=stats_repo,
        settings_service=settings_service,
    )


@pytest.fixture
def settings_service(settings_repo):
    """Create SettingsService for unit testing."""
    from application.settings_service import SettingsService

    return SettingsService(settings_repo)


@pytest.fixture
def export_service(word_repo, settings_service):
    """Create ExportService for unit testing."""
    from application.export_service import ExportService

    return ExportService(word_repo, settings_service, write_vocabulary_csv)


@pytest.fixture
def temp_csv_file():
    """Create temporary CSV file path."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)
