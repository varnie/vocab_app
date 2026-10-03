"""Add word dialog."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from application.vocab_service import VocabService
from config import DEFAULT_SOURCE_LANG, DEFAULT_TARGET_LANG, SOURCE_LANG_KEY, TARGET_LANG_KEY
from infrastructure.current_phrase import write_current_phrase
from windows import BaseWindow, pack_button, padded_box


class AddWordDialog(BaseWindow):
    """Add word dialog."""

    def __init__(self, vocab_service: VocabService, on_add=None):
        super().__init__(title="Add New Word", width=400, height=250)
        self.vocab_service = vocab_service
        self.on_add = on_add
        self._busy = False

        self.build_ui()

    def build_ui(self) -> None:
        """Build the UI."""
        box = padded_box()
        self.add(box)

        # Get source and target languages from settings
        settings = self.vocab_service.settings_service.get_settings()
        target_lang_code = settings.get(TARGET_LANG_KEY, DEFAULT_TARGET_LANG)
        source_lang_code = settings.get(SOURCE_LANG_KEY, DEFAULT_SOURCE_LANG)
        self.target_lang = target_lang_code
        self.source_lang = source_lang_code

        # Find language objects
        languages = self.vocab_service.get_languages()
        target_language = None
        source_language = None
        for lang in languages:
            if lang.code == target_lang_code:
                target_language = lang
            if lang.code == source_lang_code:
                source_language = lang

        target_lang_name = target_language.name if target_language else target_lang_code
        target_lang_abbrev = (
            target_language.abbreviation if target_language else target_lang_code.upper()
        )

        source_lang_name = source_language.name if source_language else source_lang_code
        source_lang_abbrev = (
            source_language.abbreviation if source_language else source_lang_code.upper()
        )

        # Word entry with source language label
        box.pack_start(Gtk.Label(label=f"{source_lang_name} ({source_lang_abbrev}):"), False, False, 0)
        self.word_entry = Gtk.Entry()
        self.word_entry.set_placeholder_text("Enter word or phrase")
        box.pack_start(self.word_entry, False, False, 0)

        # Translation entry with target language label
        box.pack_start(Gtk.Label(label=f"{target_lang_name} ({target_lang_abbrev}):"), False, False, 0)
        self.translation_entry = Gtk.Entry()
        self.translation_entry.set_placeholder_text("Leave empty to auto-translate")
        box.pack_start(self.translation_entry, False, False, 0)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_homogeneous(True)

        pack_button(btn_box, "Cancel", lambda _: self.close(), expand=True)

        self.save_btn = pack_button(btn_box, "Save", self.on_add_clicked, expand=True)
        self.save_btn.get_style_context().add_class("suggested-action")
        self.without_translation = Gtk.CheckButton(label="Save without translation")
        box.pack_start(self.without_translation, False, False, 0)
        self.spinner = Gtk.Spinner()
        box.pack_start(self.spinner, False, False, 0)
        self.status_label = Gtk.Label(xalign=0)
        self.status_label.set_line_wrap(True)
        box.pack_start(self.status_label, False, False, 0)
        self.word_entry.connect("activate", self.on_add_clicked)
        self.translation_entry.connect("activate", self.on_add_clicked)
        self.word_entry.grab_focus()

        box.pack_start(btn_box, False, False, 10)

    def on_add_clicked(self, widget: Gtk.Widget) -> None:
        """Save entered translation, or translate unless explicitly disabled."""
        translation = self.translation_entry.get_text().strip() or None
        if self.without_translation.get_active():
            translation = None
        self._submit(translation, auto_translate=not self.without_translation.get_active())

    def _submit(self, translation: str | None, auto_translate: bool) -> None:
        """Validate input, add the word, and close on success."""
        word = self.word_entry.get_text().strip()
        if self._busy:
            return
        if not word:
            self._show_error("Please enter a word or phrase")
            return

        self._busy = True
        self.save_btn.set_sensitive(False)
        self.word_entry.set_sensitive(False)
        self.translation_entry.set_sensitive(False)
        self.without_translation.set_sensitive(False)
        self.spinner.start()
        self.status_label.set_text("Saving…" if translation or not auto_translate else "Translating…")

        def complete(result, error):
            self._busy = False
            self.spinner.stop()
            for control in (self.save_btn, self.word_entry, self.translation_entry, self.without_translation):
                control.set_sensitive(True)
            if error:
                self._show_error(error)
                return
            # Translation runs without writes. Closing the window discards its
            # callback, so Cancel cannot leave a word saved in the background.
            try:
                result = self.vocab_service.word_service.add_word(
                    result.phrase, result.translation or None,
                    target_lang=self.target_lang, source_lang=self.source_lang,
                )
            except Exception as exc:
                self._show_error(str(exc))
                return
            write_current_phrase(result.phrase)
            if self.on_add:
                self.on_add(result.phrase)
            self.destroy()

        self.run_background(
            lambda: self.vocab_service.word_service.prepare_word(
                word, translation, auto_translate=auto_translate,
                target_lang=self.target_lang, source_lang=self.source_lang,
            ), complete
        )

    def _show_error(self, message: str) -> None:
        """Show error dialog."""
        self.status_label.set_text(message)
