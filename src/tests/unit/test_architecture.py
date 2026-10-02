"""Enforce dependency direction across every core module."""

import ast
import sys
from importlib.util import resolve_name
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
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                package = ".".join(path.relative_to(SRC).parent.parts)
                module = resolve_name("." * node.level + module, package)
            modules = [module]
        else:
            continue
        for module in modules:
            assert module.split(".")[0] in allowed, f"{path.name} depends on outer module {module}"


@pytest.mark.parametrize("path", sorted((SRC / "windows").glob("*.py")), ids=lambda p: p.name)
def test_windows_do_not_access_persistence_or_translation_adapters(path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("repositories", "infrastructure.models", "sqlalchemy"))
        elif isinstance(node, ast.Import):
            assert all(not alias.name.startswith(("repositories", "sqlalchemy")) for alias in node.names)
        elif isinstance(node, ast.Attribute):
            assert node.attr not in {"word_repo", "translation_service", "session", "_db"}


def test_services_share_settings_and_accept_alternate_adapters(vocab_service):
    service = vocab_service
    settings = service.settings_service
    assert service.word_service.settings_service is settings
    assert service.review_service.settings_service is settings
    assert service.wotd_service.settings_service is settings
    assert service.export_service.settings_service is settings
    service.settings_service.set_setting("target_lang", "es")
    assert service.word_service.settings_service.get_settings()["target_lang"] == "es"


def test_bootstrap_initializes_database_for_both_entry_points(tmp_path):
    from bootstrap import create_vocab_service

    service = create_vocab_service(db_path=str(tmp_path / "vocab.db"))
    try:
        assert service.get_languages()
        assert service.settings_service.get_setting("review_interval") == "3600"
        settings = service.settings_service
        assert all(component.settings_service is settings for component in (
            service.word_service, service.review_service, service.wotd_service, service.export_service,
        ))
        assert service.notification_service._review is service.review_service
        assert service.notification_service._word is service.word_service
    finally:
        service.close()
