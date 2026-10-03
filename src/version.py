"""Application version is the short HEAD commit hash, nothing else."""

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
