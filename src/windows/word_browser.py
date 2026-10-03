"""Word browser window."""

import gi

gi.require_version("Gtk", "3.0")
import time
from dataclasses import dataclass
from datetime import datetime

from gi.repository import Gdk, GLib, Gtk, Pango

from application.vocab_service import VocabService
from config import DEFAULT_TARGET_LANG, TARGET_LANG_KEY
from domain.entities import Word, WordSnapshot
from windows import BaseWindow, ask_confirm, pack_button, padded_box
from windows.edit_word import EditWordDialog


@dataclass(frozen=True)
class TranslationDeletion:
    word_id: int
    translation: str
    target_lang: str


class WordBrowserWindow(BaseWindow):
    """Word browser and manager window."""

    search_entry: Gtk.Entry
    lang_combo: Gtk.ComboBoxText
    model: Gtk.ListStore
    treeview: Gtk.TreeView
    delete_btn: Gtk.Button
    status_label: Gtk.Label

    def __init__(self, vocab_service: VocabService) -> None:
        super().__init__(title="Word Browser", width=910, height=600)
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0) if display else None
        if monitor:
            area = monitor.get_workarea()
            if area.width > 40 and area.height > 60:
                self.set_default_size(min(910, area.width - 40), min(600, area.height - 60))
        self.vocab_service = vocab_service
        self.selected_word_id: int | None = None
        self.words: list[Word] = []
        self.page_size = 100
        self.current_page = 0
        self._search_timer_id: int | None = None
        self.sort = "phrase"
        self.descending = False
        self._undo: WordSnapshot | TranslationDeletion | None = None

        self.build_ui()
        self.load_words()
        self.connect("destroy", self._cancel_search)

    def _cancel_search(self, *_args):
        if self._search_timer_id is not None:
            GLib.source_remove(self._search_timer_id)
            self._search_timer_id = None

    def build_ui(self) -> None:
        """Build the UI."""
        main_box = padded_box(spacing=10, margin=15)
        self.add(main_box)
        self._build_filters(main_box)
        self._build_word_list(main_box)
        self._build_actions(main_box)
        self._build_pagination(main_box)

    def _build_filters(self, main_box: Gtk.Box) -> None:
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(toolbar, False, False, 0)

        # Search entry
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search words...")
        self.search_entry.set_width_chars(10)
        self.search_entry.connect("changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_search_activate)
        toolbar.pack_start(self.search_entry, True, True, 0)

        pack_button(toolbar, "Refresh", self.on_refresh)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        main_box.pack_start(toolbar, False, False, 0)

        # Language filter
        toolbar.pack_start(Gtk.Label(label="Target Language:"), False, False, 5)

        self.lang_combo = Gtk.ComboBoxText()
        settings = self.vocab_service.settings_service.get_settings()
        current_lang = settings.get(TARGET_LANG_KEY, DEFAULT_TARGET_LANG)

        self._rebuild_lang_combo(current_lang)
        self.lang_combo.connect("changed", self.on_lang_changed)
        toolbar.pack_start(self.lang_combo, False, False, 0)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        main_box.pack_start(toolbar, False, False, 0)
        self.untranslated = Gtk.CheckButton(label="Without translation")
        self.untranslated.connect("toggled", self.on_lang_changed)
        toolbar.pack_start(self.untranslated, False, False, 0)

        self.hidden_only = Gtk.CheckButton(label="Hidden only")
        self.hidden_only.connect("toggled", self.on_lang_changed)
        toolbar.pack_start(self.hidden_only, False, False, 0)

    def _build_word_list(self, main_box: Gtk.Box) -> None:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        main_box.pack_start(scrolled, True, True, 0)

        # Create model for TreeView
        self.model = Gtk.ListStore(int, str, str, str)
        self.treeview = Gtk.TreeView(model=self.model)

        # Columns
        columns = [
            ("#", 50),
            ("Word", 300),
            ("Translation", 300),
            ("Last shown", 150),
        ]

        for i, (title, width) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width(width)
            column.set_resizable(True)
            if i:
                column.set_clickable(True)
                column.connect("clicked", self.on_sort, ("phrase", "translation", "last_reviewed")[i - 1])
            self.treeview.append_column(column)

        self.treeview.connect("row-activated", self.on_row_activated)
        self.treeview.connect("cursor-changed", self.on_cursor_changed)
        self.treeview.connect("size-allocate", self._fit_columns)
        scrolled.add(self.treeview)
        self.detail_label = Gtk.Label(xalign=0)
        self.detail_label.set_line_wrap(True)
        self.detail_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.detail_label.set_width_chars(1)
        self.detail_label.set_selectable(True)
        self.detail_label.set_max_width_chars(90)
        main_box.pack_start(self.detail_label, False, False, 0)

    def _build_actions(self, main_box: Gtk.Box) -> None:
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(bottom_bar, False, False, 0)

        self.delete_btn = pack_button(bottom_bar, "Delete translation", self.on_delete, sensitive=False)
        self.undo_btn = pack_button(bottom_bar, "Undo deletion", self.on_undo, sensitive=False)
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(bottom_bar, False, False, 0)
        self.snooze_btn = pack_button(bottom_bar, "Hide for 7 days", self.on_snooze, sensitive=False)
        self.resume_btn = pack_button(
            bottom_bar, "Show again", lambda _: self.on_snooze(None, resume=True), sensitive=False,
        )

    def _build_pagination(self, main_box: Gtk.Box) -> None:
        """Keep navigation on its own row so actions fit smaller screens."""
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(bottom_bar, False, False, 0)
        self.prev_btn = pack_button(bottom_bar, "← Prev", self.on_prev_page)
        self.next_btn = pack_button(bottom_bar, "Next →", self.on_next_page)

        # Status label
        self.status_label = Gtk.Label(label="")
        self.status_label.set_line_wrap(True)
        self.status_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.status_label.set_width_chars(1)
        self.status_label.set_xalign(0)
        bottom_bar.pack_start(self.status_label, True, True, 0)

    def _fit_columns(self, _tree, allocation):
        """Keep both text columns visible; details show the full selected text."""
        columns = self.treeview.get_columns()
        narrow = allocation.width < 650
        columns[3].set_visible(not narrow)
        available = max(200, allocation.width - 50 - (0 if narrow else 155))
        for index in (1, 2):
            width = max(100, available // 2)
            if columns[index].get_fixed_width() != width:
                columns[index].set_fixed_width(width)

    def load_words(self) -> None:
        """Load words from database."""
        search = self.search_entry.get_text().strip() or None
        words = self.vocab_service.word_service.get_words(
            search=search,
            target_lang=self._selected_language(),
            limit=self.page_size + 1,
            offset=self.current_page * self.page_size,
            sort=self.sort, descending=self.descending, untranslated=self.untranslated.get_active(),
            hidden_only=self.hidden_only.get_active(),
        )
        self._has_next = len(words) > self.page_size
        self.words = words[:self.page_size]
        if not self.words and self.current_page > 0:
            self.current_page -= 1
            self.load_words()
            return
        self.refresh_model()

    def refresh_model(self) -> None:
        """Refresh the tree model."""
        self.model.clear()
        self._clear_selection()

        for i, word in enumerate(self.words):
            last_shown = (
                datetime.fromtimestamp(word.last_reviewed).strftime("%Y-%m-%d") if word.last_reviewed else "Never"
            )
            self.model.append([i + 1, word.phrase, word.translation, last_shown])

        self._refresh_pagination()

    def _clear_selection(self) -> None:
        self.selected_word_id = None
        self.delete_btn.set_sensitive(False)
        self.delete_btn.set_label("Delete translation")
        self.snooze_btn.set_sensitive(False)
        self.resume_btn.set_sensitive(False)
        self.detail_label.set_text("")

    def _refresh_pagination(self) -> None:
        total = len(self.words)
        start = self.current_page * self.page_size + 1 if total > 0 else 0
        end = start + total - 1 if total else 0
        if total:
            self.status_label.set_text(f"{start}-{end} · Page {self.current_page + 1}")
        else:
            message = "No matches. Clear the search or change the filter."
            if not self.search_entry.get_text().strip():
                message = "No words in this view. Add a word or change the language/filter."
            self.status_label.set_text(message)
        self.prev_btn.set_sensitive(self.current_page > 0)
        self.next_btn.set_sensitive(self._has_next)

    def on_sort(self, column, key):
        self.descending = not self.descending if self.sort == key else False
        self.sort = key
        for item in self.treeview.get_columns():
            item.set_sort_indicator(item == column)
        column.set_sort_order(Gtk.SortType.DESCENDING if self.descending else Gtk.SortType.ASCENDING)
        self.current_page = 0
        self.load_words()

    def on_search_changed(self, widget: Gtk.Widget) -> None:
        """Handle search entry changed with debounce."""
        self._cancel_search()
        self._search_timer_id = GLib.timeout_add(300, self._debounced_search)

    def _debounced_search(self) -> bool:
        """Debounced search callback."""
        self._search_timer_id = None
        self.current_page = 0
        self.load_words()
        return False

    def on_search_activate(self, widget: Gtk.Widget) -> None:
        """Handle search entry Enter key."""
        self._cancel_search()
        self.current_page = 0
        self.load_words()

    def on_lang_changed(self, widget: Gtk.Widget) -> None:
        """Handle language dropdown changed."""
        self.current_page = 0
        self.load_words()

    def on_refresh(self, widget: Gtk.Widget) -> None:
        """Handle refresh button clicked."""
        self.current_page = 0
        self.refresh()

    def refresh(self):
        self.refresh_lang_dropdown()

    def on_prev_page(self, widget: Gtk.Widget) -> None:
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.load_words()

    def on_next_page(self, widget: Gtk.Widget) -> None:
        """Go to next page."""
        self.current_page += 1
        self.load_words()

    def on_cursor_changed(self, widget: Gtk.Widget) -> None:
        """Handle row selection."""
        selection = self.treeview.get_selection()
        model, it = selection.get_selected()

        if it and model:
            idx = model.get_value(it, 0) - 1
            if 0 <= idx < len(self.words):
                self.selected_word_id = self.words[idx].id
                self.snooze_btn.set_sensitive(True)
                word = self.words[idx]
                hidden = bool(word.hidden_until and word.hidden_until > time.time())
                self.resume_btn.set_sensitive(hidden)
                # Rows without a translation can't lose one — offer whole-word delete.
                self.delete_btn.set_label("Delete translation" if word.translation else "Delete word")
                self.delete_btn.set_sensitive(True)
                status = (
                    f"\nHidden until {datetime.fromtimestamp(word.hidden_until):%Y-%m-%d %H:%M}" if hidden else ""
                )
                self.detail_label.set_text(
                    f"{word.phrase}\n{word.translation or 'No translation in this language'}{status}"
                )
            else:
                self._clear_selection()
        else:
            self._clear_selection()

    def on_row_activated(
        self, treeview: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn
    ) -> None:
        """Handle row double-clicked."""
        model = treeview.get_model()
        it = model.get_iter(path)
        if it:
            idx = model.get_value(it, 0) - 1
            if 0 <= idx < len(self.words):
                word = self.words[idx]
                self.show_edit_dialog(word)

    def on_delete(self, widget: Gtk.Widget) -> None:
        """Handle delete button clicked."""
        word = self._selected_word()
        if not word:
            return
        current_lang = self._selected_language()

        if word.translation:
            # Confirm dialog
            if ask_confirm(self, f"Delete translation for '{word.phrase}'?"):
                # Only delete translation for current language, not the whole word
                self.vocab_service.word_service.delete_translation(self.selected_word_id, current_lang)
                self._undo = TranslationDeletion(word.id, word.translation, current_lang)
                self._after_delete()
        elif ask_confirm(self, f"Delete word '{word.phrase}' in ALL languages?\n"
                         "This removes every translation, review history and hidden-until date.\n"
                         "Missing a translation in this view does not mean the word has no other translations."):
            snapshot = self.vocab_service.word_service.delete_word_with_undo(self.selected_word_id)
            self._undo = snapshot
            self._after_delete()

    def _after_delete(self) -> None:
        """Common refresh after a delete or undo."""
        self.undo_btn.set_sensitive(True)
        self.selected_word_id = None
        self.refresh_lang_dropdown()
        self.on_data_changed()

    def on_undo(self, _widget):
        if self._undo:
            try:
                if isinstance(self._undo, WordSnapshot):
                    self.vocab_service.word_service.restore_word(self._undo)
                else:
                    self.vocab_service.word_service.restore_translation(
                        self._undo.word_id, self._undo.translation, self._undo.target_lang,
                    )
            except ValueError as exc:
                self.status_label.set_text(str(exc))
                return
            self._undo = None
            self.undo_btn.set_sensitive(False)
            self.refresh_lang_dropdown()
            self.on_data_changed()

    def on_snooze(self, _widget, resume=False):
        if self.selected_word_id:
            until = 0 if resume else int(time.time()) + 7 * 86400
            self.vocab_service.word_service.snooze_word(self.selected_word_id, until)
            self.load_words()
            self.on_data_changed()
            self.status_label.set_text("Word is available again." if resume else "Hidden from the queue for 7 days.")

    def _rebuild_lang_combo(self, preserve_id: str | None) -> None:
        """Rebuild the language dropdown, preserving the given selection."""
        lang_counts = self.vocab_service.review_service.get_language_counts()
        languages = self.vocab_service.get_languages()
        sorted_languages = sorted(languages, key=lambda lang: lang.name)
        lang_names = {lang.code: lang.name for lang in languages}

        self.lang_combo.remove_all()

        # Keep empty languages selectable, including untranslated-only libraries.
        selected_name, selected_count = lang_counts.get(preserve_id, (None, 0)) if preserve_id else (None, 0)
        if not selected_name:
            selected_name = lang_names.get(preserve_id, preserve_id.upper() if preserve_id else "")

        if preserve_id:
            self.lang_combo.append(preserve_id, f"{selected_name} ({selected_count})")

        # Other languages with words, alphabetically
        for lang in sorted_languages:
            if lang.code == preserve_id:
                continue
            name, count = lang_counts.get(lang.code, (lang.name, 0))
            self.lang_combo.append(lang.code, f"{name} ({count})")

        self.lang_combo.set_active_id(preserve_id or DEFAULT_TARGET_LANG)

    def refresh_lang_dropdown(self) -> None:
        """Refresh language dropdown counts."""
        selected_lang = self._selected_language()

        self.lang_combo.handler_block_by_func(self.on_lang_changed)
        try:
            self._rebuild_lang_combo(selected_lang)
        finally:
            self.lang_combo.handler_unblock_by_func(self.on_lang_changed)

        # Reload words with the selected language
        self.load_words()

    def _selected_language(self) -> str:
        return self.lang_combo.get_active_id() or self.vocab_service.settings_service.get_target_lang()

    def _selected_word(self) -> Word | None:
        return next((word for word in self.words if word.id == self.selected_word_id), None)

    def show_edit_dialog(self, word: Word) -> None:
        dialog = EditWordDialog(
            self, word, self._selected_language(),
            self.vocab_service.word_service, self.vocab_service.settings_service,
            self.run_background,
        )
        if dialog.edit():
            self.refresh_lang_dropdown()
            self.on_data_changed()
