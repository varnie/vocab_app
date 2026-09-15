"""Add word dialog."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from config import DEFAULT_SOURCE_LANG, DEFAULT_TARGET_LANG, SOURCE_LANG_KEY, TARGET_LANG_KEY
from domain.exceptions import TranslationError
from infrastructure.current_phrase import write_current_phrase
from windows import BaseWindow, padded_box, show_message


class AddWordDialog(BaseWindow):
    """Add word dialog."""

    def __init__(self, vocab_service, on_add=None):
        super().__init__(title="Add New Word", width=400, height=250)
        self.vocab_service = vocab_service
        self.on_add = on_add

        self.build_ui()

    def build_ui(self) -> None:
        """Build the UI."""
        box = padded_box()
        self.add(box)

        # Get source and target languages from settings
        settings = self.vocab_service.get_settings()
        target_lang_code = settings.get(TARGET_LANG_KEY, DEFAULT_TARGET_LANG)
        source_lang_code = settings.get(SOURCE_LANG_KEY, DEFAULT_SOURCE_LANG)

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
        box.pack_start(Gtk.Label(f"{source_lang_name} ({source_lang_abbrev}):"), False, False, 0)
        self.word_entry = Gtk.Entry()
        self.word_entry.set_placeholder_text("Enter word or phrase")
        box.pack_start(self.word_entry, False, False, 0)

        # Translation entry with target language label
        box.pack_start(Gtk.Label(f"{target_lang_name} ({target_lang_abbrev}):"), False, False, 0)
        self.translation_entry = Gtk.Entry()
        self.translation_entry.set_placeholder_text("Leave empty to auto-translate")
        box.pack_start(self.translation_entry, False, False, 0)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_homogeneous(True)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.destroy())
        btn_box.pack_start(cancel_btn, True, True, 0)

        add_btn = Gtk.Button(label="Add")
        add_btn.connect("clicked", self.on_add_clicked)
        btn_box.pack_start(add_btn, True, True, 0)

        translate_btn = Gtk.Button(label="Add & Translate")
        translate_btn.connect("clicked", self.on_add_translate)
        btn_box.pack_start(translate_btn, True, True, 0)

        box.pack_start(btn_box, False, False, 10)

    def on_add_clicked(self, widget: Gtk.Widget) -> None:
        """Add word with manual translation (no auto-translate)."""
        translation = self.translation_entry.get_text().strip() or None
        self._submit(translation, auto_translate=False)

    def on_add_translate(self, widget: Gtk.Widget) -> None:
        """Add word and auto-translate."""
        self._submit(None, auto_translate=True)

    def _submit(self, translation: str | None, auto_translate: bool) -> None:
        """Validate input, add the word, and close on success."""
        word = self.word_entry.get_text().strip()
        if not word:
            self._show_error("Please enter a word or phrase")
            return

        try:
            self.vocab_service.add_word(word, translation, auto_translate=auto_translate)
        except (ValueError, TranslationError) as e:
            self._show_error(str(e))
            return

        write_current_phrase(word)

        if self.on_add:
            self.on_add(word)
        self.destroy()

    def _show_error(self, message: str) -> None:
        """Show error dialog."""
        show_message(self, Gtk.MessageType.ERROR, message)
