"""Domain models - SQLAlchemy ORM classes."""

from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

from domain.time_utils import utc_now_ts as _utc_timestamp

Base = declarative_base()


class Language(Base):
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    abbreviation = Column(String, nullable=False)

    translations = relationship("Translation", back_populates="language")


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phrase = Column(String, unique=True, nullable=False)
    created_at = Column(Integer, nullable=False, default=_utc_timestamp)

    translations = relationship("Translation", back_populates="word", cascade="all, delete-orphan")
    stats = relationship(
        "WordStats", back_populates="word", uselist=False, cascade="all, delete-orphan"
    )
    history = relationship("History", back_populates="word", cascade="all, delete-orphan")


class Translation(Base):
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    translation = Column(String, nullable=False)
    language_id = Column(Integer, ForeignKey("languages.id"), nullable=False)
    created_at = Column(Integer, nullable=False, default=_utc_timestamp)

    word = relationship("Word", back_populates="translations")
    language = relationship("Language", back_populates="translations")

    __table_args__ = (
        UniqueConstraint("word_id", "language_id", name="_word_lang_uc"),
        Index("idx_translation_word_id", "word_id"),
        Index("idx_translation_language_id", "language_id"),
        Index("idx_translation_word_lang", "word_id", "language_id"),
    )


class WordPause(Base):
    __tablename__ = "word_pauses"
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), primary_key=True)
    until = Column(Integer, nullable=False)


class WordStats(Base):
    __tablename__ = "word_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(
        Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    last_reviewed = Column(Integer, nullable=True)

    word = relationship("Word", back_populates="stats")

    __table_args__ = (
        Index("idx_word_stats_last_reviewed", "last_reviewed"),
    )


class History(Base):
    __tablename__ = "history"
    __table_args__ = (
        Index("idx_history_reviewed_at", "reviewed_at"),
        Index("idx_history_word_id", "word_id"),
        Index("idx_history_word_time", "word_id", "reviewed_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    reviewed_at = Column(Integer, nullable=False, default=_utc_timestamp)

    word = relationship("Word", back_populates="history")


class WOTDHistory(Base):
    __tablename__ = "wotd_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String, nullable=False)
    level = Column(String, nullable=False)
    # One entry per day: UniqueConstraint makes concurrent mark_shown()
    # calls idempotent instead of inserting duplicates.
    shown_date = Column(String, nullable=False, unique=True)  # YYYY-MM-DD format
    created_at = Column(Integer, nullable=False, default=_utc_timestamp)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
