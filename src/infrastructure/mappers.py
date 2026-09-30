"""Mappers for converting between ORM models and domain entities."""

from domain.entities import (
    History,
    Language,
    Setting,
    Translation,
    Word,
    WordStats,
    WOTDHistory,
)
from infrastructure.models import (
    History as ORMHistory,
)
from infrastructure.models import (
    Language as ORMLanguage,
)
from infrastructure.models import Setting as ORMSetting
from infrastructure.models import (
    Translation as ORMTranslation,
)
from infrastructure.models import (
    Word as ORMWord,
)
from infrastructure.models import (
    WordStats as ORMWordStats,
)
from infrastructure.models import (
    WOTDHistory as ORMWOTDHistory,
)


def map_word(orm: ORMWord) -> Word:
    """Map ORM Word to domain entity."""
    return Word(
        id=orm.id,
        phrase=orm.phrase,
        created_at=orm.created_at,
    )


def map_word_with_details(orm: ORMWord) -> Word:
    """Map ORM Word to domain entity with translation and stats."""
    word = Word(
        id=orm.id,
        phrase=orm.phrase,
        created_at=orm.created_at,
    )

    if orm.translations:
        word.translation = orm.translations[0].translation
        word.language_code = (
            orm.translations[0].language.code if orm.translations[0].language else ""
        )

    if orm.stats:
        word.last_reviewed = orm.stats.last_reviewed

    return word


def map_translation(orm: ORMTranslation) -> Translation:
    """Map ORM Translation to domain entity."""
    return Translation(
        id=orm.id,
        word_id=orm.word_id,
        translation=orm.translation,
        language_id=orm.language_id,
        created_at=orm.created_at,
    )


def map_language(orm: ORMLanguage) -> Language:
    """Map ORM Language to domain entity."""
    return Language(
        id=orm.id,
        code=orm.code,
        name=orm.name,
        abbreviation=orm.abbreviation,
    )


def map_word_stats(orm: ORMWordStats) -> WordStats:
    """Map ORM WordStats to domain entity."""
    return WordStats(
        id=orm.id,
        word_id=orm.word_id,
        last_reviewed=orm.last_reviewed,
    )


def map_history(orm: ORMHistory) -> History:
    """Map ORM History to domain entity."""
    return History(
        id=orm.id,
        word_id=orm.word_id,
        reviewed_at=orm.reviewed_at,
    )


def map_wotd_history(orm: ORMWOTDHistory) -> WOTDHistory:
    """Map ORM WOTDHistory to domain entity."""
    return WOTDHistory(
        id=orm.id,
        word=orm.word,
        level=orm.level,
        shown_date=orm.shown_date,
        created_at=orm.created_at,
    )


def map_setting(orm: ORMSetting) -> Setting:
    """Map ORM Setting to domain entity."""
    return Setting(
        key=orm.key,
        value=orm.value,
    )
