"""Version is the bare short commit hash."""

import re
import subprocess  # ruff: ignore[suspicious-subprocess-import] - isolated Git fixtures

import pytest

import version


def git(root, *args):
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed executable, temporary repository
        ["git", "-C", str(root), *args],  # ruff: ignore[start-process-with-partial-path] - Git from PATH
        capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "file").write_text("data")
    git(tmp_path, "add", "file")
    git(tmp_path, "-c", "user.name=Version test", "-c", "user.email=test@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-qm", "init")
    return tmp_path


def test_returns_bare_short_hash(repo, monkeypatch):
    monkeypatch.setattr(version, "REPO_ROOT", repo)
    result = version.get_version()
    assert result == git(repo, "rev-parse", "--short=7", "HEAD")
    assert re.fullmatch(r"[0-9a-f]{7}", result)


def test_no_release_or_dirty_suffixes(repo, monkeypatch):
    """Output is just the hash even with local changes."""
    monkeypatch.setattr(version, "REPO_ROOT", repo)
    (repo / "untracked").write_text("local file")
    (repo / "file").write_text("modified")
    assert version.get_version() == git(repo, "rev-parse", "--short=7", "HEAD")


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("git", 1),
                                  subprocess.CalledProcessError(128, "git")])
def test_unavailable_git_returns_unknown(tmp_path, monkeypatch, error):
    monkeypatch.setattr(version, "REPO_ROOT", tmp_path)

    def fail(*args, **kwargs):
        assert kwargs["timeout"] == 1
        raise error

    monkeypatch.setattr(version.subprocess, "run", fail)
    assert version.get_version() == "unknown"
