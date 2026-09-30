"""Linux system tray using AppIndicator3 or GtkStatusIcon fallback."""

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gtk

from constants import ICONS_DIR, MENU_ITEMS

# Try AppIndicator3
_has_appindicator = False
try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

    _has_appindicator = True
except (ValueError, ImportError):
    pass


def get_desktop_environment():
    xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    for name in ("gnome", "kde", "plasma", "xfce", "ubuntu"):
        if name in xdg:
            return "kde" if name == "plasma" else name
    return "unknown"


class LinuxTray:
    _indicator: AppIndicator3.Indicator | None
    _status_icon: Gtk.StatusIcon | None
    _gtk_menu: Gtk.Menu | None
    _pause_item: Gtk.MenuItem | None

    def setup(self, callbacks):
        tray_icon_path = os.path.join(ICONS_DIR, "tray_text.svg")
        menu = self._create_gtk_menu(callbacks)

        if _has_appindicator:
            self._indicator = AppIndicator3.Indicator.new(
                "vocab-app",
                tray_icon_path if os.path.exists(tray_icon_path) else "dialog-information",
                AppIndicator3.IndicatorCategory.SYSTEM_SERVICES,
            )
            self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self._indicator.set_menu(menu)
        else:
            self._status_icon = Gtk.StatusIcon()
            if os.path.exists(tray_icon_path):
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(tray_icon_path, 22, 22)
                self._status_icon.set_from_pixbuf(pixbuf)
            else:
                self._status_icon.set_from_icon_name("dialog-information")
            self._status_icon.set_tooltip_text("Vocab App")
            self._status_icon.set_visible(True)
            self._gtk_menu = menu
            self._status_icon.connect("popup-menu", self._on_popup)
            self._status_icon.connect("activate", self._on_activate)

    def _create_gtk_menu(self, callbacks):
        menu = Gtk.Menu()
        for item in MENU_ITEMS:
            if item is None:
                menu.append(Gtk.SeparatorMenuItem())
            else:
                label, key = item
                mi = Gtk.MenuItem(label=label)
                mi.connect("activate", callbacks[key])
                menu.append(mi)
                if key == "pause":
                    self._pause_item = mi
        menu.show_all()
        return menu

    def _on_popup(self, icon, button, activate_time):
        self._gtk_menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, activate_time)

    def _on_activate(self, icon):
        self._gtk_menu.popup(
            None, None, Gtk.StatusIcon.position_menu, icon, 1, Gtk.get_current_event_time()
        )

    def set_label(self, text):
        if _has_appindicator and hasattr(self, "_indicator"):
            self._indicator.set_label(text, "vocab-app")

    def set_pause_label(self, label):
        self._pause_item.set_label(label)
