"""Words added today window."""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk, Pango

from application.vocab_service import VocabService
from windows import BaseWindow, padded_box


class WordsTodayWindow(BaseWindow):
    """Window showing words added today."""

    def __init__(self, vocab_service: VocabService):
        super().__init__(title="Words Added Today", width=860, height=520)
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0) if display else None
        if monitor:
            area = monitor.get_workarea()
            self.set_default_size(min(860, int(area.width * 0.9)), min(520, int(area.height * 0.85)))
        self.vocab_service = vocab_service
        self.build_ui()
        self.connect("key-press-event", self._on_key_press)

    def build_ui(self) -> None:
        """Build the UI."""
        vbox = padded_box(spacing=12, margin=16)
        self.add(vbox)

        self.wotd_label = Gtk.Label("")
        self.wotd_label.set_xalign(0)
        self.wotd_label.set_line_wrap(True)
        self.wotd_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.wotd_label.set_max_width_chars(60)
        self.wotd_label.set_selectable(True)
        self.wotd_label.set_no_show_all(True)
        vbox.pack_start(self.wotd_label, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)
        vbox.pack_start(scrolled, True, True, 0)

        self.list_store = Gtk.ListStore(str, str)
        self.tree_view = Gtk.TreeView(model=self.list_store)
        self.tree_view.set_headers_visible(True)

        self._columns = []
        for index, title in enumerate(("Word", "Translation")):
            renderer = Gtk.CellRendererText()
            renderer.set_property("wrap-mode", Pango.WrapMode.WORD_CHAR)
            renderer.set_property("wrap-width", 200)
            renderer.set_property("ypad", 8)
            renderer.set_property("xpad", 10)
            renderer.set_property("yalign", 0)
            column = Gtk.TreeViewColumn(title, renderer, text=index)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width(220)
            column.set_sort_column_id(index)
            self.tree_view.append_column(column)
            self._columns.append((column, renderer))
        self.tree_view.connect("size-allocate", self._resize_columns)

        scrolled.add(self.tree_view)

        footer = Gtk.Box(spacing=12)
        self.count_label = Gtk.Label(xalign=0)
        footer.pack_start(self.count_label, True, True, 0)
        self.copy_button = Gtk.Button(label="Copy selected")
        self.copy_button.set_tooltip_text("Copy word and translation (Ctrl+C)")
        self.copy_button.set_sensitive(False)
        self.copy_button.connect("clicked", self._copy_selected)
        footer.pack_end(self.copy_button, False, False, 0)
        self.tree_view.get_selection().connect("changed", self._selection_changed)
        vbox.pack_end(footer, False, False, 0)

        self._populate()

    def _resize_columns(self, _widget, allocation) -> None:
        """Keep both columns readable without horizontal scrolling."""
        available = max(2, allocation.width - 4)
        word_width = int(available * 0.38)
        for (column, renderer), width in zip(self._columns, (word_width, available - word_width)):
            width = max(1, width)
            wrap_width = max(1, width - 24)
            if renderer.get_property("wrap-width") != wrap_width:
                renderer.set_property("wrap-width", wrap_width)
                column.set_fixed_width(width)
                column.queue_resize()

    def _selection_changed(self, selection) -> None:
        _model, selected = selection.get_selected()
        self.copy_button.set_sensitive(selected is not None)

    def _copy_selected(self, _button=None) -> None:
        model, selected = self.tree_view.get_selection().get_selected()
        if selected is not None:
            text = f"{model[selected][0]}\t{model[selected][1]}"
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)

    def _on_key_press(self, _widget, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if (
            event.state & Gdk.ModifierType.CONTROL_MASK
            and event.keyval in (Gdk.KEY_c, Gdk.KEY_C)
            and self.tree_view.has_focus()
        ):
            self._copy_selected()
            return True
        return False

    def _populate(self) -> None:
        """Fetch and display words added today."""
        self.list_store.clear()
        words = self.vocab_service.word_service.get_words_added_today()
        for w in words:
            self.list_store.append([w.phrase, w.translation or ""])
        count = len(self.list_store)
        self.count_label.set_text("No words added today" if not count else f"Added today: {count}")
        self._refresh_wotd_banner()

    def refresh(self):
        self._populate()

    def _refresh_wotd_banner(self) -> None:
        """Show today's Word of the Day above the list, if already shown."""
        today = self.vocab_service.wotd_service.get_today_display()
        if today is None:
            self.wotd_label.hide()
            return
        word, translation, level = today
        text = f"⭐ Word of the Day [{level}]: {word}"
        if translation:
            text += f" → {translation}"
        self.wotd_label.set_text(text)
        self.wotd_label.show()
