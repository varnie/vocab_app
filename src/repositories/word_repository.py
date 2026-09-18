"""Word repository - handles word CRUD operations."""


from sqlalchemy import case, func
from sqlalchemy.orm import contains_eager, joinedload

from config import DEFAULT_TARGET_LANG
from domain.entities import Translation, Word
from domain.repositories import AbstractWordRepository
from domain.review_policy import EXPOSURE_INTERVALS, NEW_WORD_SPACING
from domain.time_utils import utc_now_ts
from infrastructure import mappers
from infrastructure.models import History as ORMHistory
from infrastructure.models import Language as ORMLanguage
from infrastructure.models import Translation as ORMTranslation
from infrastructure.models import Word as ORMWord
from infrastructure.models import WordStats as ORMWordStats
from repositories.base import AbstractRepository


class WordRepository(AbstractWordRepository, AbstractRepository):
    """Repository for word operations."""

    def _get_language(self, code: str) -> ORMLanguage | None:
        """Get language ORM row by code, or None if unknown."""
        return self.db.session.query(ORMLanguage).filter_by(code=code).first()

    def add(self, phrase: str) -> Word:
        """Add a word, return its domain entity."""
        phrase = phrase.lower()
        orm_word = self.db.session.query(ORMWord).filter_by(phrase=phrase).first()
        if orm_word:
            return mappers.map_word(orm_word)
        orm_word = ORMWord(phrase=phrase)
        self.db.session.add(orm_word)
        self.commit()
        return mappers.map_word(orm_word)

    def get_by_phrase(self, phrase: str) -> Word | None:
        """Get word by phrase."""
        orm_word = (
            self.db.session.query(ORMWord)
            .options(
                joinedload(ORMWord.stats),
                joinedload(ORMWord.translations).joinedload(ORMTranslation.language),
            )
            .filter_by(phrase=phrase.lower())
            .first()
        )
        if not orm_word:
            return None
        return mappers.map_word_with_details(orm_word)

    def get_all(
        self,
        search: str | None = None,
        target_lang: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        since: int | None = None,
    ) -> list[Word]:
        """Get all words with stats."""
        lang = None
        if target_lang:
            lang = self._get_language(target_lang)
            if not lang:
                return []

        query = self.db.session.query(ORMWord).options(joinedload(ORMWord.stats))

        if lang:
            query = query.join(
                ORMTranslation,
                (ORMTranslation.word_id == ORMWord.id) & (ORMTranslation.language_id == lang.id),
            ).options(
                contains_eager(ORMWord.translations)
            )
        else:
            query = query.options(
                joinedload(ORMWord.translations).joinedload(ORMTranslation.language)
            )

        if search:
            search_term = f"%{search}%"
            if lang:
                query = query.filter(
                    (ORMWord.phrase.ilike(search_term))
                    | (ORMTranslation.translation.ilike(search_term))
                )
            else:
                query = query.filter(ORMWord.phrase.ilike(search_term))

        if since is not None:
            query = query.filter(ORMWord.created_at >= since)

        query = query.distinct().order_by(ORMWord.phrase)
        if limit is not None:
            query = query.limit(limit).offset(offset)
        orm_words = query.all()
        return [mappers.map_word_with_details(w) for w in orm_words]

    def get_for_review(self, limit: int = 20, target_lang: str | None = None) -> list[Word]:
        """Return due exposures, mixing in one new word per four notifications.

        History represents exposure, not recall. Deriving the schedule from it
        keeps the queue persistent across restarts without a schema migration.
        """
        if limit <= 0:
            return []
        now = utc_now_ts()
        review_counts = (
            self.db.session.query(
                ORMHistory.word_id,
                func.count(ORMHistory.id).label("review_count"),
                func.max(ORMHistory.reviewed_at).label("last_shown"),
                func.min(ORMHistory.id).label("first_id"),
            )
            .group_by(ORMHistory.word_id)
            .subquery()
        )
        query = (
            self.db.session.query(ORMWord)
            .outerjoin(ORMWordStats)
            .outerjoin(review_counts, review_counts.c.word_id == ORMWord.id)
            .options(joinedload(ORMWord.stats))
        )

        if target_lang:
            lang = self._get_language(target_lang)
            if lang:
                query = (
                    query.join(
                        ORMTranslation,
                        (ORMWord.id == ORMTranslation.word_id)
                        & (ORMTranslation.language_id == lang.id),
                    )
                    .join(ORMTranslation.language)
                    .options(
                        contains_eager(ORMWord.translations).contains_eager(ORMTranslation.language)
                    )
                )
            else:
                return []
        else:
            query = query.options(
                joinedload(ORMWord.translations).joinedload(ORMTranslation.language)
            )

        count = func.coalesce(review_counts.c.review_count, 0)
        last_shown = func.coalesce(review_counts.c.last_shown, ORMWordStats.last_reviewed)
        interval = case(
            *((count <= index, seconds) for index, seconds in enumerate(EXPOSURE_INTERVALS, 1)),
            else_=EXPOSURE_INTERVALS[-1],
        )
        # A legacy timestamp without history still represents a previous exposure.
        unseen = (count == 0) & last_shown.is_(None)
        due = query.filter(~unseen, last_shown + interval <= now)
        # Relative overdue time makes a recently introduced word eligible before
        # a mature word with the same last-shown time. Randomize exact ties only.
        due = due.order_by(
            ((now - last_shown) / interval).desc(), func.random(),
        )

        recent = self.db.session.query(
            ORMHistory.id, review_counts.c.first_id,
        ).join(review_counts, review_counts.c.word_id == ORMHistory.word_id)
        if target_lang:
            recent = recent.join(
                ORMTranslation,
                (ORMTranslation.word_id == ORMHistory.word_id)
                & (ORMTranslation.language_id == lang.id),
            )
        recent = recent.order_by(ORMHistory.id.desc()).limit(NEW_WORD_SPACING - 1).all()
        allow_new = not any(row.id == row.first_id for row in recent)
        due_words = due.limit(limit).all()
        new_words = []
        if allow_new or not due_words:
            # Stable FIFO prevents a bulk import from starving older unseen words.
            new_words = query.filter(unseen).order_by(ORMWord.created_at, ORMWord.id).limit(1).all()
        orm_words = (new_words + due_words)[:limit]
        return [mappers.map_word_with_details(w) for w in orm_words]

    def delete(self, phrase: str) -> None:
        """Delete a word."""
        word = self.db.session.query(ORMWord).filter_by(phrase=phrase.lower()).first()
        if word:
            self.db.session.delete(word)
            self.commit()

    def add_translation(
        self, word_id: int, translation: str, target_lang: str = DEFAULT_TARGET_LANG
    ) -> None:
        """Add translation for a word."""
        lang = self._get_language(target_lang)
        if not lang:
            return

        existing = (
            self.db.session.query(ORMTranslation)
            .filter_by(word_id=word_id, language_id=lang.id)
            .first()
        )

        if existing:
            existing.translation = translation
        else:
            trans = ORMTranslation(word_id=word_id, translation=translation, language_id=lang.id)
            self.db.session.add(trans)

        self.commit()

    def get_translation(
        self, word_id: int, target_lang: str = DEFAULT_TARGET_LANG
    ) -> Translation | None:
        """Get translation for a word as domain entity."""
        lang = self._get_language(target_lang)
        if not lang:
            return None
        orm = (
            self.db.session.query(ORMTranslation)
            .filter_by(word_id=word_id, language_id=lang.id)
            .first()
        )
        if orm:
            return mappers.map_translation(orm)
        return None

    def update_word(self, word_id: int, phrase: str) -> None:
        """Update word phrase."""
        orm_word = self.db.session.query(ORMWord).filter_by(id=word_id).first()
        if orm_word:
            orm_word.phrase = phrase
            self.commit()

    def delete_by_id(self, word_id: int) -> None:
        """Delete a word by ID."""
        orm_word = self.db.session.query(ORMWord).filter_by(id=word_id).first()
        if orm_word:
            self.db.session.delete(orm_word)
            self.commit()

    def delete_translation(self, word_id: int, target_lang: str) -> None:
        """Delete translation for a specific language."""
        lang = self._get_language(target_lang)
        if lang:
            orm = (
                self.db.session.query(ORMTranslation)
                .filter_by(word_id=word_id, language_id=lang.id)
                .first()
            )
            if orm:
                self.db.session.delete(orm)
                self.commit()
