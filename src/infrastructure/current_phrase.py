"""Private, short-lived state shared by the GUI and hotkey CLI."""

import json
import os
import stat
import tempfile
import time
from contextlib import suppress

from constants import CURRENT_PHRASE_FILE, STATE_DIR

# A phrase is only meaningful while it is recent enough to plausibly be the
# notification the user is acting on.  This prevents a later app instance from
# deleting a stale phrase left by an earlier session.
CURRENT_PHRASE_MAX_AGE_SECONDS = 12 * 60 * 60


def _ensure_state_dir() -> None:
    """Create the user-private state directory with restrictive permissions."""
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)


def _is_expired(written_at: object) -> bool:
    return not isinstance(written_at, (int, float)) or time.time() - written_at > (
        CURRENT_PHRASE_MAX_AGE_SECONDS
    )


def write_current_phrase(phrase: str) -> None:
    """Atomically write current-phrase state with owner-only permissions."""
    _ensure_state_dir()
    payload = json.dumps({"phrase": phrase, "written_at": time.time()})
    fd, temp_path = tempfile.mkstemp(prefix=".current_phrase-", dir=STATE_DIR, text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as state_file:
            state_file.write(payload)
            state_file.flush()
            os.fsync(state_file.fileno())
        os.replace(temp_path, CURRENT_PHRASE_FILE)
    except Exception:
        with suppress(OSError):
            os.close(fd)
        with suppress(FileNotFoundError):
            os.unlink(temp_path)
        raise


def read_current_phrase() -> str | None:
    """Read a recent current phrase, rejecting unsafe or malformed state."""
    try:
        fd = os.open(CURRENT_PHRASE_FILE, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError:
        return None

    try:
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != os.getuid():
            os.close(fd)
            return None
        with os.fdopen(fd, encoding="utf-8") as state_file:
            payload = json.load(state_file)
        if not isinstance(payload, dict) or _is_expired(payload.get("written_at")):
            clear_current_phrase()
            return None
        phrase = payload.get("phrase")
        return phrase.strip() if isinstance(phrase, str) and phrase.strip() else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def clear_current_phrase() -> None:
    """Remove the private current-phrase state file if it exists."""
    with suppress(FileNotFoundError):
        os.unlink(CURRENT_PHRASE_FILE)
