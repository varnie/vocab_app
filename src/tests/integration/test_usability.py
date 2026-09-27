"""User-facing regressions exercised against real SQLite repositories."""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event, text

from application.review_scheduler import ReviewScheduler
from bootstrap import create_vocab_service
from domain.time_utils import local_today_start_ts
from infrastructure.models import History, WordStats


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
        word = service.add_word("Before", "original")
        db.session.execute(text(
            "CREATE TRIGGER reject_translation BEFORE UPDATE ON translations "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        ))
        db.commit()
        with pytest.raises(Exception, match="rejected"):
            service.update_word(word.id, "After", "changed", target_lang="ru")
        assert service.word_service.word_repo.get_by_phrase("Before") is not None
        assert service.word_service.word_repo.get_by_phrase("After") is None
        db.session.execute(text(
            "CREATE TRIGGER reject_history BEFORE INSERT ON history "
            "BEGIN SELECT RAISE(ABORT, 'history rejected'); END"
        ))
        db.commit()
        with pytest.raises(Exception, match="history rejected"):
            service.review_word(word.id)
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
    with patch("application.service_interfaces.datetime", clock):
        assert settings_service.is_quiet_time()
        scheduler = ReviewScheduler(
            MagicMock(), MagicMock(), settings_service, MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(),
        )
        scheduler._check_wotd()
        scheduler.wotd_service.get_word_of_the_day.assert_not_called()
    settings_service.set_setting("quiet_start", "")
    settings_service.set_setting("quiet_end", "")
    scheduler.pause_until(time.time() + 3600)
    scheduler._check_wotd()
    scheduler.wotd_service.get_word_of_the_day.assert_not_called()


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
