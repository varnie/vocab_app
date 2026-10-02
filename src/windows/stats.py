"""Stats window."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from application.vocab_service import VocabService
from windows import BaseWindow, pack_button, padded_box, show_message


class StatsWindow(BaseWindow):
    """Statistics window."""

    def __init__(self, vocab_service: VocabService):
        super().__init__(title="Vocabulary Statistics", width=400, height=450)
        self.vocab_service = vocab_service

        self.build_ui()

    def refresh(self):
        child = self.get_child()
        if child:
            child.destroy()
        self.build_ui()
        self.show_all()

    def build_ui(self) -> None:
        """Build the UI."""
        box = padded_box()
        self.add(box)

        # Stats
        stats = self.vocab_service.review_service.get_stats()

        for label, key in (
            ("Total words:", "total_words"),
            ("Added today:", "today_words"),
            ("Shown today:", "today_reviews"),
            ("Total exposures:", "total_reviews"),
        ):
            box.pack_start(self._make_row(label, str(stats.get(key, 0))), False, False, 0)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep, False, False, 10)

        # Streak
        streak = stats.get("streak", 0)
        streak_row = self._make_row("Streak:", f"{streak} days")
        box.pack_start(streak_row, False, False, 0)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep, False, False, 10)

        # Export button
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        pack_button(btn_box, "Refresh", lambda _: self.refresh(), expand=True)
        pack_button(btn_box, "Export CSV", self.on_export, expand=True)
        box.pack_start(btn_box, False, False, 0)

    def _make_row(self, label: str, value: str) -> Gtk.Box:
        """Make a stat row."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        lbl = Gtk.Label(label)
        lbl.set_xalign(0)
        lbl.set_hexpand(True)
        box.pack_start(lbl, True, True, 0)

        val = Gtk.Label(value)
        val.set_xalign(1)
        box.pack_start(val, False, False, 0)

        return box

    def on_export(self, widget: Gtk.Widget) -> None:
        """Export to CSV."""
        dialog = Gtk.FileChooserDialog(
            "Export to CSV",
            self,
            Gtk.FileChooserAction.SAVE,
            ("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK),
        )
        dialog.set_current_name("vocabulary.csv")
        dialog.set_do_overwrite_confirmation(True)
        language = Gtk.ComboBoxText()
        language.append("all", "All languages")
        current = self.vocab_service.settings_service.get_target_lang()
        language.append(current, f"Current target language ({current.upper()})")
        language.set_active_id("all")
        language.show()
        dialog.set_extra_widget(language)

        if dialog.run() == Gtk.ResponseType.OK:
            try:
                selected = language.get_active_id()
                self.vocab_service.export_service.export_csv(
                    dialog.get_filename(), None if selected == "all" else selected,
                )
                show_message(self, Gtk.MessageType.INFO, "Export successful!")
            except Exception as e:
                show_message(self, Gtk.MessageType.ERROR, f"Export failed: {e}")

        dialog.destroy()
