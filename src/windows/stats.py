"""Stats window."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from windows import BaseWindow, padded_box, show_message


class StatsWindow(BaseWindow):
    """Statistics window."""

    def __init__(self, vocab_service):
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
        stats = self.vocab_service.get_stats()

        # Total words
        row = self._make_row("Total words:", str(stats.get("total_words", 0)))
        box.pack_start(row, False, False, 0)

        # Added today
        row = self._make_row("Added today:", str(stats.get("today_words", 0)))
        box.pack_start(row, False, False, 0)

        # Reviews today
        row = self._make_row("Shown today:", str(stats.get("today_reviews", 0)))
        box.pack_start(row, False, False, 0)

        # Total reviews
        row = self._make_row("Total exposures:", str(stats.get("total_reviews", 0)))
        box.pack_start(row, False, False, 0)

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
        export_btn = Gtk.Button(label="Export CSV")
        export_btn.connect("clicked", self.on_export)
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", lambda _: self.refresh())
        btn_box.pack_start(refresh_btn, True, True, 0)
        btn_box.pack_start(export_btn, True, True, 0)
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

        if dialog.run() == Gtk.ResponseType.OK:
            try:
                self.vocab_service.export_csv(dialog.get_filename())
                show_message(self, Gtk.MessageType.INFO, "Export successful!")
            except Exception as e:
                show_message(self, Gtk.MessageType.ERROR, f"Export failed: {e}")

        dialog.destroy()
