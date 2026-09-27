"""GTK integration checks, opt-in on an isolated display; never use the live DB."""

import os
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("RUN_GTK_TESTS") != "1", reason="requires isolated GTK display")


@pytest.fixture
def gui(tmp_path):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    from bootstrap import create_vocab_service

    assert Gtk.init_check()[0]
    service = create_vocab_service(db_path=str(tmp_path / "gui.db"))
    yield Gtk, service
    for window in Gtk.Window.list_toplevels():
        window.destroy()
    service.close()


def drain(gtk):
    while gtk.events_pending():
        gtk.main_iteration_do(False)


def test_browser_empty_sort_language_and_undo(gui, monkeypatch):
    from windows.word_browser import WordBrowserWindow

    gtk, service = gui
    browser = WordBrowserWindow(service)
    browser.show_all()
    drain(gtk)
    assert "0--1" not in browser.status_label.get_text()
    for i in range(103):
        service.add_word(f"word{i:03}", f"translation{i:03}")
    browser.on_refresh(None)
    browser.on_next_page(None)
    assert browser.current_page == 1
    browser.lang_combo.set_active_id("fr")
    assert browser.current_page == 0
    assert len(browser.model) == 0
    browser.lang_combo.set_active_id("ru")
    browser.on_sort(browser.treeview.get_columns()[1], "phrase")
    assert browser.words[0].phrase == "word102"
    browser.treeview.set_cursor(gtk.TreePath.new_from_string("0"))
    drain(gtk)
    assert browser.selected_word_id is not None
    monkeypatch.setattr("windows.word_browser.ask_confirm", lambda *_: True)
    browser.on_delete(None)
    browser.on_undo(None)
    assert service.word_service.word_repo.get_by_phrase("word102").translation == "translation102"
    browser.search_entry.set_text("unmatched")
    browser.destroy()  # pending search must not access destroyed widgets
    drain(gtk)


def test_add_stays_responsive_and_prevents_double_submission(gui, monkeypatch):
    from windows.add_word import AddWordDialog

    gtk, service = gui
    entered, release = threading.Event(), threading.Event()
    calls = []

    def translate(*_args):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return "Привет"

    monkeypatch.setattr(service.word_service.translation_service, "translate", translate)
    monkeypatch.setattr("windows.add_word.write_current_phrase", lambda _: None)
    window = AddWordDialog(service)
    window.show_all()
    window.word_entry.set_text("Hello")
    window.on_add_clicked(None)
    window.on_add_clicked(None)
    assert entered.wait(2)
    assert not window.save_btn.get_sensitive()
    drain(gtk)
    assert not window.closed
    release.set()
    deadline = time.monotonic() + 5
    while not window.closed and time.monotonic() < deadline:
        drain(gtk)
        time.sleep(0.01)
    assert window.closed
    assert len(calls) == 1
    assert service.word_service.word_repo.get_by_phrase("hello").phrase == "Hello"


def test_settings_stats_and_today_refresh(gui):
    from windows.settings import SettingsWindow
    from windows.stats import StatsWindow
    from windows.words_today import WordsTodayWindow

    gtk, service = gui
    settings = SettingsWindow(service, config_file=None)
    stats = StatsWindow(service)
    today = WordsTodayWindow(service)
    service.add_word("Bonjour", "Hello")
    today.refresh()
    stats.refresh()
    settings.show_all()
    drain(gtk)
    assert len(today.list_store) == 1
    assert settings.get_default_size().height <= 720


def test_edit_dialog_saves_selected_language(gui):
    from gi.repository import GLib

    from windows.word_browser import WordBrowserWindow

    gtk, service = gui
    word = service.add_word("Hello", "привет")
    service.word_service.word_repo.add_translation(word.id, "bonjour", "fr")
    browser = WordBrowserWindow(service)
    browser.lang_combo.set_active_id("fr")

    def submit():
        dialog = next(window for window in gtk.Window.list_toplevels() if isinstance(window, gtk.Dialog))
        entries = [child for child in dialog.get_content_area().get_children() if isinstance(child, gtk.Entry)]
        entries[1].set_text("salut")
        dialog.response(gtk.ResponseType.OK)
        return False

    GLib.idle_add(submit)
    browser.show_edit_dialog(browser.words[0])
    assert service.word_service.word_repo.get_translation(word.id, "ru").translation == "привет"
    assert service.word_service.word_repo.get_translation(word.id, "fr").translation == "salut"


def test_settings_validate_quiet_hours_without_saving_invalid_input(gui, monkeypatch):
    from windows.settings import SettingsWindow

    _gtk, service = gui
    monkeypatch.setattr("windows.settings.AutostartManager.enable", lambda: None)
    monkeypatch.setattr("windows.settings.AutostartManager.disable", lambda: None)
    window = SettingsWindow(service)
    window.quiet_start.set_text("invalid")
    window.on_save_settings(None)
    assert "HH:MM" in window.status_label.get_text()
    assert service.get_setting("quiet_start") is None
    window.quiet_start.set_text("22:00")
    window.quiet_end.set_text("08:00")
    window.on_save_settings(None)
    assert service.get_setting("quiet_start") == "22:00"
    assert service.get_setting("quiet_end") == "08:00"


@pytest.mark.skipif(os.environ.get("UPDATE_SCREENSHOTS") != "1", reason="explicit documentation update")
def test_documentation_screenshots(gui):
    from pathlib import Path

    import cairo

    from windows.add_word import AddWordDialog
    from windows.settings import SettingsWindow
    from windows.stats import StatsWindow
    from windows.word_browser import WordBrowserWindow

    gtk, service = gui
    for phrase, translation in (
        ("A breath of fresh air", "Глоток свежего воздуха"),
        ("Bonjour", "Добрый день"),
        ("Keep an open mind", "Будь открыт новым идеям"),
        ("Take your time", "Не торопись"),
    ):
        service.add_word(phrase, translation)
    docs = Path(__file__).resolve().parents[3] / "docs"
    for name, window in (
        ("word-browser", WordBrowserWindow(service)),
        ("add-word", AddWordDialog(service)),
        ("settings", SettingsWindow(service)),
        ("stats", StatsWindow(service)),
    ):
        if isinstance(window, WordBrowserWindow):
            window.treeview.set_cursor(gtk.TreePath.new_from_string("0"))
        offscreen = gtk.OffscreenWindow()
        width, height = window.get_default_size()
        offscreen.set_size_request(width, height)
        offscreen.get_style_context().add_class("background")
        child = window.get_child()
        window.remove(child)
        offscreen.add(child)
        offscreen.show_all()
        for _ in range(10):
            drain(gtk)
            time.sleep(0.02)
        # Offscreen windows have transparent margins; paint the window background
        # before asking GTK to draw its actual widgets into the snapshot.
        allocation = offscreen.get_allocation()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, allocation.width, allocation.height)
        context = cairo.Context(surface)
        context.set_source_rgb(0.965, 0.961, 0.957)
        context.paint()
        offscreen.draw(context)
        surface.write_to_png(str(docs / f"screenshot-{name}.png"))
        offscreen.destroy()
        window.destroy()
