"""Runtime commit hash and Python package version for the current checkout."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def get_version() -> str:
    """Return the short commit hash, or 'unknown' when Git is unavailable."""
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short=7", "HEAD"],  # ruff: ignore[start-process-with-partial-path] - optional Git from PATH
            capture_output=True,
            text=True,
            check=True,
            timeout=1,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


# Package metadata requires a PEP 440 version; GUI/CLI use get_version().
_commit = get_version()
__version__ = f"0+g{_commit}" if _commit != "unknown" else "0+unknown"
