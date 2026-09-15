"""Shared setting keys and defaults; no persistence or platform dependencies."""

# Setting keys (single source of truth — use instead of string literals).
REVIEW_INTERVAL_KEY = "review_interval"
SOURCE_LANG_KEY = "source_lang"
TARGET_LANG_KEY = "target_lang"
TRANSLATION_PROVIDER_KEY = "translation_provider"
WOTD_ENABLED_KEY = "wotd_enabled"
WOTD_LEVEL_KEY = "wotd_level"
DATA_DIR_KEY = "data_dir"
GNOME_TRAY_WARNING_KEY = "gnome_tray_warning_shown"

# Default setting values.
DEFAULT_REVIEW_INTERVAL = "3600"
DEFAULT_SOURCE_LANG = "en"
DEFAULT_TARGET_LANG = "ru"
DEFAULT_TRANSLATION_PROVIDER = "mymemory"
DEFAULT_WOTD_ENABLED = "false"
DEFAULT_WOTD_LEVEL = "B2"


DEFAULT_SETTINGS = {
    REVIEW_INTERVAL_KEY: DEFAULT_REVIEW_INTERVAL,
    SOURCE_LANG_KEY: DEFAULT_SOURCE_LANG,
    TARGET_LANG_KEY: DEFAULT_TARGET_LANG,
    TRANSLATION_PROVIDER_KEY: DEFAULT_TRANSLATION_PROVIDER,
    GNOME_TRAY_WARNING_KEY: "false",
}
