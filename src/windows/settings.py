"""Settings window."""

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from application.service_interfaces import CEFR_LEVELS
from config import (
    DATA_DIR_KEY,
    DEFAULT_SETTINGS,
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    DEFAULT_TRANSLATION_PROVIDER,
    DEFAULT_WOTD_LEVEL,
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
from infrastructure.data_relocation import DataDirChoice, RelocationVerdict, relocate_database
from infrastructure.translation import ProviderRegistry
from version import get_version
from windows import BaseWindow, padded_box, show_message


class SettingsWindow(BaseWindow):
    """Settings window."""

    def __init__(self, vocab_service, config_file=None):
        super().__init__(title="Settings", width=600, height=1100)
        self.vocab_service = vocab_service
        self.config_file = config_file

        self._test_completed = True

        self.build_ui()

    def build_ui(self) -> None:
        """Build the UI."""
        scroll = Gtk.ScrolledWindow()
        self.add(scroll)

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

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.destroy())
        btn_box.pack_start(cancel_btn, True, True, 0)

        save_btn = Gtk.Button(label="Save Settings")
        save_btn.connect("clicked", self.on_save_settings)
        btn_box.pack_start(save_btn, True, True, 0)

        box.pack_start(btn_box, False, False, 10)

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
        interval_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        interval_box.pack_start(Gtk.Label("Review Interval:"), False, False, 0)
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
            self.vocab_service.get_setting(REVIEW_INTERVAL_KEY, DEFAULT_SETTINGS[REVIEW_INTERVAL_KEY])
        )
        self.interval_combo.set_active_id(current_interval)
        interval_box.pack_end(self.interval_combo, False, False, 0)
        return self._make_frame("Review", interval_box)

    def _build_translation_section(self) -> Gtk.Frame:
        """Build the translation provider/languages section."""
        translation_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Provider
        provider_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        provider_box.pack_start(Gtk.Label("Dictionary/API:"), False, False, 0)
        self.provider_combo = Gtk.ComboBoxText()
        for provider, name in ProviderRegistry.list_providers():
            self.provider_combo.append(provider, name)

        # Handle legacy "google" setting and default
        current_provider = self.vocab_service.get_settings().get(
            TRANSLATION_PROVIDER_KEY, DEFAULT_TRANSLATION_PROVIDER
        )
        if current_provider in ("google", "google_direct"):
            current_provider = DEFAULT_TRANSLATION_PROVIDER  # Legacy fallback (Google direct is blocked)
        if current_provider not in [p[0] for p in ProviderRegistry.list_providers()]:
            current_provider = DEFAULT_TRANSLATION_PROVIDER  # Default if not found

        self.provider_combo.set_active_id(current_provider)
        provider_box.pack_end(self.provider_combo, False, False, 0)
        translation_box.pack_start(provider_box, False, False, 0)

        # Source language
        src_lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        src_lang_box.pack_start(Gtk.Label("Source Language:"), False, False, 0)
        self.src_lang_combo = Gtk.ComboBoxText()
        current_src_lang = self.vocab_service.get_settings().get(SOURCE_LANG_KEY, DEFAULT_SOURCE_LANG)
        self._fill_lang_combo(self.src_lang_combo, current_src_lang)
        src_lang_box.pack_end(self.src_lang_combo, False, False, 0)
        translation_box.pack_start(src_lang_box, False, False, 0)

        # Target language
        lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lang_box.pack_start(Gtk.Label("Target Language:"), False, False, 0)
        self.lang_combo = Gtk.ComboBoxText()
        current_lang = self.vocab_service.get_settings().get(TARGET_LANG_KEY, DEFAULT_TARGET_LANG)
        self._fill_lang_combo(self.lang_combo, current_lang)
        lang_box.pack_end(self.lang_combo, False, False, 0)
        translation_box.pack_start(lang_box, False, False, 0)

        # Test API button
        test_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        test_btn = Gtk.Button(label="Test API")
        test_btn.connect("clicked", self.on_test_api)
        test_btn_box.pack_start(test_btn, False, False, 0)

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

    def _build_shortcuts_section(self) -> Gtk.Frame:
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

        return self._make_frame("Keyboard Shortcuts", shortcuts_box)

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
        custom_data_dir = config.get(DATA_DIR_KEY, "")

        self.data_dir_entry = Gtk.Entry()
        self.data_dir_entry.set_text(custom_data_dir)
        dir_box.pack_end(self.data_dir_entry, True, True, 0)
        data_box.pack_start(dir_box, False, False, 0)

        return self._make_frame("Data", data_box)

    def _build_wotd_section(self) -> Gtk.Frame:
        """Build the Word of the Day section."""
        self.wotd_check = Gtk.CheckButton(label="Enable Word of the Day")
        wotd_enabled = self.vocab_service.get_setting(WOTD_ENABLED_KEY, "false") == "true"
        self.wotd_check.set_active(wotd_enabled)

        wotd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wotd_box.pack_start(self.wotd_check, False, False, 0)

        level_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        level_box.pack_start(Gtk.Label("Level:"), False, False, 0)
        self.wotd_level_combo = Gtk.ComboBoxText()
        for level in CEFR_LEVELS:
            self.wotd_level_combo.append(level, level)

        current_level = self.vocab_service.get_setting(WOTD_LEVEL_KEY, DEFAULT_WOTD_LEVEL)
        self.wotd_level_combo.set_active_id(current_level)
        level_box.pack_end(self.wotd_level_combo, False, False, 0)
        wotd_box.pack_start(level_box, False, False, 0)

        return self._make_frame("Word of the Day", wotd_box)

    def _make_frame(self, title: str, content: Gtk.Widget) -> Gtk.Frame:
        """Wrap content in a frame with a border."""
        frame = Gtk.Frame(label=title)
        frame.set_shadow_type(Gtk.ShadowType.IN)
        align = Gtk.Alignment.new(0, 0, 1, 1)
        align.set_padding(10, 10, 10, 10)
        align.add(content)
        frame.add(align)
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

        # Safety timeout: force failure after 30 seconds
        def test_timeout():
            if not self._test_completed:
                GLib.idle_add(self._test_complete, False, provider_name)
            return False

        GLib.timeout_add_seconds(30, test_timeout)

        def run_test():
            success = self.vocab_service.test_translation_api(source_lang, target_lang, provider)
            GLib.idle_add(self._test_complete, success, provider_name)

        import threading

        thread = threading.Thread(target=run_test)
        thread.daemon = True
        thread.start()

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

        GLib.timeout_add(3000, self._clear_test_status)

    def _clear_test_status(self):
        """Clear the test status after a delay."""
        self.test_status_label.set_text("")
        return False

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
        dialog.add_button("Move my words", Gtk.ResponseType.YES)
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
        settings = {
            REVIEW_INTERVAL_KEY: self.interval_combo.get_active_id(),
            TRANSLATION_PROVIDER_KEY: self.provider_combo.get_active_id(),
            SOURCE_LANG_KEY: self.src_lang_combo.get_active_id(),
            TARGET_LANG_KEY: self.lang_combo.get_active_id(),
            WOTD_ENABLED_KEY: "true" if self.wotd_check.get_active() else "false",
            WOTD_LEVEL_KEY: self.wotd_level_combo.get_active_id(),
        }

        new_data_dir = self.data_dir_entry.get_text().strip()

        db_relocated = False
        fresh_library = False
        data_dir_changed = False
        if self.config_file:
            config = read_config(self.config_file)
            old_data_dir = config.get(DATA_DIR_KEY, "")
            if old_data_dir != new_data_dir:
                data_dir_changed = True
                result = relocate_database(self.config_file, new_data_dir, self._ask_data_dir_choice)
                if result.verdict is RelocationVerdict.CANCELLED:
                    return
                if result.verdict is RelocationVerdict.MOVED:
                    db_relocated = True
                elif result.verdict is RelocationVerdict.START_EMPTY:
                    fresh_library = True
                elif result.verdict is RelocationVerdict.FAILED:
                    show_message(self, Gtk.MessageType.ERROR, result.error)
                    return
            config[DATA_DIR_KEY] = new_data_dir
            if not write_config(self.config_file, config):
                show_message(
                    self,
                    Gtk.MessageType.ERROR,
                    "Failed to write the config file. Settings were not saved.",
                )
                return

        self.vocab_service.save_settings(settings)

        # Handle autostart
        if self.autostart_check.get_active():
            AutostartManager.enable()
        else:
            AutostartManager.disable()

        # Show confirmation
        if db_relocated:
            msg_text = (
                "Settings saved!\n\n"
                "Your vocabulary was moved to the new location.\n"
                "Restart the app to use it."
            )
        elif fresh_library:
            msg_text = (
                "Settings saved!\n\n"
                "Note: you chose to start empty — after restart the app will use "
                "a separate, empty library in the new location.\n"
                "Your old vocabulary stays where it was."
            )
        elif data_dir_changed:
            msg_text = (
                "Settings saved!\n\n"
                "Note: you need to restart the app for data directory changes to take effect."
            )
        else:
            msg_text = "Settings saved successfully!"

        show_message(self, Gtk.MessageType.INFO, msg_text)
