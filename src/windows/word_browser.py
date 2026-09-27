"""Word browser window."""

import gi

gi.require_version("Gtk", "3.0")
import time
from datetime import datetime

from gi.repository import GLib, Gtk

from config import DEFAULT_TARGET_LANG, TARGET_LANG_KEY
from domain.entities import Word
from windows import BaseWindow, ask_confirm, padded_box, set_margins


class WordBrowserWindow(BaseWindow):
    """Word browser and manager window."""

    search_entry: Gtk.Entry
    lang_combo: Gtk.ComboBoxText
    model: Gtk.ListStore
    treeview: Gtk.TreeView
    delete_btn: Gtk.Button
    status_label: Gtk.Label

    def __init__(self, vocab_service) -> None:
        super().__init__(title="Word Browser", width=910, height=600)
        self.vocab_service = vocab_service
        self.selected_word_id: int | None = None
        self.words: list[Word] = []
        self.page_size = 100
        self.current_page = 0
        self._search_timer_id: int | None = None
        self.sort = "phrase"
        self.descending = False
        self._undo = None

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

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(toolbar, False, False, 0)

        # Search entry
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search words...")
        self.search_entry.set_width_chars(25)
        self.search_entry.connect("changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_search_activate)
        toolbar.pack_start(self.search_entry, False, False, 0)

        # Language filter
        toolbar.pack_start(Gtk.Label(label="Language:"), False, False, 5)

        self.lang_combo = Gtk.ComboBoxText()
        settings = self.vocab_service.get_settings()
        current_lang = settings.get(TARGET_LANG_KEY, DEFAULT_TARGET_LANG)

        self._rebuild_lang_combo(current_lang)
        self.lang_combo.connect("changed", self.on_lang_changed)
        toolbar.pack_start(self.lang_combo, False, False, 0)
        self.untranslated = Gtk.CheckButton(label="Without translation")
        self.untranslated.connect("toggled", self.on_lang_changed)
        toolbar.pack_start(self.untranslated, False, False, 0)

        # Refresh button
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", self.on_refresh)
        toolbar.pack_start(refresh_btn, False, False, 0)

        # TreeView
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
            ("Last reviewed", 120),
        ]

        for i, (title, width) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            column.set_fixed_width(width)
            column.set_resizable(True)
            if i:
                column.set_clickable(True)
                column.connect("clicked", self.on_sort, ("phrase", "translation", "last_reviewed")[i - 1])
            self.treeview.append_column(column)

        self.treeview.connect("row-activated", self.on_row_activated)
        self.treeview.connect("cursor-changed", self.on_cursor_changed)
        scrolled.add(self.treeview)
        self.detail_label = Gtk.Label(xalign=0)
        self.detail_label.set_line_wrap(True)
        self.detail_label.set_selectable(True)
        self.detail_label.set_max_width_chars(90)
        main_box.pack_start(self.detail_label, False, False, 0)

        # Bottom bar
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(bottom_bar, False, False, 0)

        # Delete button
        self.delete_btn = Gtk.Button(label="Delete translation")
        self.delete_btn.connect("clicked", self.on_delete)
        self.delete_btn.set_sensitive(False)
        bottom_bar.pack_start(self.delete_btn, False, False, 0)
        self.undo_btn = Gtk.Button(label="Undo deletion")
        self.undo_btn.set_sensitive(False)
        self.undo_btn.connect("clicked", self.on_undo)
        bottom_bar.pack_start(self.undo_btn, False, False, 0)
        self.snooze_btn = Gtk.Button(label="Hide for 7 days")
        self.snooze_btn.set_sensitive(False)
        self.snooze_btn.connect("clicked", self.on_snooze)
        bottom_bar.pack_start(self.snooze_btn, False, False, 0)
        resume_btn = Gtk.Button(label="Show again")
        resume_btn.connect("clicked", lambda _: self.on_snooze(None, resume=True))
        bottom_bar.pack_start(resume_btn, False, False, 0)

        # Pagination and status get their own row so actions fit smaller screens.
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(bottom_bar, False, False, 0)
        self.prev_btn = Gtk.Button(label="← Prev")
        self.prev_btn.connect("clicked", self.on_prev_page)
        bottom_bar.pack_start(self.prev_btn, False, False, 0)

        self.next_btn = Gtk.Button(label="Next →")
        self.next_btn.connect("clicked", self.on_next_page)
        bottom_bar.pack_start(self.next_btn, False, False, 0)

        # Status label
        self.status_label = Gtk.Label(label="")
        self.status_label.set_line_wrap(True)
        self.status_label.set_xalign(0)
        bottom_bar.pack_start(self.status_label, True, True, 0)

    def load_words(self) -> None:
        """Load words from database."""
        search = self.search_entry.get_text().strip() or None
        lang = self.lang_combo.get_active_id() if self.lang_combo.get_model() else None

        # If empty or None, use current language from settings
        if not lang:
            settings = self.vocab_service.get_settings()
            lang = settings.get(TARGET_LANG_KEY, DEFAULT_TARGET_LANG)

        words = self.vocab_service.get_words(
            search=search,
            target_lang=lang,
            limit=self.page_size + 1,
            offset=self.current_page * self.page_size,
            sort=self.sort, descending=self.descending, untranslated=self.untranslated.get_active(),
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
        self.selected_word_id = None
        self.delete_btn.set_sensitive(False)
        self.delete_btn.set_label("Delete translation")
        self.snooze_btn.set_sensitive(False)
        self.detail_label.set_text("")

        for i, word in enumerate(self.words):
            phrase = word.phrase
            target = word.translation
            last_reviewed_ts = word.last_reviewed

            if last_reviewed_ts:
                lr = datetime.fromtimestamp(last_reviewed_ts)
                last_reviewed_str = lr.strftime("%Y-%m-%d")
            else:
                last_reviewed_str = "Never"

            self.model.append([i + 1, phrase, target, last_reviewed_str])

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
        if self._search_timer_id is not None:
            GLib.source_remove(self._search_timer_id)
        self._search_timer_id = GLib.timeout_add(300, self._debounced_search)

    def _debounced_search(self) -> bool:
        """Debounced search callback."""
        self._search_timer_id = None
        self.current_page = 0
        self.load_words()
        return False

    def on_search_activate(self, widget: Gtk.Widget) -> None:
        """Handle search entry Enter key."""
        if self._search_timer_id is not None:
            GLib.source_remove(self._search_timer_id)
            self._search_timer_id = None
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
                # Rows without a translation can't lose one — offer whole-word delete.
                self.delete_btn.set_label("Delete translation" if word.translation else "Delete word")
                self.delete_btn.set_sensitive(True)
                self.detail_label.set_text(f"{word.phrase}\n{word.translation or 'No translation yet'}")
            else:
                self.selected_word_id = None
                self.delete_btn.set_sensitive(False)
        else:
            self.selected_word_id = None
            self.delete_btn.set_sensitive(False)
            self.snooze_btn.set_sensitive(False)

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
        if not self.selected_word_id:
            return

        # Find the word
        word = None
        for w in self.words:
            if w.id == self.selected_word_id:
                word = w
                break

        if not word:
            return

        # Get current language from dropdown
        current_lang = self.lang_combo.get_active_id() if self.lang_combo.get_model() else None
        if not current_lang:
            settings = self.vocab_service.get_settings()
            current_lang = settings.get(TARGET_LANG_KEY, DEFAULT_TARGET_LANG)

        if word.translation:
            # Confirm dialog
            if ask_confirm(self, f"Delete translation for '{word.phrase}'?"):
                # Only delete translation for current language, not the whole word
                self.vocab_service.delete_translation(self.selected_word_id, current_lang)
                self._undo = ("translation", word.id, word.translation, current_lang)
                self._after_delete()
        elif ask_confirm(self, f"Delete word '{word.phrase}'?"):
            self.vocab_service.delete_word_by_id(self.selected_word_id)
            self._undo = ("word", word.phrase, word.translation, current_lang)
            self._after_delete()

    def _after_delete(self) -> None:
        """Common refresh after a delete or undo."""
        self.undo_btn.set_sensitive(True)
        self.selected_word_id = None
        self.load_words()
        self.refresh_lang_dropdown()
        self.on_data_changed()

    def on_undo(self, _widget):
        if self._undo:
            try:
                kind, *payload = self._undo
                if kind == "word":
                    phrase, translation, lang = payload
                    restored = self.vocab_service.add_word(phrase)
                    if translation:
                        self.vocab_service.update_word(restored.id, phrase, translation, lang)
                else:
                    self.vocab_service.restore_translation(*payload)
            except ValueError as exc:
                self.status_label.set_text(str(exc))
                return
            self._undo = None
            self.undo_btn.set_sensitive(False)
            self.refresh_lang_dropdown()
            self.on_data_changed()

    def on_snooze(self, _widget, resume=False):
        if self.selected_word_id:
            self.vocab_service.snooze_word(self.selected_word_id, 0 if resume else int(time.time()) + 7 * 86400)
            self.status_label.set_text("Word is available again." if resume else "Hidden from the queue for 7 days.")

    def _rebuild_lang_combo(self, preserve_id: str | None) -> None:
        """Rebuild the language dropdown, preserving the given selection."""
        lang_counts = self.vocab_service.get_language_counts()
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
        # Preserve current selection before rebuilding
        selected_lang = self.lang_combo.get_active_id() if self.lang_combo.get_model() else None
        if not selected_lang:
            settings = self.vocab_service.get_settings()
            selected_lang = settings.get(TARGET_LANG_KEY, DEFAULT_TARGET_LANG)

        self.lang_combo.handler_block_by_func(self.on_lang_changed)
        try:
            self._rebuild_lang_combo(selected_lang)
        finally:
            self.lang_combo.handler_unblock_by_func(self.on_lang_changed)

        # Reload words with the selected language
        self.load_words()

    def show_edit_dialog(self, word: Word) -> None:
        """Show edit dialog for a word."""
        dialog = Gtk.Dialog(
            "Edit Word",
            self,
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            ("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK),
        )

        box = dialog.get_content_area()
        set_margins(box, 15)

        # Word entry
        box.pack_start(Gtk.Label("Word:"), False, False, 5)
        word_entry = Gtk.Entry()
        word_entry.set_text(word.phrase)
        box.pack_start(word_entry, False, False, 5)

        # Translation entry
        box.pack_start(Gtk.Label("Translation:"), False, False, 5)
        trans_entry = Gtk.Entry()
        trans_entry.set_text(word.translation)
        box.pack_start(trans_entry, False, False, 5)
        target_lang = self.lang_combo.get_active_id()
        error_label = Gtk.Label(xalign=0)
        error_label.set_line_wrap(True)
        box.pack_start(error_label, False, False, 5)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.get_widget_for_response(Gtk.ResponseType.OK).get_style_context().add_class("suggested-action")
        for entry in (word_entry, trans_entry):
            entry.set_activates_default(True)
        translate_btn = Gtk.Button(label="Translate again")
        box.pack_start(translate_btn, False, False, 5)
        # Translation previews do not persist anything until Save is pressed.
        alive = [True]
        dialog.connect("destroy", lambda *_: alive.__setitem__(0, False))

        def translate(_button):
            phrase = word_entry.get_text().strip()
            source = self.vocab_service.settings_service.get_source_lang()
            provider = self.vocab_service.settings_service.get_translation_provider()
            translate_btn.set_sensitive(False)
            error_label.set_text("Translating…")

            def complete(result, error):
                if alive[0]:
                    translate_btn.set_sensitive(True)
                    error_label.set_text(error or "")
                    if not error:
                        trans_entry.set_text(result)

            self.run_background(
                lambda: self.vocab_service.word_service.translation_service.translate(
                    phrase, target_lang, source, provider
                ), complete,
            )

        translate_btn.connect("clicked", translate)

        dialog.show_all()

        while dialog.run() == Gtk.ResponseType.OK:
            new_phrase = word_entry.get_text().strip()
            new_trans = trans_entry.get_text().strip()

            try:
                self.vocab_service.update_word(
                    word.id, new_phrase, new_trans, target_lang=target_lang
                )
            except ValueError as exc:
                error_label.set_text(str(exc))
                continue
            self.refresh_lang_dropdown()
            self.on_data_changed()
            break

        dialog.destroy()
