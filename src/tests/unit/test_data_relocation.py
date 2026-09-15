"""Filesystem relocation is testable without GTK."""

from unittest.mock import Mock

from infrastructure.data_relocation import DataDirChoice, RelocationVerdict, relocate_database


def test_cancel_keeps_existing_database(tmp_path, monkeypatch):
    source = tmp_path / "vocab.db"
    source.write_bytes(b"vocabulary")
    monkeypatch.setattr("infrastructure.data_relocation.DEFAULT_DB_PATH", str(source))
    result = relocate_database(None, str(tmp_path / "new"), lambda: DataDirChoice.CANCEL)
    assert result.verdict is RelocationVerdict.CANCELLED
    assert source.read_bytes() == b"vocabulary"
    assert not (tmp_path / "new").exists()


def test_relocation_does_not_overwrite_existing_database(tmp_path, monkeypatch):
    source = tmp_path / "vocab.db"
    source.write_bytes(b"original")
    target_dir = tmp_path / "new"
    target_dir.mkdir()
    target = target_dir / "vocab.db"
    target.write_bytes(b"other vocabulary")
    monkeypatch.setattr("infrastructure.data_relocation.DEFAULT_DB_PATH", str(source))
    result = relocate_database(None, str(target_dir), lambda: DataDirChoice.MOVE)
    assert result.verdict is RelocationVerdict.FAILED
    assert source.read_bytes() == b"original"
    assert target.read_bytes() == b"other vocabulary"


def test_unchanged_location_does_not_ask_for_choice(tmp_path, monkeypatch):
    monkeypatch.setattr("infrastructure.data_relocation.DEFAULT_DB_PATH", str(tmp_path / "vocab.db"))
    choose = Mock()
    result = relocate_database(None, str(tmp_path), choose)
    assert result.verdict is RelocationVerdict.NOTHING_TO_DO
    choose.assert_not_called()
