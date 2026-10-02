# Windows package - shared GTK helpers for dialog windows.

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import threading

from gi.repository import Gdk, GLib, Gtk


class BaseWindow(Gtk.Window):
    """Base window with centered position and default size."""

    def __init__(self, title: str, width: int, height: int) -> None:
        super().__init__(title=title)
        self.set_default_size(width, height)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.closed = False
        self.on_data_changed = lambda: None
        self.connect("destroy", self._mark_closed)
        self.connect("key-press-event", self._on_key)

    def _mark_closed(self, *_args):
        self.closed = True

    def _on_key(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if (
            event.keyval == Gdk.KEY_f and event.state & Gdk.ModifierType.CONTROL_MASK
            and hasattr(self, "search_entry")
        ):
            self.search_entry.grab_focus()
            return True
        return False

    def run_background(self, work, complete):
        """Return results to GTK only while the window is still alive."""
        def deliver(result, error):
            if not self.closed:
                complete(result, error)
            return False

        def worker():
            result, error = None, None
            try:
                result = work()
            except Exception as exc:
                error = str(exc)
            finally:
                self.vocab_service.remove_session()
            GLib.idle_add(deliver, result, error)

        threading.Thread(target=worker, daemon=True).start()


def set_margins(widget: Gtk.Widget, margin: int) -> None:
    """Apply uniform margins to an existing widget."""
    widget.set_margin_top(margin)
    widget.set_margin_bottom(margin)
    widget.set_margin_start(margin)
    widget.set_margin_end(margin)


def padded_box(
    orientation: Gtk.Orientation = Gtk.Orientation.VERTICAL,
    spacing: int = 10,
    margin: int = 20,
) -> Gtk.Box:
    """Create a box with uniform margins."""
    box = Gtk.Box(orientation=orientation, spacing=spacing)
    set_margins(box, margin)
    return box


def pack_button(box: Gtk.Box, label: str, callback, *, expand=False, sensitive=True) -> Gtk.Button:
    """Create and connect an action button in a horizontal box."""
    button = Gtk.Button(label=label)
    button.connect("clicked", callback)
    button.set_sensitive(sensitive)
    box.pack_start(button, expand, expand, 0)
    return button


def labelled_row(label: str, widget: Gtk.Widget) -> Gtk.Box:
    """Place a label on the left and its control on the right."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    box.pack_start(Gtk.Label(label=label), False, False, 0)
    box.pack_end(widget, False, False, 0)
    return box


def show_message(parent: Gtk.Window, kind: Gtk.MessageType, text: str) -> None:
    """Show a modal OK dialog."""
    dialog = Gtk.MessageDialog(
        parent,
        Gtk.DialogFlags.DESTROY_WITH_PARENT,
        kind,
        Gtk.ButtonsType.OK,
        text,
    )
    dialog.run()
    dialog.destroy()


def ask_confirm(parent: Gtk.Window, text: str) -> bool:
    """Show a modal Yes/No dialog, return True on Yes."""
    dialog = Gtk.MessageDialog(
        parent,
        Gtk.DialogFlags.DESTROY_WITH_PARENT,
        Gtk.MessageType.QUESTION,
        Gtk.ButtonsType.YES_NO,
        text,
    )
    response = dialog.run()
    dialog.destroy()
    return response == Gtk.ResponseType.YES


__all__ = ["BaseWindow", "ask_confirm", "labelled_row", "pack_button", "padded_box", "set_margins", "show_message"]
