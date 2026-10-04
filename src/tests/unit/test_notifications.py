"""Notification command deadlines and literal vocabulary text."""

import subprocess  # ruff: ignore[suspicious-subprocess-import] - mocked notification commands
from unittest.mock import Mock

import pytest

from application.notification_service import format_word_body
from infrastructure import notifications


@pytest.mark.parametrize("backend", ["linux", "terminal-notifier", "osascript"])
@pytest.mark.parametrize("failure", [False, True])
def test_notification_commands_are_bounded_and_preserve_text(monkeypatch, backend, failure):
    monkeypatch.setattr(notifications, "IS_MACOS", backend != "linux")
    monkeypatch.setattr(notifications.shutil, "which", lambda name: (
        "/usr/bin/" + name if name == ("notify-send" if backend == "linux" else backend) else None
    ))
    run = Mock(return_value=subprocess.CompletedProcess([], 0))
    if failure:
        run.side_effect = subprocess.TimeoutExpired("notification", 5)
    monkeypatch.setattr(notifications.subprocess, "run", run)
    body = format_word_body('<hello> & "hi"', "a < b & c > d", "EN")
    assert notifications.send_notification(body, "<title>") is not failure
    assert run.call_args.kwargs["timeout"] == 5
    args = run.call_args.args[0]
    if backend == "linux":
        assert args[-1] == '<b>&lt;hello&gt; &amp; &quot;hi&quot;</b>\n→ a &lt; b &amp; c &gt; d [EN]'
    elif backend == "terminal-notifier":
        assert args[-1] == '<hello> & "hi"\n→ a < b & c > d [EN]'
        assert args[2] == "<title>"
    else:
        assert '<hello> & \\"hi\\"' in args[-1]
        assert "a < b & c > d" in args[-1]
