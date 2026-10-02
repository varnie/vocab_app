"""Opt-in reproducible queue measurement: RUN_QUEUE_BENCHMARK=1 pytest -s ..."""

import os
import statistics
import time

import pytest
from sqlalchemy import insert

from bootstrap import create_vocab_service
from infrastructure.models import History, Language, Translation, Word


@pytest.mark.skipif(os.environ.get("RUN_QUEUE_BENCHMARK") != "1", reason="opt-in benchmark")
def test_large_queue(tmp_path):
    service = create_vocab_service(db_path=str(tmp_path / "benchmark.db"))
    try:
        db = service._db
        language_id = db.session.query(Language.id).filter_by(code="ru").scalar()
        db.remove_session()
        with db.engine.begin() as connection:
            connection.execute(insert(Word), [
                {"id": i, "phrase": f"word{i:05}", "created_at": i} for i in range(1, 10001)
            ])
            connection.execute(insert(Translation), [
                {"word_id": i, "language_id": language_id, "translation": f"translation{i}"}
                for i in range(1, 10001)
            ])
            for batch in range(20):
                connection.execute(insert(History), [
                    {"word_id": i, "reviewed_at": 1000 + batch} for i in range(1, 10001)
                ])
        elapsed = []
        for _ in range(11):
            start = time.perf_counter()
            assert service.review_service.get_next_word() is not None
            elapsed.append((time.perf_counter() - start) * 1000)
        print(f"\n10,000 words / 200,000 exposures: median={statistics.median(elapsed[1:]):.2f} ms")
    finally:
        service.close()
