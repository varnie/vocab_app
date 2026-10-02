#!/usr/bin/env python3
"""Application constants."""

import os
import sys

# App info
APP_NAME = "vocab_app"

# Platform detection
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Default data directory
if IS_MACOS:
    DEFAULT_DATA_DIR = os.path.expanduser("~/Library/Application Support/vocab_app")
    CONFIG_DIR = os.path.expanduser("~/Library/Application Support/vocab_app")
    AUTOSTART_DIR = os.path.expanduser("~/Library/LaunchAgents")
    AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "com.vocab_app.plist")
else:
    DEFAULT_DATA_DIR = os.path.expanduser("~/.local/share/vocab_app")
    CONFIG_DIR = os.path.expanduser("~/.config/vocab_app")
    AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
    AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, f"{APP_NAME}.desktop")

# Config file
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings")

# Database
DEFAULT_DB_PATH = os.path.join(DEFAULT_DATA_DIR, "vocab.db")

# Runtime state
# Prefer the OS-provided, per-user runtime directory.  The state-directory
# fallback is private to the current user and remains available on platforms
# without XDG_RUNTIME_DIR (including macOS).
RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR")
STATE_DIR = (
    os.path.join(RUNTIME_DIR, APP_NAME)
    if RUNTIME_DIR
    else os.path.expanduser(f"~/.local/state/{APP_NAME}")
)
CURRENT_PHRASE_FILE = os.path.join(STATE_DIR, "current_phrase.json")

# Icon directory
ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

# Tray menu items: (label, callback_key) or None for separator
MENU_ITEMS = [
    ("Show next word", "show_next"),
    ("Pause", "pause"),
    None,
    ("Add word", "add_word"),
    ("Words added today", "words_today"),
    ("Word Browser", "word_browser"),
    ("Stats", "stats"),
    ("Settings", "settings"),
    None,
    ("Quit", "quit"),
]
