"""Integration tests for repository."""

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from infrastructure.models import WOTDHistory as ORMWOTDHistory


@pytest.mark.parametrize("existing", [False, True])
def test_settings_batch_failure_rolls_back_and_session_recovers(settings_service, settings_repo, test_db, existing):
    if existing:
        settings_service.save_settings({"source_lang": "en", "target_lang": "ru"})
    before = settings_repo.get_all()
    operation = "UPDATE" if existing else "INSERT"
    test_db.session.execute(text(
        f"CREATE TRIGGER reject_settings BEFORE {operation} ON settings "
        "WHEN NEW.key = 'target_lang' BEGIN SELECT RAISE(ABORT, 'rejected'); END"
    ))
    test_db.commit()
    with pytest.raises(IntegrityError, match="rejected"):
        settings_service.save_settings({"source_lang": "de", "target_lang": "fr"})
    assert settings_repo.get_all() == before
    settings_service.set_setting("source_lang", "es")
    assert settings_service.get_source_lang() == "es"


def test_settings_batch_uses_one_commit(settings_service, test_db):
    commits = []
    event.listen(test_db.session, "after_commit", lambda _session: commits.append(True))
    settings_service.save_settings({"source_lang": "de", "target_lang": "fr", "review_interval": "7200"})
    assert commits == [True]
    assert settings_service.get_source_lang() == "de"
    assert settings_service.get_target_lang() == "fr"
    assert settings_service.get_review_interval() == 7200


class TestWordRepositoryIntegration:
    """Integration tests for WordRepository."""

    def test_word_crud_full_cycle(self, word_repo):
        """Test full CRUD cycle."""
        # Create
        word = word_repo.save_word("testword", None, "ru")
        assert word.phrase == "testword"

        # Read
        found = word_repo.get_by_phrase("testword")
        assert found is not None
        assert found.phrase == "testword"

        # Update
        word_repo.update_word(word.id, "updatedword")
        updated = word_repo.get_by_phrase("updatedword")
        assert updated is not None

        # Delete
        word_repo.delete("updatedword")
        deleted = word_repo.get_by_phrase("updatedword")
        assert deleted is None

    def test_delete_translation(self, word_repo):
        """Test deleting translation."""
        word = word_repo.save_word("todelete", None, "ru")
        word_repo.add_translation(word.id, "удалить", "ru")

        word_repo.delete_translation(word.id, "ru")

        translation = word_repo.get_translation(word.id, "ru")
        assert translation is None

    def test_stats_recording(self, word_repo, stats_repo):
        """Test recording review stats."""
        word = word_repo.save_word("statstest", None, "ru")

        history = stats_repo.record_review(word.id, update_stats=True)
        record = word_repo.get_by_phrase("statstest")

        assert record is not None
        assert record.last_reviewed is not None
        assert record.last_reviewed == history.reviewed_at
        assert stats_repo.get_stats().total_reviews == 1


class TestWOTDRepositoryIntegration:
    """Integration tests for WOTD history uniqueness."""

    def test_double_mark_shown_same_day_is_idempotent(self, test_db):
        """Concurrent mark_shown() calls must not duplicate today's row."""
        from repositories.wotd_repository import WOTDRepository

        repo = WOTDRepository(test_db)
        repo.mark_shown("hello", "A1")
        repo.mark_shown("hello", "A1")  # Must not raise.

        today = repo.get_today()
        assert today is not None
        assert today.word == "hello"

        rows = (
            test_db.session.query(ORMWOTDHistory)
            .filter_by(shown_date=today.shown_date)
            .all()
        )
        assert len(rows) == 1
