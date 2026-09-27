"""Tests for translation provider fallback behavior."""

from unittest.mock import MagicMock, patch

import pytest


def _provider_returning(value, raise_exc=None):
    """Build a provider instance whose translate returns value or raises."""
    provider = MagicMock()
    if raise_exc is not None:
        provider.translate.side_effect = raise_exc
    else:
        provider.translate.return_value = value
    return provider


def test_fallback_to_working_provider():
    """When the selected provider fails, a working fallback is used."""
    from infrastructure.translation import TranslationServiceImpl

    failing = _provider_returning(None, raise_exc=RuntimeError("blocked"))
    working = _provider_returning("привет")

    with patch.object(
        TranslationServiceImpl, "FALLBACK_ORDER", ["google_direct", "mymemory"]
    ), patch(
        "infrastructure.translation.ProviderRegistry.get",
        side_effect=[failing, working],
    ):
        service = TranslationServiceImpl()
        result = service.translate("hello", provider_name="google_direct")

    assert result == "привет"


def test_all_providers_fail_raises():
    """If every provider fails, a TranslationError is raised."""
    from domain.exceptions import TranslationError
    from infrastructure.translation import TranslationServiceImpl

    failing = _provider_returning(None, raise_exc=RuntimeError("blocked"))

    with (
        patch.object(TranslationServiceImpl, "FALLBACK_ORDER", ["google_direct", "mymemory"]),
        patch("infrastructure.translation.ProviderRegistry.get", return_value=failing),
        pytest.raises(TranslationError),
    ):
        TranslationServiceImpl().translate("hello", provider_name="google_direct")


def test_mymemory_is_default_provider():
    """The default provider should be mymemory (Google direct is blocked)."""
    from infrastructure.translation import TranslationServiceImpl

    assert TranslationServiceImpl().translate.__defaults__[2] == "mymemory"


def test_unresponsive_worker_falls_back_without_unbounded_wait():
    from subprocess import CompletedProcess, TimeoutExpired  # ruff: ignore[suspicious-subprocess-import] - testing the bounded subprocess adapter

    from infrastructure.translation import TranslationServiceImpl

    with patch("infrastructure.translation.subprocess.run") as run:
        run.side_effect = [TimeoutExpired("worker", 15), CompletedProcess([], 0, '"translated"')]
        assert TranslationServiceImpl().translate("Text", provider_name="mymemory") == "translated"
        assert run.call_count == 2
        for call in run.call_args_list:
            assert call.kwargs["timeout"] == 15
            assert call.kwargs["input"]
            assert "Text" not in call.args[0]


def test_direct_provider_keeps_all_sentence_segments(monkeypatch, capsys):
    import io
    import json

    from infrastructure.translation_worker import main

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(["google_direct", "Two sentences.", "en", "ru"])))
    response = MagicMock()
    response.json.return_value = [[["First. ", "a"], ["Second.", "b"]]]
    with patch("requests.get", return_value=response) as get:
        main()
    assert json.loads(capsys.readouterr().out) == "First. Second."
    assert get.call_args.kwargs["timeout"] == (5, 10)
