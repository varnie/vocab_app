"""Infrastructure - Platform-specific notification service."""

import logging
import os
import re
import shutil
import subprocess

from constants import IS_MACOS

logger = logging.getLogger(__name__)

ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "translate.svg")


def _escape_applescript_string(value: str) -> str:
    """Escape untrusted text for use inside an AppleScript string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n")


def send_notification(body: str, title: str = "") -> bool:
    """Send system notification.

    Args:
        body: Notification body text
        title: Notification title

    Returns:
        True if notification was sent successfully
    """
    if IS_MACOS:
        return _send_macos_notification(body, title)
    else:
        return _send_linux_notification(body, title)


def _send_macos_notification(body: str, title: str) -> bool:
    """Send notification on macOS."""
    clean_body = re.sub(r"<[^>]+>", "", body)
    clean_title = re.sub(r"<[^>]+>", "", title)

    terminal_notifier = shutil.which("terminal-notifier")
    if terminal_notifier:
        result = subprocess.run(  # ruff:ignore[subprocess-without-shell-equals-true]
            [terminal_notifier, "-title", clean_title, "-message", clean_body],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0

    # Fallback to osascript
    osascript = shutil.which("osascript")
    if osascript:
        script = (
            f'display notification "{_escape_applescript_string(clean_body)}" '
            f'with title "{_escape_applescript_string(clean_title)}"'
        )
        result = subprocess.run([osascript, "-e", script], check=False)  # ruff:ignore[subprocess-without-shell-equals-true]
        return result.returncode == 0

    logger.warning("No notification tools available (terminal-notifier or osascript)")
    return False


def _send_linux_notification(body: str, title: str) -> bool:
    """Send notification on Linux."""
    notify_send = shutil.which("notify-send")
    if not notify_send:
        logger.warning("notify-send not found")
        return False

    args = [notify_send, "-u", "low", title, body]

    if os.path.exists(ICON_PATH):
        args[1:1] = ["-i", ICON_PATH]

    result = subprocess.run(args, check=False)  # ruff:ignore[subprocess-without-shell-equals-true]
    return result.returncode == 0
