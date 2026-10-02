"""Edit one word and preview translations before saving."""

from typing import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from application.service_interfaces import AbstractSettingsService, AbstractWordManagementService
from domain.entities import Word
from windows import set_margins


class EditWordDialog(Gtk.Dialog):
    def __init__(
        self,
        parent: Gtk.Window,
        word: Word,
        target_lang: str,
        word_service: AbstractWordManagementService,
        settings_service: AbstractSettingsService,
        run_background: Callable,
    ) -> None:
        super().__init__(
            title="Edit Word", transient_for=parent,
            destroy_with_parent=True,
        )
        self.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        self.word = word
        self.target_lang = target_lang
        self.word_service = word_service
        self.settings_service = settings_service
        self.run_background = run_background
        self.closed = False
        self.connect("destroy", self._on_destroy)

        box = self.get_content_area()
        set_margins(box, 15)
        box.pack_start(Gtk.Label(label="Word:"), False, False, 5)
        self.word_entry = Gtk.Entry()
        self.word_entry.set_text(word.phrase)
        box.pack_start(self.word_entry, False, False, 5)
        box.pack_start(Gtk.Label(label="Translation:"), False, False, 5)
        self.trans_entry = Gtk.Entry()
        self.trans_entry.set_text(word.translation)
        box.pack_start(self.trans_entry, False, False, 5)
        self.error_label = Gtk.Label(xalign=0)
        self.error_label.set_line_wrap(True)
        box.pack_start(self.error_label, False, False, 5)
        self.set_default_response(Gtk.ResponseType.OK)
        self.get_widget_for_response(Gtk.ResponseType.OK).get_style_context().add_class("suggested-action")
        for entry in (self.word_entry, self.trans_entry):
            entry.set_activates_default(True)
        self.translate_btn = Gtk.Button(label="Translate again")
        self.translate_btn.connect("clicked", self._translate)
        box.pack_start(self.translate_btn, False, False, 5)

    def _on_destroy(self, *_args) -> None:
        self.closed = True

    def _set_translating(self, translating: bool) -> None:
        for widget in (self.translate_btn, self.word_entry, self.trans_entry):
            widget.set_sensitive(not translating)
        self.set_response_sensitive(Gtk.ResponseType.OK, not translating)

    def _translate(self, _button) -> None:
        phrase = self.word_entry.get_text().strip()
        source = self.settings_service.get_source_lang()
        self._set_translating(True)
        self.error_label.set_text("Translating…")
        self.run_background(
            lambda: self.word_service.translate_preview(phrase, self.target_lang, source),
            self._translation_complete,
        )

    def _translation_complete(self, result, error) -> None:
        if self.closed:
            return
        self._set_translating(False)
        self.error_label.set_text(error or "")
        if not error:
            self.trans_entry.set_text(result)

    def edit(self) -> bool:
        """Return whether the user saved; keep validation errors in the dialog."""
        self.show_all()
        try:
            while self.run() == Gtk.ResponseType.OK:
                try:
                    self.word_service.update_word(
                        self.word.id, self.word_entry.get_text().strip(),
                        self.trans_entry.get_text().strip(), target_lang=self.target_lang,
                    )
                except ValueError as exc:
                    self.error_label.set_text(str(exc))
                    continue
                return True
            return False
        finally:
            self.destroy()
