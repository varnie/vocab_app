"""Integration tests for SQLite foreign-key enforcement."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from repositories.language_repository import LanguageRepository
from repositories.sqlite import SQLiteDatabase
from repositories.word_repository import WordRepository


@pytest.fixture
def file_db(tmp_path):
    """Real SQLiteDatabase on a temp file (exercises connect() + pragmas)."""
    db = SQLiteDatabase(str(tmp_path / "fk_test.db"))
    db.connect()
    LanguageRepository(db).init_defaults()
    yield db
    db.close()


class TestForeignKeys:
    """Declared FK cascades must be enforced by the database, not just the ORM."""

    def test_pragma_foreign_keys_on(self, file_db):
        """Every pooled connection must enforce foreign keys."""
        with file_db.engine.connect() as conn:
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1

    def test_delete_word_cascades_at_db_level(self, file_db):
        """Raw-SQL parent delete must cascade to translations via FK."""
        repo = WordRepository(file_db)
        word = repo.save_word("cascade-me", None, "ru")
        repo.add_translation(word.id, "каскад", "ru")

        # Bypass ORM cascades: DB-level ON DELETE CASCADE must clean up.
        file_db.session.execute(text("DELETE FROM words WHERE id = :id"), {"id": word.id})
        file_db.commit()

        remaining = file_db.session.execute(
            text("SELECT COUNT(*) FROM translations WHERE word_id = :id"), {"id": word.id}
        ).scalar()
        assert remaining == 0

    def test_orphan_translation_rejected(self, file_db):
        """Inserting a translation for a missing word must fail."""
        with pytest.raises(IntegrityError):
            file_db.session.execute(
                text(
                    "INSERT INTO translations (word_id, language_id, translation) "
                    "VALUES (999999, 1, 'orphan')"
                )
            )
            file_db.commit()
        file_db.rollback()
