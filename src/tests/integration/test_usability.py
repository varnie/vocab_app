"""User-facing regressions exercised against real SQLite repositories."""

import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event, text

from application.review_scheduler import ReviewScheduler
from bootstrap import create_vocab_service
from domain.time_utils import local_today_start_ts
from infrastructure.models import History, WordStats


@pytest.fixture
def library(tmp_path):
    service = create_vocab_service(db_path=str(tmp_path / "vocab.db"))
    yield service
    service.close()


def test_edit_uses_displayed_language_and_preserves_spelling(word_service, word_repo):
    word = word_service.add_word("Hello", "привет")
    word_repo.add_translation(word.id, "bonjour", "fr")
    word_service.update_word(word.id, "Hello World", "salut", target_lang="fr")
    assert word_repo.get_by_phrase("HELLO WORLD").phrase == "Hello World"
    assert word_repo.get_translation(word.id, "ru").translation == "привет"
    assert word_repo.get_translation(word.id, "fr").translation == "salut"


def test_unicode_duplicates_and_literal_search(word_service, word_repo):
    first = word_service.add_word("École_100%", "School")
    assert word_service.add_word("ÉCOLE_100%", "School").id == first.id
    word_service.add_word("ÉcoleA100x", "Other")
    assert [w.id for w in word_service.get_words(search="éCOLE_100%", target_lang="ru")] == [first.id]
    word_service.delete_word("ÉCOLE_100%")
    assert word_repo.get_by_phrase("école_100%") is None


def test_saved_translation_skips_network_unless_forced(word_service, mock_translation_service):
    word_service.add_word("Hello", "Original")
    assert word_service.add_word("hello", auto_translate=True).translation == "Original"
    mock_translation_service.translate.assert_not_called()
    word_service.add_word("hello", auto_translate=True, force_translate=True)
    mock_translation_service.translate.assert_called_once()


def test_language_is_captured_before_translation(word_service, word_repo, settings_service):
    def translate(*_args):
        settings_service.set_setting("target_lang", "fr")
        return "Привет"

    word_service.translation_service.translate.side_effect = translate
    word = word_service.add_word("Hello", auto_translate=True, target_lang="ru", source_lang="en")
    assert word.language_code == "ru"
    assert word.translation == "Привет"
    assert word_repo.get_translation(word.id, "fr") is None


def test_untranslated_filter_respects_selected_language(word_service, word_repo):
    """Switching language must change the untranslated list (browser popup)."""
    word_service.add_word("apple", "яблоко")  # ru only
    word_service.add_word("banana")  # no translation at all
    cherry = word_service.add_word("cherry", "вишня")
    word_repo.add_translation(cherry.id, "Kirsche", "de")

    ru_missing = sorted(w.phrase for w in word_service.get_words(target_lang="ru", untranslated=True))
    de_missing = sorted(w.phrase for w in word_service.get_words(target_lang="de", untranslated=True))

    assert ru_missing == ["banana"]
    assert de_missing == ["apple", "banana"]


def test_delete_word_with_undo_removes_word_and_translations(library):
    """Whole-word delete (browser popup for untranslated rows)."""
    word = library.word_service.add_word("Gone", "Ушедший")

    library.word_service.delete_word_with_undo(word.id)

    assert library.word_service.get_words() == []
    assert library.word_service.get_translation(word.id) is None


def test_undo_word_delete_restores_word_with_translation(library):
    """Undo restores the original word and translation."""
    word = library.word_service.add_word("Back", "Назад")
    snapshot = library.word_service.delete_word_with_undo(word.id)
    assert library.word_service.get_words() == []
    library.word_service.restore_word(snapshot)
    assert library.word_service.get_words()[0].id == word.id
    assert library.word_service.get_translation(word.id) == "Назад"


def test_clear_translation_and_undo(word_service, word_repo):
    word = word_service.add_word("Hello", "Original")
    word_service.update_word(word.id, "Hello", "", target_lang="ru")
    assert word_repo.get_translation(word.id, "ru") is None
    assert [w.id for w in word_service.get_words(target_lang="ru", untranslated=True)] == [word.id]
    word_service.restore_translation(word.id, "Original", "ru")
    with pytest.raises(ValueError, match="already exists"):
        word_service.restore_translation(word.id, "Stale", "ru")
    assert word_repo.get_translation(word.id, "ru").translation == "Original"


def test_global_sort_and_language_reload(word_service, word_repo):
    for i in range(105):
        word = word_service.add_word(f"word{i:03}", f"ru{i:03}")
        word_repo.add_translation(word.id, f"fr{104 - i:03}", "fr")
    first = word_service.get_words(target_lang="ru", limit=100, descending=True)
    second = word_service.get_words(target_lang="ru", limit=100, offset=100, descending=True)
    assert first[0].phrase == "word104"
    assert second[-1].phrase == "word000"
    french = word_service.get_words(target_lang="fr", sort="translation", limit=1)
    assert french[0].phrase == "word104"
    assert french[0].translation == "fr000"


def test_snooze_and_earliest_eligibility(word_service, review_service):
    word = word_service.add_word("Hello", "Original")
    until = int(time.time()) + 86400
    word_service.snooze_word(word.id, until)
    assert review_service.get_next_word() is None
    assert review_service.next_available_at() == until
    word_service.snooze_word(word.id, 0)
    assert review_service.get_next_word().id == word.id
    review_service.review_word(word.id)
    assert review_service.get_next_word() is None
    assert review_service.next_available_at() >= int(time.time()) + 14398


def test_failed_edit_and_review_are_atomic(tmp_path):
    service = create_vocab_service(db_path=str(tmp_path / "atomic.db"))
    db = service._db
    try:
        word = service.word_service.add_word("Before", "original")
        db.session.execute(text(
            "CREATE TRIGGER reject_translation BEFORE UPDATE ON translations "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        ))
        db.commit()
        with pytest.raises(Exception, match="rejected"):
            service.word_service.update_word(word.id, "After", "changed", target_lang="ru")
        assert service.word_service.word_repo.get_by_phrase("Before") is not None
        assert service.word_service.word_repo.get_by_phrase("After") is None
        db.session.execute(text(
            "CREATE TRIGGER reject_history BEFORE INSERT ON history "
            "BEGIN SELECT RAISE(ABORT, 'history rejected'); END"
        ))
        db.commit()
        with pytest.raises(Exception, match="history rejected"):
            service.review_service.review_word(word.id)
        assert db.session.query(History).count() == 0
        assert db.session.query(WordStats).count() == 0
    finally:
        service.close()


def test_review_uses_one_commit(word_service, review_service, test_db):
    word = word_service.add_word("Hello", "Original")
    commits = []
    event.listen(test_db.session, "after_commit", lambda _session: commits.append(True))
    review_service.review_word(word.id)
    assert len(commits) == 1


def test_local_midnight():
    midnight = datetime.fromtimestamp(local_today_start_ts())
    assert (midnight.hour, midnight.minute, midnight.second) == (0, 0, 0)
    assert midnight.date() == datetime.now().date()


def test_quiet_hours_and_pause_cover_wotd(settings_service):
    settings_service.set_setting("quiet_start", "22:00")
    settings_service.set_setting("quiet_end", "08:00")
    clock = MagicMock(wraps=datetime)
    clock.now.return_value = datetime(2026, 9, 27, 23, 0)
    with patch("application.settings_service.datetime", clock):
        assert settings_service.is_quiet_time()
        scheduler = ReviewScheduler(
            MagicMock(), MagicMock(), settings_service, MagicMock(), MagicMock(),
            MagicMock(), MagicMock(),
        )
        scheduler.running = True
        scheduler._check_wotd()
        scheduler.wotd_service.get_word_of_the_day.assert_not_called()
    settings_service.set_setting("quiet_start", "")
    settings_service.set_setting("quiet_end", "")
    scheduler.set_paused(True)
    scheduler._check_wotd()
    scheduler.wotd_service.get_word_of_the_day.assert_not_called()
    restored = ReviewScheduler(
        MagicMock(), MagicMock(), settings_service, MagicMock(), MagicMock(),
        MagicMock(), MagicMock(),
    )
    assert restored.paused
    restored.set_paused(False)
    assert not restored.notifications_paused()
    assert settings_service.get_setting("paused") == "false"


def test_scheduler_records_exposure_and_releases_real_sqlite_session(library, monkeypatch):
    monkeypatch.setattr("application.review_scheduler.REVIEW_INITIAL_DELAY_SECONDS", 0)
    library.word_service.add_word("Hello", "original")
    monkeypatch.setattr(library.notification_service, "_write_phrase", lambda _: None)
    released = threading.Event()
    session_states = []
    notifications = []

    def cleanup():
        library.remove_session()
        session_states.append(library._db.ScopedSession.registry.has())
        released.set()

    scheduler = ReviewScheduler(
        library.review_service, library.wotd_service, library.settings_service,
        lambda body: notifications.append(body), lambda _: None,
        library.notification_service, lambda _: None, cleanup,
    )
    scheduler.start()
    try:
        assert released.wait(2)
        assert session_states == [False]
        assert notifications == ["<b>Hello</b>\n→ original [RU]"]
        assert library.review_service.get_stats()["total_reviews"] == 1
    finally:
        scheduler.stop()
    assert not scheduler._review_thread.is_alive()
    assert not scheduler._wotd_thread.is_alive()


def test_invalid_language_does_not_rename(word_service, word_repo):
    word = word_service.add_word("Original", "translation")
    with pytest.raises(ValueError, match="Unknown"):
        word_service.update_word(word.id, "Renamed", "new", target_lang="missing")
    assert word_repo.get_by_phrase("Original") is not None


def test_translation_worker_round_trip_and_termination(tmp_path, monkeypatch):
    from domain.exceptions import TranslationError
    from infrastructure.translation import GoogleDeepTranslatorProvider

    # A local provider double keeps the real process/pipe/deadline path offline.
    module = tmp_path / "deep_translator.py"
    module.write_text(
        "import time\n"
        "class GoogleTranslator:\n"
        "    def __init__(self, source, target): pass\n"
        "    def translate(self, text):\n"
        "        if text == 'slow': time.sleep(30)\n"
        "        return 'Bonjour — ' + text\n"
        "MyMemoryTranslator = GoogleTranslator\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    provider = GoogleDeepTranslatorProvider()
    assert provider.translate("École", "fr", "en") == "Bonjour — École"
    monkeypatch.setattr("infrastructure.translation.TRANSLATION_TIMEOUT_SECONDS", 0.3)
    started = time.monotonic()
    with pytest.raises(TranslationError, match="timed out"):
        provider.translate("slow", "fr", "en")
    assert time.monotonic() - started < 5
