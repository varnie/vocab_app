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
    gi.require_version("Gdk", "3.0")
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


def test_cancel_translation_never_saves_late_result(gui, monkeypatch):
    from windows.add_word import AddWordDialog

    gtk, service = gui
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def translate(*_args):
        entered.set()
        assert release.wait(5)
        return "late translation"

    original_remove = service.remove_session

    def remove_session():
        original_remove()
        finished.set()

    monkeypatch.setattr(service.word_service.translation_service, "translate", translate)
    monkeypatch.setattr(service, "remove_session", remove_session)
    window = AddWordDialog(service)
    window.show_all()
    window.word_entry.set_text("Cancelled")
    window.on_add_clicked(None)
    assert entered.wait(2)
    window.close()
    drain(gtk)
    assert window.closed
    release.set()
    assert finished.wait(2)
    drain(gtk)
    assert service.word_service.word_repo.get_by_phrase("Cancelled") is None


@pytest.mark.parametrize("width", [440, 860, 1000])
def test_browser_narrow_layout_and_hidden_status(gui, width):
    from windows.word_browser import WordBrowserWindow

    gtk, service = gui
    word = service.add_word("A long phrase " * 10, "Long translation " * 10)
    service.snooze_word(word.id, int(time.time()) + 86400)
    browser = WordBrowserWindow(service)
    browser.show_all()
    browser.resize(width, 650)
    for _ in range(10):
        drain(gtk)
        time.sleep(0.02)
    assert browser.get_size().width <= width
    browser.hidden_only.set_active(True)
    browser.treeview.set_cursor(gtk.TreePath.new_from_string("0"))
    drain(gtk)
    assert "Hidden until" in browser.detail_label.get_text()
    assert browser.resume_btn.get_sensitive()
    browser.on_snooze(None, resume=True)
    assert len(browser.model) == 0
    assert not browser.resume_btn.get_sensitive()


def test_browser_deletes_and_restores_other_languages(gui, monkeypatch):
    from windows.word_browser import WordBrowserWindow

    gtk, service = gui
    word = service.add_word("Hello", "bonjour", target_lang="fr")
    service.review_word(word.id)
    browser = WordBrowserWindow(service)
    browser.show_all()
    browser.untranslated.set_active(True)
    browser.treeview.set_cursor(gtk.TreePath.new_from_string("0"))
    drain(gtk)
    messages = []

    def confirm(_parent, message):
        messages.append(message)
        return True

    monkeypatch.setattr("windows.word_browser.ask_confirm", confirm)
    browser.on_delete(None)
    browser.on_undo(None)
    assert "ALL languages" in messages[0]
    assert service.word_service.word_repo.get_translation(word.id, "fr").translation == "bonjour"
    assert service.get_stats()["total_reviews"] == 1


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

    from gi.repository import Gdk

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
        window.show_all()
        for _ in range(10):
            drain(gtk)
            time.sleep(0.02)
        width, height = window.get_size()
        snapshot = Gdk.pixbuf_get_from_window(window.get_window(), 0, 0, width, height)
        assert snapshot is not None
        snapshot.savev(str(docs / f"screenshot-{name}.png"), "png", [], [])
        window.destroy()
