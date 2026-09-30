"""Domain entities - pure Python dataclasses, no framework dependencies."""

from dataclasses import dataclass


@dataclass
class Word:
    """Domain entity for a vocabulary word."""

    id: int = 0
    phrase: str = ""
    created_at: int = 0
    translation: str = ""
    language_code: str = ""
    last_reviewed: int | None = None
    hidden_until: int | None = None


@dataclass
class Translation:
    """Domain entity for a translation."""

    id: int = 0
    word_id: int = 0
    translation: str = ""
    language_id: int = 0
    created_at: int = 0


@dataclass
class Language:
    """Domain entity for a language."""

    id: int = 0
    code: str = ""
    name: str = ""
    abbreviation: str = ""


@dataclass
class WordStats:
    """Domain entity for word learning statistics."""

    id: int = 0
    word_id: int = 0
    last_reviewed: int | None = None


@dataclass
class History:
    """Domain entity for review history."""

    id: int = 0
    word_id: int = 0
    reviewed_at: int = 0


@dataclass
class WordPause:
    """A word hidden until a Unix timestamp."""

    word_id: int
    until: int


@dataclass
class WordSnapshot:
    """Complete vocabulary entry retained for undo, independent of storage tables."""

    word: Word
    translations: tuple[Translation, ...]
    stats: tuple[WordStats, ...]
    history: tuple[History, ...]
    pauses: tuple[WordPause, ...]


@dataclass
class WOTDHistory:
    """Domain entity for Word of the Day history."""

    id: int = 0
    word: str = ""
    level: str = ""
    shown_date: str = ""
    created_at: int = 0


@dataclass
class Setting:
    """Domain entity for application settings."""

    key: str = ""
    value: str = ""


@dataclass
class Stats:
    """Domain entity for overall statistics."""

    total_words: int = 0
    today_words: int = 0
    today_reviews: int = 0
    total_reviews: int = 0
    streak: int = 0
