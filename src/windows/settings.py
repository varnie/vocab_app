"""Settings window."""

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from application.service_interfaces import CEFR_LEVELS
from application.settings_service import parse_quiet_hours
from application.vocab_service import VocabService
from config import (
    DATA_DIR_KEY,
    DEFAULT_SETTINGS,
    DEFAULT_TRANSLATION_PROVIDER,
    DEFAULT_WOTD_LEVEL,
    QUIET_END_KEY,
    QUIET_START_KEY,
    REVIEW_INTERVAL_KEY,
    SOURCE_LANG_KEY,
    TARGET_LANG_KEY,
    TRANSLATION_PROVIDER_KEY,
    WOTD_ENABLED_KEY,
    WOTD_LEVEL_KEY,
)
from constants import DEFAULT_DATA_DIR, IS_MACOS
from infrastructure.autostart import AutostartManager
from infrastructure.config_file import read_config, write_config
from infrastructure.data_relocation import PENDING_RELOCATION_KEY, DataDirChoice, RelocationVerdict, relocate_database
from infrastructure.translation import ProviderRegistry
from version import get_version
from windows import BaseWindow, labelled_row, pack_button, padded_box


class SettingsWindow(BaseWindow):
    """Settings window."""

    def __init__(self, vocab_service: VocabService, config_file=None):
        super().__init__(title="Settings", width=650, height=720)
        self.vocab_service = vocab_service
        self.config_file = config_file

        self._test_completed = True

        self.build_ui()

    def build_ui(self) -> None:
        """Build the UI."""
        scroll = Gtk.ScrolledWindow()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(main_box)
        main_box.pack_start(scroll, True, True, 0)

        box = padded_box()
        scroll.add(box)

        box.pack_start(self._build_review_section(), False, False, 0)
        box.pack_start(self._build_translation_section(), False, False, 0)
        box.pack_start(self._build_shortcuts_section(), False, False, 0)
        box.pack_start(self._build_startup_section(), False, False, 0)
        box.pack_start(self._build_data_section(), False, False, 0)
        box.pack_start(self._build_wotd_section(), False, False, 0)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        pack_button(btn_box, "Cancel", lambda _: self.destroy(), expand=True)
        save_btn = pack_button(btn_box, "Save Settings", self.on_save_settings, expand=True)
        save_btn.get_style_context().add_class("suggested-action")

        footer = padded_box(spacing=8, margin=12)
        self.status_label = Gtk.Label(xalign=0)
        self.status_label.set_line_wrap(True)
        footer.pack_start(self.status_label, False, False, 0)
        footer.pack_start(btn_box, False, False, 0)
        main_box.pack_end(footer, False, False, 0)

        # Version footer
        footer_label = Gtk.Label(f"App version: {get_version()}")
        footer_label.set_xalign(0)
        footer_label.set_margin_top(10)
        footer_label.set_selectable(True)
        box.pack_start(footer_label, False, False, 0)

    def _fill_lang_combo(self, combo: Gtk.ComboBoxText, current_code: str) -> None:
        """Fill a language combo box and select the current language."""
        for lang in self.vocab_service.get_languages():
            combo.append(lang.code, lang.name)
        combo.set_active_id(current_code)

    def _build_review_section(self) -> Gtk.Frame:
        """Build the review interval section."""
        self.interval_combo = Gtk.ComboBoxText()
        intervals = [
            ("1800", "30 minutes"),
            ("3600", "1 hour"),
            ("7200", "2 hours"),
            ("14400", "4 hours"),
            ("28800", "8 hours"),
        ]
        for value, label in intervals:
            self.interval_combo.append(value, label)
        current_interval = str(
            self.vocab_service.settings_service.get_setting(REVIEW_INTERVAL_KEY, DEFAULT_SETTINGS[REVIEW_INTERVAL_KEY])
        )
        self.interval_combo.set_active_id(current_interval)
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        section.pack_start(labelled_row("Review Interval:", self.interval_combo), False, False, 0)
        quiet = Gtk.Box(spacing=10)
        quiet.pack_start(Gtk.Label(label="Quiet hours (local HH:MM):"), False, False, 0)
        self.quiet_start = Gtk.Entry()
        self.quiet_end = Gtk.Entry()
        for entry, key, hint in (
            (self.quiet_start, QUIET_START_KEY, "22:00"),
            (self.quiet_end, QUIET_END_KEY, "08:00"),
        ):
            entry.set_width_chars(6)
            entry.set_placeholder_text(hint)
            entry.set_text(self.vocab_service.settings_service.get_setting(key, "") or "")
            quiet.pack_start(entry, False, False, 0)
        section.pack_start(quiet, False, False, 0)
        hint = Gtk.Label(label="Leave both empty to disable. Applies to Word of the Day too.")
        section.pack_start(hint, False, False, 0)
        return self._make_frame("Notifications", section)

    def _build_translation_section(self) -> Gtk.Frame:
        """Build the translation provider/languages section."""
        translation_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Provider
        self.provider_combo = Gtk.ComboBoxText()
        for provider, name in ProviderRegistry.list_providers():
            self.provider_combo.append(provider, name)

        # Preserve supported providers; fall back only for unknown/legacy IDs.
        current_provider = self.vocab_service.settings_service.get_translation_provider()
        if current_provider not in [p[0] for p in ProviderRegistry.list_providers()]:
            current_provider = DEFAULT_TRANSLATION_PROVIDER  # Default if not found

        self.provider_combo.set_active_id(current_provider)
        translation_box.pack_start(labelled_row("Dictionary/API:", self.provider_combo), False, False, 0)

        # Source language
        self.src_lang_combo = Gtk.ComboBoxText()
        current_src_lang = self.vocab_service.settings_service.get_source_lang()
        self._fill_lang_combo(self.src_lang_combo, current_src_lang)
        translation_box.pack_start(labelled_row("Source Language:", self.src_lang_combo), False, False, 0)

        # Target language
        self.lang_combo = Gtk.ComboBoxText()
        current_lang = self.vocab_service.settings_service.get_target_lang()
        self._fill_lang_combo(self.lang_combo, current_lang)
        translation_box.pack_start(labelled_row("Target Language:", self.lang_combo), False, False, 0)

        # Test API button
        test_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        pack_button(test_btn_box, "Test API", self.on_test_api)

        self.test_spinner = Gtk.Spinner()
        self.test_spinner.set_size_request(20, 20)
        self.test_spinner.hide()
        test_btn_box.pack_start(self.test_spinner, False, False, 0)

        self.test_status_label = Gtk.Label("")
        self.test_status_label.set_xalign(0)
        self.test_status_label.set_line_wrap(True)
        self.test_status_label.hide()
        test_btn_box.pack_start(self.test_status_label, True, True, 0)

        translation_box.pack_start(test_btn_box, False, False, 0)
        return self._make_frame("Translation", translation_box)

    def _build_shortcuts_section(self) -> Gtk.Expander:
        """Build the keyboard shortcuts info section."""
        shortcuts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Info label - platform-specific instructions
        if IS_MACOS:
            shortcut_info = (
                "Configure hotkeys in System Settings → Keyboard → Shortcuts → Services\n"
                "or use a tool like Hammerspoon / Karabiner.\n\n"
                "Commands:"
            )
        else:
            shortcut_info = (
                "Configure hotkeys in your desktop environment:\n"
                "(Usually Settings → Keyboard → Shortcuts)\n\n"
                "Commands:"
            )
        info_label = Gtk.Label(shortcut_info)
        info_label.set_xalign(0)
        info_label.set_line_wrap(True)
        shortcuts_box.pack_start(info_label, False, False, 0)

        # Commands info
        cli_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vocab_cli.py"
        )
        cmds_label = Gtk.Label(
            f"Save selected:   python3 {cli_path} --save\n"
            f"Delete current: python3 {cli_path} --delete\n"
            f"Show next:      python3 {cli_path} --next"
        )
        cmds_label.set_xalign(0)
        cmds_label.set_line_wrap(True)
        cmds_label.set_selectable(True)
        shortcuts_box.pack_start(cmds_label, False, False, 0)

        expander = Gtk.Expander(label="Keyboard shortcuts")
        expander.add(shortcuts_box)
        return expander

    def _build_startup_section(self) -> Gtk.Frame:
        """Build the autostart section."""
        self.autostart_check = Gtk.CheckButton(label="Start with system login")
        self.autostart_check.set_active(AutostartManager.is_enabled())
        return self._make_frame("Startup", self.autostart_check)

    def _build_data_section(self) -> Gtk.Frame:
        """Build the data directory section."""
        data_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        hint_label = Gtk.Label(f"Leave empty to use default: {DEFAULT_DATA_DIR}")
        hint_label.set_xalign(0)
        hint_label.set_line_wrap(True)
        data_box.pack_start(hint_label, False, False, 0)

        # Custom data directory (read from config file)
        dir_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        dir_box.pack_start(Gtk.Label("Custom Path:"), False, False, 0)

        # Read from config file if available (JSON)
        config = read_config(self.config_file) if self.config_file else {}
        custom_data_dir = config.get(PENDING_RELOCATION_KEY, {}).get("data_dir", config.get(DATA_DIR_KEY, ""))

        self.data_dir_entry = Gtk.Entry()
        self.data_dir_entry.set_text(custom_data_dir)
        dir_box.pack_end(self.data_dir_entry, True, True, 0)
        data_box.pack_start(dir_box, False, False, 0)

        return self._make_frame("Data", data_box)

    def _build_wotd_section(self) -> Gtk.Frame:
        """Build the Word of the Day section."""
        self.wotd_check = Gtk.CheckButton(label="Enable Word of the Day")
        wotd_enabled = self.vocab_service.settings_service.get_setting(WOTD_ENABLED_KEY, "false") == "true"
        self.wotd_check.set_active(wotd_enabled)

        wotd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wotd_box.pack_start(self.wotd_check, False, False, 0)

        level_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        level_box.pack_start(Gtk.Label("Level:"), False, False, 0)
        self.wotd_level_combo = Gtk.ComboBoxText()
        for level in CEFR_LEVELS:
            self.wotd_level_combo.append(level, level)

        current_level = self.vocab_service.settings_service.get_setting(WOTD_LEVEL_KEY, DEFAULT_WOTD_LEVEL)
        self.wotd_level_combo.set_active_id(current_level)
        level_box.pack_end(self.wotd_level_combo, False, False, 0)
        wotd_box.pack_start(level_box, False, False, 0)

        return self._make_frame("Word of the Day", wotd_box)

    def _make_frame(self, title: str, content: Gtk.Widget) -> Gtk.Frame:
        """Wrap content in a frame with a border."""
        frame = Gtk.Frame(label=title)
        frame.set_shadow_type(Gtk.ShadowType.IN)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(10)
        content.set_margin_end(10)
        frame.add(content)
        return frame

    def on_test_api(self, widget: Gtk.Widget) -> None:
        """Test translation API."""
        if not self._test_completed:
            return

        provider = self.provider_combo.get_active_id()
        source_lang = self.src_lang_combo.get_active_id()
        target_lang = self.lang_combo.get_active_id()

        provider_name = ProviderRegistry.get(provider).get_name()
        self.test_status_label.set_text(f"Testing {provider_name}...")
        self.test_spinner.show()
        self.test_spinner.start()
        self._test_completed = False

        self.run_background(
            lambda: self.vocab_service.test_translation_api(source_lang, target_lang, provider),
            lambda result, error: self._test_complete(bool(result) and not error, provider_name),
        )

    def _test_complete(self, success, provider_name):
        """Handle test completion."""
        if self._test_completed:
            return
        self._test_completed = True

        self.test_spinner.stop()
        self.test_spinner.hide()

        status = "Success!" if success else "Failed!"
        detail = "works." if success else "not working."
        self.test_status_label.set_text(f"{status} {provider_name} {detail}")

    def _ask_data_dir_choice(self) -> DataDirChoice:
        """Ask how to handle the existing vocabulary on data-dir change."""
        dialog = Gtk.MessageDialog(
            self,
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.NONE,
            "The data directory changed.\n"
            "What should happen to your existing vocabulary?",
        )
        dialog.add_button("Copy my words on restart", Gtk.ResponseType.YES)
        dialog.add_button("Start empty", Gtk.ResponseType.NO)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            return DataDirChoice.MOVE
        if response == Gtk.ResponseType.NO:
            return DataDirChoice.START_EMPTY
        return DataDirChoice.CANCEL

    def on_save_settings(self, widget: Gtk.Widget) -> None:
        """Save settings."""
        try:
            settings = self._collect_settings()
        except ValueError as exc:
            self.status_label.set_text(str(exc))
            return

        data_dir_changed = self._apply_data_directory_choice(self.data_dir_entry.get_text().strip())
        if data_dir_changed is None:
            return

        try:
            self.vocab_service.settings_service.save_settings(settings)
        except Exception as exc:
            self.status_label.set_text(f"Could not save settings: {exc}")
            return

        self.on_data_changed()
        if self.autostart_check.get_active():
            AutostartManager.enable()
        else:
            AutostartManager.disable()

        if data_dir_changed:
            message = (
                "Settings saved!\n\n"
                "The directory change is scheduled for the next app start.\n"
                "Until then, all changes are saved in the current library.\n"
                "The original database will be kept as a backup."
            )
        else:
            message = "Settings saved successfully!"
        self.status_label.set_text(message)

    def _collect_settings(self) -> dict:
        """Read the form and reject invalid quiet hours before any writes."""
        start, end = self.quiet_start.get_text().strip(), self.quiet_end.get_text().strip()
        try:
            parse_quiet_hours(start, end)
        except ValueError as exc:
            raise ValueError("Enter both quiet-hour times as HH:MM, or leave both empty.") from exc
        return {
            QUIET_START_KEY: start,
            QUIET_END_KEY: end,
            REVIEW_INTERVAL_KEY: self.interval_combo.get_active_id(),
            TRANSLATION_PROVIDER_KEY: self.provider_combo.get_active_id(),
            SOURCE_LANG_KEY: self.src_lang_combo.get_active_id(),
            TARGET_LANG_KEY: self.lang_combo.get_active_id(),
            WOTD_ENABLED_KEY: "true" if self.wotd_check.get_active() else "false",
            WOTD_LEVEL_KEY: self.wotd_level_combo.get_active_id(),
        }

    def _apply_data_directory_choice(self, new_data_dir: str) -> bool | None:
        """Return whether restart is needed, or None on cancellation/failure."""
        if not self.config_file:
            return False
        config = read_config(self.config_file)
        old_data_dir = config.get(DATA_DIR_KEY, "")
        pending_dir = config.get(PENDING_RELOCATION_KEY, {}).get("data_dir")
        if old_data_dir != new_data_dir and pending_dir != new_data_dir:
            result = relocate_database(self.config_file, new_data_dir, self._ask_data_dir_choice)
            if result.verdict is RelocationVerdict.CANCELLED:
                return None
            if result.verdict is RelocationVerdict.FAILED:
                self.status_label.set_text(result.error)
                return None
            return True
        if old_data_dir == new_data_dir and PENDING_RELOCATION_KEY in config:
            del config[PENDING_RELOCATION_KEY]
            if not write_config(self.config_file, config):
                self.status_label.set_text("Could not cancel the pending directory change.")
                return None
        return pending_dir == new_data_dir
