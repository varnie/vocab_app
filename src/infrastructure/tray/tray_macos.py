"""Native macOS menu bar tray using PyObjC."""

import os

import objc
from AppKit import NSImage, NSMenu, NSMenuItem, NSStatusBar, NSVariableStatusItemLength
from Foundation import NSObject
from gi.repository import GLib

from constants import ICONS_DIR, MENU_ITEMS


class _MenuDelegate(NSObject):
    """ObjC delegate that dispatches NSMenuItem actions to Python callbacks."""

    def initWithCallbacks_(self, callbacks):
        self = objc.super(_MenuDelegate, self).init()
        if self is None:
            return None
        self._callbacks = callbacks
        return self

    @objc.typedSelector(b"v@:@")
    def menuAction_(self, sender):
        callback = self._callbacks.get(sender.tag())
        if callback:
            GLib.idle_add(callback, None)


class MacOSTray:
    def setup(self, callbacks):
        icon_path = os.path.join(ICONS_DIR, "tray_template.png")

        status_bar = NSStatusBar.systemStatusBar()
        self._status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)

        button = self._status_item.button()
        if os.path.exists(icon_path):
            image = NSImage.alloc().initWithContentsOfFile_(icon_path)
            if image:
                image.setSize_((22, 22))
                image.setTemplate_(True)
                button.setImage_(image)
        else:
            button.setTitle_("Aa")

        # Build tag->callback map and NSMenu
        tag_callbacks = {}
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)

        action_index = 0
        for item in MENU_ITEMS:
            if item is None:
                menu.addItem_(NSMenuItem.separatorItem())
            else:
                title, key = item
                tag_callbacks[action_index] = callbacks[key]
                mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    title, "menuAction:", ""
                )
                mi.setTarget_(self._delegate if hasattr(self, "_delegate") else None)
                mi.setTag_(action_index)
                mi.setEnabled_(True)
                menu.addItem_(mi)
                if key == "pause":
                    self._pause_item = mi
                    self._pause_tag = action_index
                action_index += 1

        self._delegate = _MenuDelegate.alloc().initWithCallbacks_(tag_callbacks)
        # Set target on all items now that delegate exists
        for i in range(menu.numberOfItems()):
            mi = menu.itemAtIndex_(i)
            if not mi.isSeparatorItem():
                mi.setTarget_(self._delegate)

        self._status_item.setMenu_(menu)

    def set_label(self, text):
        pass

    def set_pause_label(self, label):
        self._pause_item.setTitle_(label)
