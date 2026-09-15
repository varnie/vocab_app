"""Filesystem mechanics for changing the vocabulary location, independent of GTK."""

import os
import shutil
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from constants import DEFAULT_DB_PATH
from infrastructure.data_paths import get_db_path


class DataDirChoice(Enum):
    """User decision on what to do with the existing vocabulary."""

    MOVE = auto()
    START_EMPTY = auto()
    CANCEL = auto()


class RelocationVerdict(Enum):
    """Outcome of a database relocation attempt."""

    NOTHING_TO_DO = auto()
    MOVED = auto()
    START_EMPTY = auto()
    CANCELLED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class RelocationResult:
    """Result of a database relocation: verdict plus error details on failure."""

    verdict: RelocationVerdict
    error: str = ""


def relocate_database(
    config_file: str | None, new_data_dir: str, choose: Callable[[], DataDirChoice]
) -> RelocationResult:
    """Move the active DB file to the new data dir, or confirm a fresh start."""
    old_db_path = get_db_path(config_file) if config_file else DEFAULT_DB_PATH
    new_db_path = (
        os.path.join(os.path.expanduser(new_data_dir), "vocab.db")
        if new_data_dir.strip()
        else DEFAULT_DB_PATH
    )
    if os.path.abspath(old_db_path) == os.path.abspath(new_db_path):
        return RelocationResult(RelocationVerdict.NOTHING_TO_DO)
    if not os.path.exists(old_db_path):
        # No existing vocabulary; a fresh DB is created on restart.
        return RelocationResult(RelocationVerdict.NOTHING_TO_DO)

    choice = choose()
    if choice is DataDirChoice.CANCEL:
        return RelocationResult(RelocationVerdict.CANCELLED)
    if choice is DataDirChoice.START_EMPTY:
        return RelocationResult(RelocationVerdict.START_EMPTY)
    try:
        target_dir = os.path.dirname(new_db_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        if os.path.exists(new_db_path):
            return RelocationResult(
                RelocationVerdict.FAILED,
                "A database already exists at the new location:\n"
                f"{new_db_path}\nMove cancelled — nothing was changed.",
            )
        shutil.move(old_db_path, new_db_path)
        return RelocationResult(RelocationVerdict.MOVED)
    except OSError as e:
        return RelocationResult(
            RelocationVerdict.FAILED,
            f"Could not move the database:\n{old_db_path}\n→ {new_db_path}\n{e}",
        )
