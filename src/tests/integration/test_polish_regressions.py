"""Data-loss and request-race regressions using temporary SQLite databases."""

import csv
import sqlite3
import time
from unittest.mock import Mock

import pytest
from sqlalchemy import text

from application.translation_test_service import TranslationTestService
from bootstrap import create_vocab_service
from domain.entities import WordSnapshot
from domain.exceptions import TranslationError
from infrastructure.config_file import read_config, write_config
from infrastructure.data_paths import get_db_path
from infrastructure.data_relocation import (
    DataDirChoice,
    RelocationVerdict,
    apply_pending_relocation,
    relocate_database,
)
from infrastructure.models import History, Translation, Word, WordPause, WordStats
from infrastructure.translation import TranslationServiceImpl


@pytest.fixture
def library(tmp_path):
    service = create_vocab_service(db_path=str(tmp_path / "vocab.db"))
    yield service
    service.close()


def rows(service):
    return {
        model.__tablename__: [
            tuple(getattr(row, col.name) for col in model.__table__.columns)
            for row in service._db.session.query(model).all()
        ]
        for model in (Word, Translation, WordStats, History, WordPause)
    }


def test_whole_word_undo_restores_every_row_after_filtered_query(library):
    word = library.add_word("Hello", "bonjour", target_lang="fr")
    library.add_word("Hello", "Hallo", target_lang="de")
    library.review_word(word.id)
    library.review_word(word.id)
    library.snooze_word(word.id, int(time.time()) + 86400)
    before = rows(library)
    assert library.get_words(target_lang="ru", untranslated=True)[0].translation == ""
    snapshot = library.delete_word_with_undo(word.id)
    assert isinstance(snapshot, WordSnapshot)
    assert snapshot.word.phrase == "Hello"
    assert len(snapshot.translations) == 2
    assert all(not values for values in rows(library).values())
    library.restore_word(snapshot)
    assert rows(library) == before


def test_undo_conflict_preserves_new_data_and_rolls_back(library):
    word = library.add_word("First", "one")
    snapshot = library.delete_word_with_undo(word.id)
    library.add_word("Second", "two")
    before = rows(library)
    with pytest.raises(ValueError, match=r"newer data|cannot safely"):
        library.restore_word(snapshot)
    assert rows(library) == before


def test_failed_translation_insert_does_not_leave_a_word(library):
    library._db.session.execute(text(
        "CREATE TRIGGER reject_insert BEFORE INSERT ON translations "
        "BEGIN SELECT RAISE(ABORT, 'insert rejected'); END"
    ))
    library._db.commit()
    with pytest.raises(Exception, match="insert rejected"):
        library.add_word("Incomplete", "translation")
    assert library.word_service.word_repo.get_by_phrase("Incomplete") is None
    assert not rows(library)["translations"]
    # A failure must not poison the session or remove a pre-existing phrase.
    word = library.add_word("Existing")
    with pytest.raises(Exception, match="insert rejected"):
        library.add_word("Existing", "translation")
    assert library.word_service.word_repo.get_by_phrase("Existing").id == word.id


def test_export_all_languages_and_untranslated(library, tmp_path):
    library.add_word("Hello", "привет", target_lang="ru")
    library.add_word("Hello", "bonjour", target_lang="fr")
    library.add_word("Untranslated")
    # Simulate a browser loading only a subset into the same SQLAlchemy session.
    library.get_words(target_lang="ru")
    path = tmp_path / "words.csv"
    library.export_csv(str(path))
    with path.open() as stream:
        exported = list(csv.DictReader(stream))
    assert {(row["source"], row["target"], row["target language"]) for row in exported} == {
        ("Hello", "привет", "ru"), ("Hello", "bonjour", "fr"), ("Untranslated", "", ""),
    }
    library.export_csv(str(path), "fr")
    with path.open() as stream:
        assert [row["target"] for row in csv.DictReader(stream)] == ["bonjour", ""]


def test_wotd_keeps_request_language(library, monkeypatch):
    library.set_setting("wotd_enabled", "true")
    monkeypatch.setattr(library.wotd_service.word_source, "get_word", lambda _: {"word": "Apple", "level": "A1"})

    def translate(*_args):
        library.set_setting("target_lang", "fr")
        return "яблоко"

    monkeypatch.setattr(library.wotd_service.translation_service, "translate", translate)
    word = library.get_word_of_the_day()
    assert word.language_code == "ru"
    assert library.word_service.word_repo.get_translation(word.id, "fr") is None


def test_provider_test_cannot_succeed_via_fallback(monkeypatch):
    selected, fallback = Mock(), Mock()
    selected.translate.side_effect = TranslationError("selected provider failed")
    fallback.translate.return_value = "fallback result"
    monkeypatch.setattr("infrastructure.translation.ProviderRegistry.get", lambda name:
                        selected if name == "google_direct" else fallback)
    translator = TranslationServiceImpl()
    assert not TranslationTestService(translator).test_connection(provider_name="google_direct")
    fallback.translate.assert_not_called()
    assert translator.translate("hello", provider_name="google_direct") == "fallback result"


def test_hidden_filter_and_resume_do_not_record_exposures(library):
    word = library.add_word("Hidden", "translation")
    library.add_word("Visible", "translation")
    until = int(time.time()) + 86400
    library.snooze_word(word.id, until)
    result = library.get_words(target_lang="ru", hidden_only=True)
    assert [(item.id, item.hidden_until) for item in result] == [(word.id, until)]
    library.snooze_word(word.id, 0)
    assert library.get_words(hidden_only=True) == []
    assert rows(library)["history"] == []


@pytest.mark.parametrize("choice", [DataDirChoice.MOVE, DataDirChoice.START_EMPTY])
def test_relocation_waits_for_restart_and_includes_late_writes(tmp_path, choice):
    config = str(tmp_path / "config.json")
    original = tmp_path / "old"
    destination = tmp_path / "new"
    assert write_config(config, {"data_dir": str(original)})
    service = create_vocab_service(config)
    try:
        service.add_word("Before", "до")
        result = relocate_database(config, str(destination), lambda: choice)
        assert result.verdict is RelocationVerdict.SCHEDULED
        assert get_db_path(config) == str(original / "vocab.db")
        assert not destination.exists()
        service.save_settings({"target_lang": "fr"})
        service.add_word("After", "après")
    finally:
        service.close()
    apply_pending_relocation(config)
    assert (original / "vocab.db").exists()
    assert get_db_path(config) == str(destination / "vocab.db")
    service = create_vocab_service(config)
    try:
        phrases = [word.phrase for word in service.get_words()]
        assert phrases == (["After", "Before"] if choice is DataDirChoice.MOVE else [])
        service.add_word("New location", "works")
    finally:
        service.close()


def test_relocation_handles_wal_and_config_failure_without_data_loss(tmp_path, monkeypatch):
    config = str(tmp_path / "config.json")
    original = tmp_path / "old"
    original.mkdir()
    destination = tmp_path / "new"
    assert write_config(config, {"data_dir": str(original)})
    with sqlite3.connect(original / "vocab.db") as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES ('committed in WAL')")
        connection.commit()
        relocate_database(config, str(destination), lambda: DataDirChoice.MOVE)
        saved_config = read_config(config)
        with monkeypatch.context() as patch:
            patch.setattr("infrastructure.data_relocation.write_config", lambda *_: False)
            with pytest.raises(OSError, match="activate"):
                apply_pending_relocation(config)
        assert read_config(config) == saved_config
        assert not (destination / "vocab.db").exists()
        apply_pending_relocation(config)
        with sqlite3.connect(destination / "vocab.db") as copied:
            assert copied.execute("SELECT value FROM sample").fetchone() == ("committed in WAL",)


@pytest.mark.parametrize("choice", [DataDirChoice.MOVE, DataDirChoice.START_EMPTY])
def test_relocation_refuses_destination_created_after_scheduling(tmp_path, choice):
    config = str(tmp_path / "config.json")
    original = tmp_path / "old"
    destination = tmp_path / "new"
    write_config(config, {"data_dir": str(original)})
    relocate_database(config, str(destination), lambda: choice)
    destination.mkdir()
    target = destination / "vocab.db"
    target.write_bytes(b"another library")
    with pytest.raises(FileExistsError):
        apply_pending_relocation(config)
    assert target.read_bytes() == b"another library"
    assert get_db_path(config) == str(original / "vocab.db")
