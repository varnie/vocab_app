"""Statistics repository - handles review stats and history."""

from datetime import datetime, timedelta

from sqlalchemy import func

from domain.entities import History, Stats
from domain.repositories import AbstractStatsRepository
from domain.time_utils import local_today_start_ts, utc_now_ts
from infrastructure import mappers
from infrastructure.models import History as ORMHistory
from infrastructure.models import Language as ORMLanguage
from infrastructure.models import Translation as ORMTranslation
from infrastructure.models import Word as ORMWord
from infrastructure.models import WordStats as ORMWordStats
from repositories.base import AbstractRepository


class StatsRepository(AbstractStatsRepository, AbstractRepository):
    """Repository for word statistics."""

    def record_review(self, word_id: int, update_stats: bool = False) -> History:
        """Record a review in history and return domain entity."""
        now = utc_now_ts()
        orm_history = ORMHistory(word_id=word_id, reviewed_at=now)
        if update_stats:
            stats = self.db.session.query(ORMWordStats).filter_by(word_id=word_id).first()
            if stats is None:
                stats = ORMWordStats(word_id=word_id)
                self.db.session.add(stats)
            stats.last_reviewed = now
        self.db.session.add(orm_history)
        self.commit()
        return mappers.map_history(orm_history)

    def get_stats(self) -> Stats:
        """Get overall statistics."""
        now = datetime.now()
        today_start = local_today_start_ts()
        today_date = now.date()

        db = self.db.session

        # Combined: total words + today's new words.
        # Counts words directly so words without a translation are included.
        total_today = (
            db.query(
                func.count(ORMWord.id).label("total"),
                func.count(ORMWord.id).filter(ORMWord.created_at >= today_start).label("today_words"),
            )
            .select_from(ORMWord)
            .first()
        )
        total = total_today.total or 0
        today_words = total_today.today_words or 0

        # Combined: total reviews + today's reviews
        review_counts = (
            db.query(
                func.count(ORMHistory.id).label("total_reviews"),
                func.count(ORMHistory.id).filter(ORMHistory.reviewed_at >= today_start).label("today_reviews"),
            )
            .first()
        )
        total_reviews = review_counts.total_reviews or 0
        today_reviews = review_counts.today_reviews or 0

        # Streak — single query for distinct review dates
        rows = (
            db.query(func.date(ORMHistory.reviewed_at, "unixepoch", "localtime").label("day"))
            .distinct()
            .order_by(func.date(ORMHistory.reviewed_at, "unixepoch", "localtime").desc())
            .all()
        )

        streak = 0
        if rows:
            review_dates = {row[0] for row in rows}
            check_date = today_date
            while check_date.strftime("%Y-%m-%d") in review_dates:
                streak += 1
                check_date -= timedelta(days=1)

        return Stats(
            total_words=total,
            today_words=today_words,
            today_reviews=today_reviews,
            total_reviews=total_reviews,
            streak=streak,
        )

    def get_language_counts(self) -> dict:
        """Get word count per language."""
        results = (
            self.db.session.query(
                ORMLanguage.code,
                ORMLanguage.name,
                func.count(func.distinct(ORMTranslation.word_id)).label("count"),
            )
            .join(ORMTranslation, ORMTranslation.language_id == ORMLanguage.id)
            .join(ORMWord, ORMWord.id == ORMTranslation.word_id)
            .group_by(ORMLanguage.id)
            .all()
        )

        return {row.code: (row.name, row.count) for row in results}
