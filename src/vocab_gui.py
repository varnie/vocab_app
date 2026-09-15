#!/usr/bin/env python3
"""Main vocab GUI application with system tray."""

import logging
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

from application.review_scheduler import ReviewScheduler
from bootstrap import create_vocab_service
from config import GNOME_TRAY_WARNING_KEY
from constants import CONFIG_FILE, ICONS_DIR, IS_LINUX, IS_MACOS
from infrastructure.current_phrase import read_current_phrase, write_current_phrase
from infrastructure.notifications import send_notification
from windows.add_word import AddWordDialog
from windows.settings import SettingsWindow
from windows.stats import StatsWindow
from windows.word_browser import WordBrowserWindow
from windows.words_today import WordsTodayWindow

logger = logging.getLogger(__name__)


def _create_tray():
    if IS_MACOS:
        from infrastructure.tray.tray_macos import MacOSTray

        return MacOSTray()
    from infrastructure.tray.tray_linux import LinuxTray

    return LinuxTray()


class VocabApp(Gtk.Application):
    """Main application with system tray using Gtk.Application."""

    def __init__(self):
        super().__init__(
            application_id="com.vocab_app",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.connect("activate", self._on_activate)

        self.config_file = CONFIG_FILE
        self.vocab_service = None
        self.scheduler = None
        self.tray = None

        self._windows = {}

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gtk.Window.set_default_icon_from_file(os.path.join(ICONS_DIR, "translate.svg"))

        # Keep app running even without windows (tray app)
        Gio.Application.hold(self)

        try:
            self.vocab_service = create_vocab_service(self.config_file)
        except Exception as e:
            logger.exception("Error creating vocab_service: %s", e)
            import traceback

            traceback.print_exc()
            sys.exit(1)
        if not self.vocab_service:
            error_dialog = Gtk.MessageDialog(
                None,
                Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.ERROR,
                Gtk.ButtonsType.OK,
                "Failed to initialize database. Check your settings.",
            )
            error_dialog.run()
            sys.exit(1)

        self.tray = _create_tray()
        self.tray.setup(self._menu_callbacks())

        self.scheduler = ReviewScheduler(
            review_service=self.vocab_service.review_service,
            wotd_service=self.vocab_service.wotd_service,
            settings_service=self.vocab_service.settings_service,
            read_phrase=read_current_phrase,
            write_phrase=write_current_phrase,
            notify_callback=self.notify,
            # ReviewScheduler invokes this callback from its worker thread.
            # GTK/AppIndicator widgets must only be updated on GTK's main loop.
            label_callback=lambda label: GLib.idle_add(self.tray.set_label, label),
            cleanup_callback=self.vocab_service.remove_session,
            notification_service=self.vocab_service.notification_service,
        )
        self.scheduler.start()

        if IS_LINUX:
            from infrastructure.tray import get_desktop_environment

            if get_desktop_environment() in (
                "gnome",
                "ubuntu",
            ) and not self.vocab_service.get_setting(GNOME_TRAY_WARNING_KEY):
                self.notify(
                    "GNOME detected. If tray icon is missing, "
                    "install 'Top Icons' or 'Tray Icons' extension.",
                    "Vocab",
                )
                self.vocab_service.set_setting(GNOME_TRAY_WARNING_KEY, "true")

    def do_activate(self):
        Gtk.Application.do_activate(self)

    def _on_activate(self, app):
        pass

    def _menu_callbacks(self):
        return {
            "show_next": self.on_show_next,
            "pause": self.on_pause,
            "add_word": self.on_add_word,
            "words_today": self.on_words_today,
            "word_browser": self.on_word_browser,
            "stats": self.on_show_stats,
            "settings": self.on_settings,
            "quit": self.on_quit,
        }

    def _open_window(self, key, create_fn):
        if self._windows.get(key):
            self._windows[key].present()
        else:
            win = create_fn()
            win.set_application(self)
            win.show_all()
            self._windows[key] = win

    def _open_simple(self, key, window_cls, *args) -> None:
        """Open a window that only needs vocab_service (plus extra args)."""

        def create_window():
            win = window_cls(self.vocab_service, *args)
            win.connect("destroy", lambda w: self._on_window_closed(key, w))
            return win

        self._open_window(key, create_window)

    def _on_window_closed(self, key, window=None):
        self._windows[key] = None

    @staticmethod
    def notify(body: str, title: str = "Vocab") -> None:
        """Send notification with icon."""
        send_notification(body, title)

    def on_show_next(self, widget=None) -> None:
        """Show next word immediately."""
        word = self.scheduler.on_show_next()
        if word:
            self.tray.set_label(str(word.phrase)[:20])

    def on_show_stats(self, widget=None) -> None:
        """Show stats window."""
        self._open_simple("stats", StatsWindow)

    def on_add_word(self, widget=None) -> None:
        """Show add word dialog."""

        def on_add(word):
            self.tray.set_label(word[:20])

        def create_window():
            win = AddWordDialog(self.vocab_service, on_add)
            win.connect("destroy", lambda w: self._on_window_closed("add", w))
            return win

        self._open_window("add", create_window)

    def on_pause(self, widget=None) -> None:
        """Toggle pause/resume reviews."""
        label = self.scheduler.on_pause()
        self.tray.set_pause_label(label)

    def on_settings(self, widget=None) -> None:
        """Show settings window."""
        self._open_simple("settings", SettingsWindow, self.config_file)

    def on_words_today(self, widget=None) -> None:
        """Show words added today window."""
        self._open_simple("words_today", WordsTodayWindow)

    def on_word_browser(self, widget=None) -> None:
        """Show word browser window."""
        self._open_simple("browser", WordBrowserWindow)

    def on_quit(self, widget=None) -> None:
        """Quit application."""
        if self.scheduler:
            self.scheduler.stop()
        self.vocab_service.close()
        self.quit()


def main():
    """Main entry point - GUI only."""
    app = VocabApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
