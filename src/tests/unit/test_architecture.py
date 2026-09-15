"""Enforce dependency direction across every core module."""

import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2]
CORE_MODULES = [
    *sorted((SRC / "domain").rglob("*.py")),
    *sorted((SRC / "application").rglob("*.py")),
    SRC / "config.py",
]


@pytest.mark.parametrize("path", CORE_MODULES, ids=lambda path: str(path.relative_to(SRC)))
def test_core_imports_only_inner_layers_and_standard_library(path):
    allowed = set(sys.stdlib_module_names) | {"domain"}
    if "application" in path.relative_to(SRC).parts:
        allowed |= {"application", "config"}
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        else:
            continue
        for module in modules:
            assert module.split(".")[0] in allowed, f"{path.name} depends on outer module {module}"


def test_factory_shares_settings_and_accepts_alternate_adapters(vocab_service):
    service = vocab_service
    settings = service.settings_service
    assert service.word_service.settings_service is settings
    assert service.review_service.settings_service is settings
    assert service.wotd_service.settings_service is settings
    assert service.export_service.settings_service is settings
    service.set_setting("target_lang", "es")
    assert service.word_service.settings_service.get_settings()["target_lang"] == "es"


def test_bootstrap_initializes_database_for_both_entry_points(tmp_path):
    from bootstrap import create_vocab_service

    service = create_vocab_service(db_path=str(tmp_path / "vocab.db"))
    try:
        assert service.get_languages()
        assert service.get_setting("review_interval") == "3600"
    finally:
        service.close()
