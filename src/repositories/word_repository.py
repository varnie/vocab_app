"""Word repository - handles word CRUD operations."""

from dataclasses import asdict

from sqlalchemy import case, func
from sqlalchemy.orm import aliased, contains_eager, joinedload

from config import DEFAULT_TARGET_LANG
from domain.entities import Translation, Word, WordSnapshot
from domain.entities import WordPause as PauseSnapshot
from domain.repositories import AbstractWordRepository
from domain.review_policy import EXPOSURE_INTERVALS, NEW_WORD_SPACING
from domain.time_utils import utc_now_ts
from infrastructure import mappers
from infrastructure.models import History as ORMHistory
from infrastructure.models import Language as ORMLanguage
from infrastructure.models import Translation as ORMTranslation
from infrastructure.models import Word as ORMWord
from infrastructure.models import WordPause
from infrastructure.models import WordStats as ORMWordStats
from repositories.base import AbstractRepository


class WordRepository(AbstractWordRepository, AbstractRepository):
    """Repository for word operations."""

    def _get_language(self, code: str) -> ORMLanguage | None:
        """Get language ORM row by code, or None if unknown."""
        return self.db.session.query(ORMLanguage).filter_by(code=code).first()

    def save_word(self, phrase: str, translation: str | None, target_lang: str) -> Word:
        """Create a phrase and its translation in one transaction."""
        session = self.db.session
        try:
            lang = self._get_language(target_lang) if translation is not None else None
            if translation is not None and lang is None:
                raise ValueError("Unknown translation language")
            word = session.query(ORMWord).filter(func.casefold(ORMWord.phrase) == phrase.casefold()).first()
            if word is None:
                word = ORMWord(phrase=phrase)
                session.add(word)
                session.flush()
            if translation is not None:
                existing = session.query(ORMTranslation).filter_by(word_id=word.id, language_id=lang.id).first()
                if existing:
                    existing.translation = translation
                else:
                    session.add(ORMTranslation(word_id=word.id, language_id=lang.id, translation=translation))
            self.commit()
            return mappers.map_word(word)
        except Exception:
            session.rollback()
            raise

    def delete_with_snapshot(self, word_id: int) -> WordSnapshot:
        """Capture all dependent rows before deleting, including filtered-out translations."""
        session = self.db.session
        try:
            word = session.query(ORMWord).populate_existing().filter_by(id=word_id).first()
            if word is None:
                raise ValueError("This word has already been deleted. Refresh the browser.")

            def related(model, mapper):
                rows = session.query(model).populate_existing().filter_by(word_id=word_id).all()
                return tuple(mapper(row) for row in rows)

            snapshot = WordSnapshot(
                word=mappers.map_word(word),
                translations=related(ORMTranslation, mappers.map_translation),
                stats=related(ORMWordStats, mappers.map_word_stats),
                history=related(ORMHistory, mappers.map_history),
                pauses=related(WordPause, lambda row: PauseSnapshot(row.word_id, row.until)),
            )
            # Bulk delete uses database cascades, independent of partially loaded relationships.
            session.query(ORMWord).filter_by(id=word_id).delete(synchronize_session=False)
            self.commit()
            session.expire_all()
            return snapshot
        except Exception:
            session.rollback()
            raise

    def restore_snapshot(self, snapshot: WordSnapshot) -> None:
        """Restore original IDs and timestamps atomically; never overwrite newer data."""
        session = self.db.session
        try:
            phrase = snapshot.word.phrase
            if self.get_by_phrase(phrase):
                raise ValueError("This phrase already exists. Undo would overwrite newer data.")
            word_values = {
                "id": snapshot.word.id, "phrase": phrase, "created_at": snapshot.word.created_at,
            }
            records = (
                (ORMWord, [word_values]),
                (ORMTranslation, [asdict(row) for row in snapshot.translations]),
                (ORMWordStats, [asdict(row) for row in snapshot.stats]),
                (ORMHistory, [asdict(row) for row in snapshot.history]),
                (WordPause, [asdict(row) for row in snapshot.pauses]),
            )
            for model, rows in records:
                for values in rows:
                    pk = values["word_id"] if model is WordPause else values["id"]
                    if session.get(model, pk) is not None:
                        raise ValueError("New data uses a deleted record's ID. Undo cannot safely restore it.")
                    session.add(model(**values))
                session.flush()
            self.commit()
            session.expire_all()
        except Exception:
            session.rollback()
            raise

    def get_export_rows(self, target_lang: str | None = None) -> list[Word]:
        """One row per translation, retaining words without any translation."""
        rows = self.db.session.query(ORMWord).populate_existing().options(
            joinedload(ORMWord.translations).joinedload(ORMTranslation.language)
        ).order_by(func.casefold(ORMWord.phrase), ORMWord.id).all()
        result = []
        for row in rows:
            translations = sorted(row.translations, key=lambda item: item.language.code)
            if target_lang:
                translations = [item for item in translations if item.language.code == target_lang]
            for translation in translations:
                word = mappers.map_word(row)
                word.translation = translation.translation
                word.language_code = translation.language.code
                result.append(word)
            if not translations:
                result.append(mappers.map_word(row))
        return result

    def add(self, phrase: str) -> Word:
        """Add a word, return its domain entity."""
        orm_word = self.db.session.query(ORMWord).filter(func.casefold(ORMWord.phrase) == phrase.casefold()).first()
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
            .populate_existing()
            .filter(func.casefold(ORMWord.phrase) == phrase.casefold())
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
        sort: str = "phrase",
        descending: bool = False,
        untranslated: bool = False,
        hidden_only: bool = False,
    ) -> list[Word]:
        """Get all words with stats."""
        lang = None
        if target_lang:
            lang = self._get_language(target_lang)
            if not lang:
                return []

        query = self.db.session.query(ORMWord).populate_existing().options(joinedload(ORMWord.stats))
        if hidden_only:
            query = query.filter(self.db.session.query(WordPause.word_id).filter(
                WordPause.word_id == ORMWord.id, WordPause.until > utc_now_ts()
            ).exists())

        if lang:
            join = query.outerjoin if untranslated else query.join
            query = join(
                ORMTranslation,
                (ORMTranslation.word_id == ORMWord.id) & (ORMTranslation.language_id == lang.id),
            ).options(
                contains_eager(ORMWord.translations).joinedload(ORMTranslation.language)
            )
            if untranslated:
                query = query.filter(ORMTranslation.id.is_(None))
        else:
            query = query.options(
                joinedload(ORMWord.translations).joinedload(ORMTranslation.language)
            )

        if search:
            search_term = "%" + search.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            if lang:
                query = query.filter(
                    (func.casefold(ORMWord.phrase).like(search_term, escape="\\"))
                    | (func.casefold(ORMTranslation.translation).like(search_term, escape="\\"))
                )
            else:
                query = query.filter(func.casefold(ORMWord.phrase).like(search_term, escape="\\"))

        if since is not None:
            query = query.filter(ORMWord.created_at >= since)

        sort_column = {
            "phrase": func.casefold(ORMWord.phrase),
            "translation": func.casefold(ORMTranslation.translation) if lang else func.casefold(ORMWord.phrase),
            "last_reviewed": ORMWordStats.last_reviewed,
            "created_at": ORMWord.created_at,
        }.get(sort, func.casefold(ORMWord.phrase))
        if sort == "last_reviewed":
            query = query.outerjoin(ORMWordStats)
        query = query.order_by(sort_column.desc() if descending else sort_column.asc(), ORMWord.id)
        if limit is not None:
            query = query.limit(limit).offset(offset)
        orm_words = query.all()
        pauses = dict(self.db.session.query(WordPause.word_id, WordPause.until).filter(
            WordPause.word_id.in_([word.id for word in orm_words])
        ).all()) if orm_words else {}
        words = [mappers.map_word_with_details(w) for w in orm_words]
        for word in words:
            word.hidden_until = pauses.get(word.id)
        return words

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
            .populate_existing()
            .outerjoin(ORMWordStats)
            .outerjoin(review_counts, review_counts.c.word_id == ORMWord.id)
            .options(joinedload(ORMWord.stats))
            .filter(~self.db.session.query(WordPause.word_id).filter(
                WordPause.word_id == ORMWord.id, WordPause.until > now
            ).exists())
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

        first_history = aliased(ORMHistory)
        first_id = self.db.session.query(func.min(first_history.id)).filter(
            first_history.word_id == ORMHistory.word_id
        ).correlate(ORMHistory).scalar_subquery()
        recent = self.db.session.query(ORMHistory.id, first_id.label("first_id"))
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
            # A NOT EXISTS lookup avoids grouping the entire history a second time.
            new_query = self.db.session.query(ORMWord).populate_existing().outerjoin(ORMWordStats).filter(
                ORMWordStats.last_reviewed.is_(None),
                ~self.db.session.query(ORMHistory.id).filter(ORMHistory.word_id == ORMWord.id).exists(),
                ~self.db.session.query(WordPause.word_id).filter(
                    WordPause.word_id == ORMWord.id, WordPause.until > now
                ).exists(),
            ).options(joinedload(ORMWord.stats))
            if target_lang:
                new_query = new_query.join(ORMTranslation).join(ORMTranslation.language).filter(
                    ORMLanguage.code == target_lang
                ).options(contains_eager(ORMWord.translations).contains_eager(ORMTranslation.language))
            else:
                new_query = new_query.options(joinedload(ORMWord.translations).joinedload(ORMTranslation.language))
            new_words = new_query.order_by(ORMWord.created_at, ORMWord.id).limit(1).all()
        orm_words = (new_words + due_words)[:limit]
        return [mappers.map_word_with_details(w) for w in orm_words]

    def delete(self, phrase: str) -> None:
        """Delete a word."""
        word = self.db.session.query(ORMWord).filter(func.casefold(ORMWord.phrase) == phrase.casefold()).first()
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

    def update_word(
        self, word_id: int, phrase: str, translation: str | None = None, target_lang: str = DEFAULT_TARGET_LANG
    ) -> None:
        """Validate first, then atomically save phrase and selected translation."""
        duplicate = self.db.session.query(ORMWord.id).filter(
            func.casefold(ORMWord.phrase) == phrase.casefold(), ORMWord.id != word_id
        ).first()
        if duplicate:
            raise ValueError("This phrase already exists. Edit the existing entry instead.")
        lang = self._get_language(target_lang) if translation is not None else None
        if translation is not None and lang is None:
            raise ValueError("Unknown translation language")
        orm_word = self.db.session.query(ORMWord).filter_by(id=word_id).first()
        if orm_word:
            orm_word.phrase = phrase
            if translation is not None:
                existing = self.db.session.query(ORMTranslation).filter_by(
                    word_id=word_id, language_id=lang.id
                ).first()
                if translation.strip():
                    if existing:
                        existing.translation = translation.strip()
                    else:
                        self.db.session.add(ORMTranslation(
                            word_id=word_id, language_id=lang.id, translation=translation.strip()
                        ))
                elif existing:
                    self.db.session.delete(existing)
            self.commit()

    def snooze_word(self, word_id: int, until: int) -> None:
        pause = self.db.session.get(WordPause, word_id)
        if pause:
            pause.until = until
        else:
            self.db.session.add(WordPause(word_id=word_id, until=until))
        self.commit()

    def next_available_at(self, target_lang: str) -> int | None:
        """Earliest eligibility, including snoozed words; independent of cadence."""
        counts = self.db.session.query(
            ORMHistory.word_id, func.count(ORMHistory.id).label("count"),
            func.max(ORMHistory.reviewed_at).label("last"),
        ).group_by(ORMHistory.word_id).subquery()
        count = func.coalesce(counts.c.count, 0)
        interval = case(
            *((count <= i, seconds) for i, seconds in enumerate(EXPOSURE_INTERVALS, 1)),
            else_=EXPOSURE_INTERVALS[-1],
        )
        last = func.coalesce(counts.c.last, ORMWordStats.last_reviewed)
        eligible = func.max(func.coalesce(last + interval, 0), func.coalesce(WordPause.until, 0))
        return self.db.session.query(func.min(eligible)).select_from(ORMWord).join(
            ORMTranslation, ORMTranslation.word_id == ORMWord.id
        ).join(ORMLanguage, ORMLanguage.id == ORMTranslation.language_id).outerjoin(
            counts, counts.c.word_id == ORMWord.id
        ).outerjoin(ORMWordStats).outerjoin(WordPause).filter(ORMLanguage.code == target_lang).scalar()

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
