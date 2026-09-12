import unittest
from pathlib import Path

import cursor_fence


class Event:
    def __init__(self, keysym: str, keycode: int) -> None:
        self.keysym = keysym
        self.keycode = keycode


class CoreTests(unittest.TestCase):
    def test_default_configuration_is_safe(self) -> None:
        config = cursor_fence.CursorFenceApp.default_config()
        self.assertEqual(config["mode"], "window")
        self.assertFalse(config["start_locked"])
        self.assertTrue(config["notifications_enabled"])
        self.assertFalse(config["sync_indicator"])
        self.assertEqual(config["hotkey"]["vk"], 0x91)

    def test_system_language_detection_follows_windows_locale(self) -> None:
        self.assertEqual(cursor_fence.detect_system_language(locale_name="zh-CN"), "zh")
        self.assertEqual(cursor_fence.detect_system_language(locale_name="en-US"), "en")
        self.assertEqual(cursor_fence.detect_system_language(locale_name="ja-JP"), "en")
        self.assertEqual(cursor_fence.detect_system_language(ui_language_id=2052), "zh")
        self.assertEqual(cursor_fence.detect_system_language(ui_language_id=1033), "en")

    def test_hand_edited_boolean_and_integer_values_are_tolerant(self) -> None:
        self.assertTrue(cursor_fence.parse_bool("YES"))
        self.assertFalse(cursor_fence.parse_bool("no", True))
        self.assertTrue(cursor_fence.parse_bool("typo", True))
        self.assertEqual(cursor_fence.parse_int("0x91"), 0x91)
        self.assertEqual(cursor_fence.parse_int("145"), 145)
        self.assertEqual(cursor_fence.parse_int("bad", 7), 7)

    def test_hotkey_display_order(self) -> None:
        modifiers = cursor_fence.MOD_CONTROL | cursor_fence.MOD_ALT | cursor_fence.MOD_SHIFT
        self.assertEqual(cursor_fence.format_hotkey(modifiers, "K"), "Ctrl+Alt+Shift+K")

    def test_key_conversion_for_named_and_character_keys(self) -> None:
        self.assertEqual(cursor_fence.key_from_event(Event("Scroll_Lock", 0x91)), (0x91, "ScrollLock"))
        self.assertEqual(cursor_fence.key_from_event(Event("k", 0x4B)), (0x4B, "K"))
        self.assertIsNone(cursor_fence.key_from_event(Event("Control_L", 0x11)))

    def test_source_startup_command_is_quoted(self) -> None:
        command = cursor_fence.get_startup_command()
        self.assertIn("--startup", command)
        self.assertIn(str(Path(cursor_fence.__file__).resolve()), command)
        self.assertTrue(command.startswith('"'))

    def test_lock_key_metadata_and_colorref(self) -> None:
        self.assertEqual(cursor_fence.LOCK_KEY_INFO[0x91], ("ScrollLock", "Scroll Lock"))
        self.assertEqual(cursor_fence.LOCK_KEY_INFO[0x14], ("CapsLock", "Caps Lock"))
        self.assertEqual(cursor_fence.LOCK_KEY_INFO[0x90], ("NumLock", "Num Lock"))
        self.assertEqual(cursor_fence.colorref("#0f1117"), 0x0017110F)

    def test_monitor_work_area_excludes_taskbar_strip(self) -> None:
        info = cursor_fence.MONITORINFO()
        info.rcMonitor.left, info.rcMonitor.top = 0, 0
        info.rcMonitor.right, info.rcMonitor.bottom = 1920, 1080
        info.rcWork.left, info.rcWork.top = 0, 0
        info.rcWork.right, info.rcWork.bottom = 1920, 1032
        self.assertEqual(cursor_fence.rect_tuple(info.rcWork), (0, 0, 1920, 1032))
        self.assertNotEqual(cursor_fence.rect_tuple(info.rcWork), cursor_fence.rect_tuple(info.rcMonitor))

    def test_rect_coordinates_support_negative_origins_and_mixed_sizes(self) -> None:
        rect = cursor_fence.RECT(-2560, -180, 0, 1260)
        self.assertEqual(cursor_fence.rect_tuple(rect), (-2560, -180, 0, 1260))
        self.assertEqual(rect.right - rect.left, 2560)
        self.assertEqual(rect.bottom - rect.top, 1440)


if __name__ == "__main__":
    unittest.main()
