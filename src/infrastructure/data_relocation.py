"""Filesystem mechanics for changing the vocabulary location, independent of GTK."""

import os
import sqlite3
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from config import DATA_DIR_KEY
from constants import DEFAULT_DB_PATH
from infrastructure.config_file import read_config, write_config
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
    SCHEDULED = auto()


PENDING_RELOCATION_KEY = "pending_data_relocation"


@dataclass(frozen=True)
class RelocationResult:
    """Result of a database relocation: verdict plus error details on failure."""

    verdict: RelocationVerdict
    error: str = ""


def relocate_database(
    config_file: str | None, new_data_dir: str, choose: Callable[[], DataDirChoice]
) -> RelocationResult:
    """Schedule a copy at GUI startup; never move an open database."""
    old_db_path = get_db_path(config_file) if config_file else DEFAULT_DB_PATH
    new_db_path = (
        os.path.join(os.path.expanduser(new_data_dir), "vocab.db")
        if new_data_dir.strip()
        else DEFAULT_DB_PATH
    )
    if os.path.abspath(old_db_path) == os.path.abspath(new_db_path):
        return RelocationResult(RelocationVerdict.NOTHING_TO_DO)
    choice = choose()
    if choice is DataDirChoice.CANCEL:
        return RelocationResult(RelocationVerdict.CANCELLED)
    try:
        if os.path.exists(new_db_path):
            return RelocationResult(
                RelocationVerdict.FAILED,
                "A database already exists at the new location:\n"
                f"{new_db_path}\nMove cancelled — nothing was changed.",
            )
        if not config_file:
            raise OSError("A config file is required to schedule the change")
        config = read_config(config_file)
        config[PENDING_RELOCATION_KEY] = {
            "data_dir": new_data_dir, "source": os.path.abspath(old_db_path),
            "copy": choice is DataDirChoice.MOVE,
        }
        if not write_config(config_file, config):
            raise OSError("Could not save the pending directory change")
        return RelocationResult(RelocationVerdict.SCHEDULED)
    except OSError as e:
        return RelocationResult(
            RelocationVerdict.FAILED,
            f"Could not move the database:\n{old_db_path}\n→ {new_db_path}\n{e}",
        )


def apply_pending_relocation(config_file: str) -> None:
    """Apply a scheduled change before the single-instance GUI opens its DB.

    SQLite backup includes committed WAL data. The original remains intact.
    CLI processes never apply pending changes themselves.
    """
    config = read_config(config_file)
    pending = config.get(PENDING_RELOCATION_KEY)
    if not pending:
        return
    directory = pending["data_dir"]
    target = os.path.join(os.path.expanduser(directory), "vocab.db") if directory else DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    # Exclusive creation prevents accidental overwrite, even after scheduling.
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with sqlite3.connect(target) as destination:
            if pending["copy"]:
                from pathlib import Path
                with sqlite3.connect(Path(pending["source"]).as_uri() + "?mode=ro", uri=True) as source:
                    source.backup(destination)
            if destination.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise OSError("The copied database failed its integrity check")
        config[DATA_DIR_KEY] = directory
        del config[PENDING_RELOCATION_KEY]
        if not write_config(config_file, config):
            raise OSError("Could not activate the new data directory; the original remains active")
    except Exception:
        os.unlink(target)
        raise
