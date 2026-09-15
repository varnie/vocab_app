"""Tests for private, short-lived current-phrase state."""

import json
import os
from pathlib import Path

import pytest

from infrastructure import current_phrase


@pytest.fixture
def phrase_state_dir(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(current_phrase, "STATE_DIR", str(state_dir))
    monkeypatch.setattr(current_phrase, "CURRENT_PHRASE_FILE", str(state_dir / "current_phrase.json"))
    return state_dir


def test_write_and_read_current_phrase_are_private_and_atomic(phrase_state_dir):
    current_phrase.write_current_phrase("Hello world")

    state_file = phrase_state_dir / "current_phrase.json"
    assert current_phrase.read_current_phrase() == "Hello world"
    assert stat_mode(phrase_state_dir) == 0o700
    assert stat_mode(state_file) == 0o600
    assert json.loads(state_file.read_text(encoding="utf-8"))["phrase"] == "Hello world"


def test_read_current_phrase_discards_expired_state(phrase_state_dir, monkeypatch):
    current_phrase.write_current_phrase("expired")
    monkeypatch.setattr(
        current_phrase,
        "CURRENT_PHRASE_MAX_AGE_SECONDS",
        0,
    )

    assert current_phrase.read_current_phrase() is None
    assert not (phrase_state_dir / "current_phrase.json").exists()


def test_read_current_phrase_rejects_symlink(phrase_state_dir, tmp_path):
    phrase_state_dir.mkdir(mode=0o700)
    target = tmp_path / "target"
    target.write_text('{"phrase": "unsafe"}', encoding="utf-8")
    (phrase_state_dir / "current_phrase.json").symlink_to(target)

    assert current_phrase.read_current_phrase() is None


def stat_mode(path: Path) -> int:
    return os.stat(path).st_mode & 0o777
