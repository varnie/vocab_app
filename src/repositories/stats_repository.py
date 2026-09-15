"""Statistics repository - handles review stats and history."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from domain.entities import History, Stats, WordStats
from domain.repositories import AbstractStatsRepository
from domain.time_utils import today_start_ts, utc_now_ts
from infrastructure import mappers
from infrastructure.models import History as ORMHistory
from infrastructure.models import Language as ORMLanguage
from infrastructure.models import Translation as ORMTranslation
from infrastructure.models import Word as ORMWord
from infrastructure.models import WordStats as ORMWordStats
from repositories.base import AbstractRepository


class StatsRepository(AbstractStatsRepository, AbstractRepository):
    """Repository for word statistics."""

    def update_word_stats(
        self, word_id: int
    ) -> None:
        """Update word stats (set last_reviewed to now)."""
        now = utc_now_ts()
        stats = self.db.session.query(ORMWordStats).filter_by(word_id=word_id).first()

        if stats:
            stats.last_reviewed = now
        else:
            stats = ORMWordStats(
                word_id=word_id,
                last_reviewed=now,
            )
            self.db.session.add(stats)

        self.commit()

    def get_word_stats(self, word_id: int) -> WordStats | None:
        """Get stats for a word."""
        orm = self.db.session.query(ORMWordStats).filter_by(word_id=word_id).first()
        if not orm:
            return None
        return mappers.map_word_stats(orm)

    def record_review(self, word_id: int) -> History:
        """Record a review in history and return domain entity."""
        orm_history = ORMHistory(word_id=word_id)
        self.db.session.add(orm_history)
        self.commit()
        return mappers.map_history(orm_history)

    def get_stats(self) -> Stats:
        """Get overall statistics."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        today_start = today_start_ts()
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
            db.query(func.date(ORMHistory.reviewed_at, "unixepoch").label("day"))
            .distinct()
            .order_by(func.date(ORMHistory.reviewed_at, "unixepoch").desc())
            .all()
        )

        streak = 0
        if rows:
            review_dates = {row[0] for row in rows}
            check_date = today_date
            while check_date.strftime("%Y-%m-%d") in review_dates:
                streak += 1
                check_date -= timedelta(days=1)

        return mappers.map_stats(
            {
                "total_words": total,
                "today_words": today_words,
                "today_reviews": today_reviews,
                "total_reviews": total_reviews,
                "streak": streak,
            }
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
