"""Exercise the passive queue against SQLite with a controlled clock."""

import pytest

from infrastructure.models import History, WordStats
from repositories.word_repository import WordRepository

NOW = 2_000_000_000


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr("repositories.word_repository.utc_now_ts", lambda: NOW)


def expose(db, word, count, last):
    db.session.add_all([
        History(word_id=word.id, reviewed_at=last - count + index + 1)
        for index in range(count)
    ])
    db.commit()


@pytest.mark.parametrize("count,interval", [
    (1, 14400), (2, 86400), (3, 259200), (4, 604800), (5, 1209600), (100, 1209600),
])
def test_interval_boundary(word_service, review_service, test_db, count, interval):
    word = word_service.add_word("boundary", "translation")
    expose(test_db, word, count, NOW - interval + 1)
    assert review_service.get_next_word() is None
    test_db.session.query(History).filter_by(word_id=word.id).update({
        History.reviewed_at: History.reviewed_at - 1,
    })
    test_db.commit()
    assert review_service.get_next_word().id == word.id


def test_bulk_addition_allows_three_due_between_new_words(word_service, test_db):
    old = [word_service.add_word(f"old{i}", "translation") for i in range(4)]
    for word in old:
        expose(test_db, word, 4, NOW - 10 * 86400)
    new = [word_service.add_word(f"new{i}", "translation") for i in range(8)]

    chosen = []
    for _ in range(5):
        # Recreate the repository: the mix must survive restarts.
        word = WordRepository(test_db).get_for_review(limit=1, target_lang="ru")[0]
        chosen.append(word.id)
        expose(test_db, word, 1, NOW)

    assert chosen[0] == new[0].id
    assert set(chosen[1:4]) <= {word.id for word in old}
    assert len(set(chosen)) == 5
    assert chosen[4] == new[1].id


def test_new_words_fill_empty_due_queue(word_service, review_service, test_db):
    first = word_service.add_word("first", "translation")
    second = word_service.add_word("second", "translation")
    expose(test_db, first, 1, NOW)
    assert review_service.get_next_word().id == second.id
    expose(test_db, second, 1, NOW)
    assert review_service.get_next_word() is None


def test_relative_overdue_outweighs_lifetime_count(word_service, review_service, test_db):
    young = word_service.add_word("young", "translation")
    mature = word_service.add_word("mature", "translation")
    expose(test_db, young, 2, NOW - 86400)
    expose(test_db, mature, 20, NOW - 60 * 86400)
    assert review_service.get_next_word().id == mature.id


def test_legacy_timestamp_respects_cooldown(word_service, review_service, test_db):
    word = word_service.add_word("legacy", "translation")
    test_db.session.add(WordStats(word_id=word.id, last_reviewed=NOW))
    test_db.commit()
    assert review_service.get_next_word() is None


def test_other_language_does_not_consume_new_slot(word_service, word_repo, test_db):
    due = word_service.add_word("due", "translation")
    unseen = word_service.add_word("unseen", "translation")
    foreign = word_repo.add("foreign")
    word_repo.add_translation(foreign.id, "hola", "es")
    expose(test_db, due, 4, NOW - 8 * 86400)
    expose(test_db, foreign, 1, NOW)
    assert word_repo.get_for_review(limit=1, target_lang="ru")[0].id == unseen.id
    assert word_repo.get_for_review(limit=1, target_lang="es") == []
    assert word_repo.get_for_review(target_lang="unknown") == []


def test_due_selection_happens_before_limit(word_service, word_repo, test_db):
    for index in range(25):
        word = word_service.add_word(f"recent{index}", "translation")
        expose(test_db, word, 1, NOW)
    due = word_service.add_word("due", "translation")
    expose(test_db, due, 1, NOW - 14400)
    assert word_repo.get_for_review(limit=1, target_lang="ru")[0].id == due.id
    assert word_repo.get_for_review(limit=0, target_lang="ru") == []
