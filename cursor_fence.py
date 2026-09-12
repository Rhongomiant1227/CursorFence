"""CursorFence - a small Windows cursor clipping utility.

The lock is implemented with the native Win32 ClipCursor API.  It constrains
the cursor rectangle at the OS level and never moves the cursor or injects
mouse input, so mouse DPI, polling/report rate, acceleration and button
events remain under the control of Windows and the mouse hardware.
"""

from __future__ import annotations

import ctypes
import configparser
import json
import locale
import os
import queue
import sys
import threading
import traceback
from pathlib import Path
from ctypes import wintypes
import tkinter as tk
from tkinter import messagebox, ttk


def _locale_language(locale_name: object) -> str | None:
    """Map a locale name to one of the languages supported by the UI."""
    if not locale_name:
        return None
    normalized = str(locale_name).strip().lower().replace("-", "_")
    if normalized.startswith("zh"):
        return "zh"
    if normalized.startswith("en"):
        return "en"
    return None


def detect_system_language(locale_name: object | None = None, ui_language_id: int | None = None) -> str:
    """Return the UI language selected by Windows, with an English fallback.

    Windows exposes the user's display language as a LANGID.  The locale
    fallback keeps this helper usable on older Windows builds and in tests,
    while environment/locale values cover non-Windows tooling that imports
    the module for static checks.
    """
    if ui_language_id is None and locale_name is None:
        try:
            ui_language_id = int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
        except (AttributeError, OSError, TypeError, ValueError):
            ui_language_id = None
    if ui_language_id is not None:
        primary_id = int(ui_language_id) & 0x3FF
        if primary_id == 0x04:  # Chinese (all Windows Chinese variants)
            return "zh"
        if primary_id == 0x09:  # English (all Windows English variants)
            return "en"
        # An explicit Windows display language takes precedence over the
        # process locale.  Unsupported system languages use the documented
        # English fallback rather than accidentally inheriting another locale.
        return "en"
    if locale_name is None:
        candidates: list[object] = []
        try:
            candidates.append(locale.getlocale()[0])
        except (ValueError, TypeError):
            pass
        for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
            candidates.append(os.environ.get(variable))
        for candidate in candidates:
            language = _locale_language(candidate)
            if language:
                return language
    else:
        language = _locale_language(locale_name)
        if language:
            return language
    # English is the neutral fallback for unsupported system languages.
    return "en"


LANGUAGE = detect_system_language()

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": {
        "platform_windows_only": "CursorFence 只能在 Windows 上运行。",
        "tray_show_settings": "显示设置",
        "tray_unlock": "解除鼠标锁定",
        "tray_lock": "锁定鼠标",
        "tray_exit": "退出 CursorFence",
        "tray_status": "CursorFence — {status}",
        "status_active_label": "已锁定",
        "status_inactive_label": "未锁定",
        "status_ready": "准备就绪",
        "detail_ready": "按下快捷键开始锁定",
        "subtitle": "轻量常驻工具 · 快捷键锁定鼠标范围",
        "toggle_now": "立即切换",
        "hotkey_title": "控制快捷键",
        "hotkey_body": "全局生效，即使工具窗口在后台也可以切换",
        "hotkey_hint": "支持 Ctrl / Alt / Shift / Win + 任意主键；默认 ScrollLock",
        "led_sync_active": "让激活状态与 {pretty} 指示灯保持一致",
        "led_sync_generic": "使用锁定键指示灯同步激活状态",
        "led_warning_active": "启用后，程序会同步这个锁定键的键盘灯；可能改变系统当前的 CapsLock / NumLock / ScrollLock 状态。",
        "led_warning_generic": "请将快捷键设为无修饰键的 ScrollLock、CapsLock 或 NumLock，才能使用键盘灯同步。",
        "mode_title": "锁定范围",
        "mode_window": "当前窗口",
        "mode_window_hint": "以按下快捷键时的前台窗口为目标，窗口移动或缩放后会跟随",
        "mode_screen": "当前显示器",
        "mode_screen_hint": "锁定鼠标所在显示器的工作区（不含任务栏）",
        "options_title": "启动与常驻",
        "startup_toggle": "登录 Windows 后自动运行（当前用户）",
        "start_locked_toggle": "程序启动后自动启用锁定",
        "notifications_toggle": "状态切换时显示右下角通知",
        "footer_hint": "关闭窗口会最小化到通知区域。",
        "minimize_tray": "最小化至托盘",
        "disclaimer": "鼠标锁定仅使用 Windows ClipCursor；不会移动或模拟鼠标输入，不会改变 DPI、回报率或加速度。",
        "led_confirm_title": "启用键盘灯同步？",
        "led_confirm_message": "已选择 {pretty}。\n\n启用后：键盘灯亮 = 鼠标已锁定；键盘灯灭 = 鼠标未锁定。\n{consequence}\n\n是否启用？",
        "consequence_caps": "Caps Lock 会继续改变字母大小写。",
        "consequence_num": "Num Lock 会继续改变数字键盘行为。",
        "consequence_scroll": "Scroll Lock 会继续保留其系统切换状态。",
        "tray_failure": "通知区域图标异常，详细信息已写入本地日志",
        "notify_lock": "鼠标已锁定（{mode}）\n按 {hotkey} 解除",
        "notify_unlock": "鼠标锁定已解除",
        "callback_error": "程序遇到异常，详细信息已写入本地日志",
        "startup_enabled": "已启用开机自动运行",
        "startup_disabled": "已关闭开机自动运行",
        "startup_error_title": "无法修改开机启动",
        "startup_error_message": "Windows 拒绝了当前用户的启动项修改。请检查注册表权限后重试。",
        "record_prompt": "按任意键…（Esc 取消）",
        "record_button": "录制快捷键",
        "hotkey_error": "快捷键处理异常，详细信息已写入本地日志",
        "no_target": "没有可锁定的前台窗口",
        "detail_active": "范围：{mode} · 再按 {hotkey} 解除",
        "detail_auto_unlock": "目标窗口已关闭或最小化，已自动解除",
        "clip_failure": "Windows 拒绝了鼠标边界设置",
        "duplicate_instance": "CursorFence 已在运行。请从通知区域图标打开设置。",
        "fatal_error": "CursorFence 遇到未处理错误，已解除鼠标锁定。\n\n错误日志：{path}",
        "check_updates": "检查更新",
        "update_checking": "正在检查更新…",
        "update_unavailable": "暂时无法连接 GitHub 更新服务",
        "update_unavailable_detail": "暂时无法连接 GitHub 更新服务，请稍后重试。",
        "update_dialog_title": "发现新版本",
        "update_dialog_message": "发现 CursorFence {tag}。\n\n是否下载并安装？程序将退出并由 GitHub 官方安装包完成更新。",
        "update_skipped": "已跳过更新（当前 v{version}）",
        "update_latest": "当前已是最新版本 v{version}",
        "update_latest_detail": "当前已是最新版本（v{version}）。",
        "update_downloading": "正在下载 {tag}…",
        "update_download_failed": "更新下载失败，请稍后重试",
        "update_download_failed_detail": "无法下载更新安装包，请检查网络后重试。",
        "update_launch_failed": "无法启动更新安装程序",
        "update_launch_failed_detail": "无法启动更新安装程序。",
        "update_error_title": "检查更新",
        "update_failed_title": "更新失败",
        "config_header": "# CursorFence 用户配置（UTF-8）\n# 修改后重启 CursorFence 后生效。\n\n",
        "config_note": "可直接编辑此文件，重启 CursorFence 后生效。",
    },
    "en": {
        "platform_windows_only": "CursorFence runs on Windows only.",
        "tray_show_settings": "Show settings",
        "tray_unlock": "Unlock mouse",
        "tray_lock": "Lock mouse",
        "tray_exit": "Exit CursorFence",
        "tray_status": "CursorFence — {status}",
        "status_active_label": "Locked",
        "status_inactive_label": "Unlocked",
        "status_ready": "Ready",
        "detail_ready": "Press the hotkey to start locking",
        "subtitle": "A lightweight utility that locks the mouse to a selected area",
        "toggle_now": "Toggle now",
        "hotkey_title": "Control hotkey",
        "hotkey_body": "Works globally, even when this window is in the background",
        "hotkey_hint": "Ctrl / Alt / Shift / Win + any main key; default: ScrollLock",
        "led_sync_active": "Keep the active state in sync with the {pretty} indicator",
        "led_sync_generic": "Use the lock-key indicator to sync the active state",
        "led_warning_active": "When enabled, the app syncs this lock key's keyboard indicator; this may change the current CapsLock / NumLock / ScrollLock state.",
        "led_warning_generic": "Set the hotkey to an unmodified ScrollLock, CapsLock, or NumLock to use keyboard-indicator sync.",
        "mode_title": "Lock range",
        "mode_window": "Current window",
        "mode_window_hint": "Targets the foreground window when the hotkey is pressed and follows moves or resizing",
        "mode_screen": "Current monitor",
        "mode_screen_hint": "Locks the work area of the monitor containing the mouse (excluding the taskbar)",
        "options_title": "Startup and tray",
        "startup_toggle": "Run automatically after signing in to Windows (current user)",
        "start_locked_toggle": "Enable the lock automatically when the app starts",
        "notifications_toggle": "Show a notification when the lock state changes",
        "footer_hint": "Closing the window minimizes CursorFence to the notification area.",
        "minimize_tray": "Minimize to tray",
        "disclaimer": "Mouse locking uses Windows ClipCursor only; it does not move or simulate input or change DPI, polling rate, or acceleration.",
        "led_confirm_title": "Enable keyboard-indicator sync?",
        "led_confirm_message": "Selected {pretty}.\n\nWhen enabled: indicator on = mouse locked; indicator off = mouse unlocked.\n{consequence}\n\nEnable it?",
        "consequence_caps": "Caps Lock will continue to change letter casing.",
        "consequence_num": "Num Lock will continue to change numeric-keypad behavior.",
        "consequence_scroll": "Scroll Lock will retain its normal system toggle behavior.",
        "tray_failure": "The notification-area icon failed; details were written to the local log",
        "notify_lock": "Mouse locked ({mode})\nPress {hotkey} to unlock",
        "notify_unlock": "Mouse lock released",
        "callback_error": "The app encountered an error; details were written to the local log",
        "startup_enabled": "Enabled automatic startup",
        "startup_disabled": "Disabled automatic startup",
        "startup_error_title": "Unable to change startup",
        "startup_error_message": "Windows rejected the startup-entry change for the current user. Check registry permissions and try again.",
        "record_prompt": "Press any key… (Esc cancels)",
        "record_button": "Record hotkey",
        "hotkey_error": "Hotkey processing failed; details were written to the local log",
        "no_target": "No foreground window can be locked",
        "detail_active": "Range: {mode} · Press {hotkey} again to unlock",
        "detail_auto_unlock": "The target window closed or was minimized; lock released",
        "clip_failure": "Windows rejected the mouse-boundary request",
        "duplicate_instance": "CursorFence is already running. Open settings from the notification-area icon.",
        "fatal_error": "CursorFence encountered an unexpected error and released the mouse lock.\n\nError log: {path}",
        "check_updates": "Check for updates",
        "update_checking": "Checking for updates…",
        "update_unavailable": "GitHub update service is temporarily unavailable",
        "update_unavailable_detail": "GitHub update service is temporarily unavailable. Please try again later.",
        "update_dialog_title": "Update available",
        "update_dialog_message": "CursorFence {tag} is available.\n\nDownload and install it now? The app will close and the official GitHub installer will complete the update.",
        "update_skipped": "Update skipped (current v{version})",
        "update_latest": "You are already running the latest version v{version}",
        "update_latest_detail": "You are already running the latest version (v{version}).",
        "update_downloading": "Downloading {tag}…",
        "update_download_failed": "Update download failed; please try again later",
        "update_download_failed_detail": "The update installer could not be downloaded. Check your network and try again.",
        "update_launch_failed": "Could not start the update installer",
        "update_launch_failed_detail": "The update installer could not be started.",
        "update_error_title": "Check for updates",
        "update_failed_title": "Update failed",
        "config_header": "# CursorFence user configuration (UTF-8)\n# Restart CursorFence after editing this file.\n\n",
        "config_note": "You can edit this file directly; restart CursorFence after editing.",
    },
}


def tr(key: str, **values: object) -> str:
    """Translate a user-visible message for the detected system language."""
    template = _TRANSLATIONS.get(LANGUAGE, _TRANSLATIONS["en"]).get(key)
    if template is None:
        template = _TRANSLATIONS["en"].get(key, key)
    return template.format(**values) if values else template


if sys.platform != "win32":
    raise SystemExit(tr("platform_windows_only"))


# Make Win32 coordinates line up with the physical monitor/window coordinates
# on high-DPI and mixed-DPI desktops.  This must happen before creating Tk.
try:
    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2.  Win32's virtual desktop
    # APIs then return one consistent physical-pixel coordinate space across
    # monitors with different resolutions/scales, including negative origins.
    ctypes.windll.user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    ctypes.windll.user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        ctypes.windll.shcore.SetProcessDpiAwareness.restype = ctypes.c_long
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware.argtypes = []
            ctypes.windll.user32.SetProcessDPIAware.restype = wintypes.BOOL
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


user32 = ctypes.windll.user32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
except OSError:
    dwmapi = None
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


# Declare pointer-sized Win32 signatures explicitly. ctypes otherwise uses C
# ``int`` defaults, which can truncate HWNDs and RECT pointers in a 64-bit
# build: the UI would report "locked" while Windows kept the desktop range.
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.ClipCursor.argtypes = [ctypes.POINTER(RECT)]
user32.ClipCursor.restype = wintypes.BOOL
user32.GetClipCursor.argtypes = [ctypes.POINTER(RECT)]
user32.GetClipCursor.restype = wintypes.BOOL
user32.GetKeyState.argtypes = [ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.MessageBeep.argtypes = [wintypes.UINT]
user32.MessageBeep.restype = wintypes.BOOL


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MONITOR_DEFAULTTONEAREST = 0x00000002
VK_LWIN = 0x5B
VK_RWIN = 0x5C
KEYEVENTF_KEYUP = 0x0002
GA_ROOT = 2
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


KEY_NAMES = {
    "Scroll_Lock": (0x91, "ScrollLock"),
    "Pause": (0x13, "Pause"),
    "Escape": (0x1B, "Esc"),
    "Return": (0x0D, "Enter"),
    "Tab": (0x09, "Tab"),
    "BackSpace": (0x08, "Backspace"),
    "space": (0x20, "Space"),
    "Insert": (0x2D, "Insert"),
    "Delete": (0x2E, "Delete"),
    "Home": (0x24, "Home"),
    "End": (0x23, "End"),
    "Prior": (0x21, "PageUp"),
    "Next": (0x22, "PageDown"),
    "Left": (0x25, "Left"),
    "Up": (0x26, "Up"),
    "Right": (0x27, "Right"),
    "Down": (0x28, "Down"),
    "Print": (0x2C, "PrintScreen"),
    "Num_Lock": (0x90, "NumLock"),
    "Caps_Lock": (0x14, "CapsLock"),
    "Menu": (0x5D, "Menu"),
}
for _index in range(1, 25):
    KEY_NAMES[f"F{_index}"] = (0x6F + _index, f"F{_index}")

MODIFIER_KEYSYMS = {
    "Control_L": ("Ctrl", MOD_CONTROL),
    "Control_R": ("Ctrl", MOD_CONTROL),
    "Shift_L": ("Shift", MOD_SHIFT),
    "Shift_R": ("Shift", MOD_SHIFT),
    "Alt_L": ("Alt", MOD_ALT),
    "Alt_R": ("Alt", MOD_ALT),
    "Meta_L": ("Win", MOD_WIN),
    "Meta_R": ("Win", MOD_WIN),
    "Super_L": ("Win", MOD_WIN),
    "Super_R": ("Win", MOD_WIN),
    "Win_L": ("Win", MOD_WIN),
    "Win_R": ("Win", MOD_WIN),
}
MODIFIER_ORDER = (("Ctrl", MOD_CONTROL), ("Alt", MOD_ALT), ("Shift", MOD_SHIFT), ("Win", MOD_WIN))

APP_NAME = "CursorFence"
APP_DISPLAY_NAME = "CursorFence"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
MUTEX_NAME = "Local\\CursorFence.SingleInstance"
LOG_DIRECTORY = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME / "logs"
LOCK_KEY_INFO = {
    0x91: ("ScrollLock", "Scroll Lock"),
    0x14: ("CapsLock", "Caps Lock"),
    0x90: ("NumLock", "Num Lock"),
}
HOTKEY_POLL_MS = 8
# The UI refreshes a moving window boundary at a human-scale interval.  A
# separate native-API watchdog reapplies the last accepted rectangle much
# faster while a lock is active.  Some high-FPS games periodically call
# ClipCursor themselves; keeping this interval short closes most of the race
# in which the cursor could otherwise reach a neighbouring monitor.
BOUNDARY_REFRESH_MS = 40
CURSOR_REAPPLY_MS = 2
NOTIFICATION_DISPLAY_MS = 2600
APP_VERSION = "0.3.0"


def write_error_log(context: str, exc_info: tuple | None = None) -> None:
    """Persist unexpected errors so windowed EXE failures are diagnosable."""
    try:
        LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
        details = "".join(traceback.format_exception(*exc_info)) if exc_info else "No traceback was supplied.\n"
        with (LOG_DIRECTORY / "error.log").open("a", encoding="utf-8") as handle:
            handle.write(f"\n{'=' * 72}\n{context}\n{details}")
    except OSError:
        # Logging must never become a second reason for the utility to stop.
        pass


def resource_path(*parts: str) -> Path:
    """Resolve an asset from source or from PyInstaller's extracted bundle."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def config_file_path() -> Path:
    """Return the user-editable INI location for this build.

    An installed onedir build carries ``installer.marker`` next to its EXE;
    portable builds keep the INI beside the EXE so it can travel with the
    archive.  Source runs use the normal per-user application directory.
    """
    appdata = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "installer.marker").is_file():
            return appdata / "CursorFence.ini"
        return exe_dir / "CursorFence.ini"
    return appdata / "CursorFence.ini"


def parse_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "是", "启用"}:
        return True
    if normalized in {"0", "false", "no", "off", "否", "禁用"}:
        return False
    return default


def parse_int(value, default: int = 0) -> int:
    """Parse decimal or ``0x`` integer values from hand-edited INI files."""
    if isinstance(value, bool):
        return int(value)
    try:
        text = str(value).strip()
        try:
            return int(text, 0)
        except ValueError:
            return int(text, 10)
    except (TypeError, ValueError):
        return default


def get_top_level_hwnd(widget: tk.Tk) -> int:
    hwnd = int(widget.winfo_id())
    return int(user32.GetAncestor(hwnd, GA_ROOT) or hwnd)


def colorref(hex_color: str) -> int:
    """Convert #RRGGBB into the COLORREF byte order used by DWM."""
    value = hex_color.removeprefix("#")
    red, green, blue = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)


def apply_dark_window_chrome(widget: tk.Tk) -> None:
    """Remove the light native title bar/border while retaining normal controls."""
    if dwmapi is None:
        return
    try:
        hwnd = get_top_level_hwnd(widget)
        dark = ctypes.c_int(1)
        border = wintypes.DWORD(colorref("#0f1117"))
        caption = wintypes.DWORD(colorref("#0f1117"))
        text = wintypes.DWORD(colorref("#f4f7fb"))
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), ctypes.sizeof(dark))
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ctypes.byref(border), ctypes.sizeof(border))
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption), ctypes.sizeof(caption))
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text), ctypes.sizeof(text))
    except Exception:
        # A plain native title bar remains a valid fallback on older Windows.
        pass


def lock_key_toggle_state(vk: int) -> bool:
    """Return the LED/toggle state of ScrollLock, CapsLock or NumLock."""
    return bool(user32.GetKeyState(vk) & 0x0001)


def set_cursor_clip(rect: RECT | None) -> bool:
    """Apply or release the process-wide cursor clip rectangle."""
    if rect is None:
        return bool(user32.ClipCursor(None))
    return bool(user32.ClipCursor(ctypes.byref(rect)))


def get_cursor_clip() -> tuple[int, int, int, int] | None:
    rect = RECT()
    if not user32.GetClipCursor(ctypes.byref(rect)):
        return None
    return rect_tuple(rect)


def flip_lock_key(vk: int) -> None:
    """Explicitly flip a supported lock key after a user asks to sync LEDs."""
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def get_startup_command() -> str:
    """Return a quoted command that launches this executable/script silently."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --startup'
    return f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve()}" --startup'


def startup_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except (OSError, ImportError):
        return False


def set_startup_enabled(enabled: bool) -> bool:
    """Toggle current-user startup without requiring elevation."""
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, get_startup_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except (OSError, ImportError):
        return False


def acquire_single_instance() -> wintypes.HANDLE | None:
    """Keep one process alive and return its mutex handle for its lifetime."""
    kernel32.SetLastError(0)
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    error = ctypes.get_last_error()
    if not handle or error == 183:  # ERROR_ALREADY_EXISTS
        if handle:
            kernel32.CloseHandle(handle)
        return None
    return handle


def key_from_event(event: tk.Event) -> tuple[int, str] | None:
    """Resolve a Tk key event into a Windows virtual key and readable label."""
    keysym = str(event.keysym)
    if keysym in MODIFIER_KEYSYMS:
        return None
    if keysym in KEY_NAMES:
        return KEY_NAMES[keysym]
    keycode = int(getattr(event, "keycode", 0) or 0)
    if 0x01 <= keycode <= 0xFE:
        # Tk reports the Windows virtual-key code in keycode on Windows.
        if len(keysym) == 1 and keysym.isprintable():
            label = keysym.upper()
        else:
            label = keysym.replace("_", " ")
        return keycode, label
    if len(keysym) == 1:
        vk = int(user32.VkKeyScanW(ord(keysym))) & 0xFF
        return vk, keysym.upper()
    return None


def format_hotkey(modifiers: int, key_label: str) -> str:
    parts = [name for name, flag in MODIFIER_ORDER if modifiers & flag]
    parts.append(key_label)
    return "+".join(parts)


def rect_tuple(rect: RECT) -> tuple[int, int, int, int]:
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


class ToggleRow(tk.Frame):
    """A compact, theme-independent switch used for boolean settings.

    ``ttk.Checkbutton`` renders a native indicator whose appearance depends on
    the active Windows theme (and can show the distracting black ``X`` seen in
    older builds).  This small canvas-based control keeps the UI consistent,
    while still exposing the ``configure(state=...)`` interface used by the
    settings logic.
    """

    TRACK_WIDTH = 42
    TRACK_HEIGHT = 24

    def __init__(
        self,
        master,
        *,
        variable: tk.BooleanVar,
        text: str | None = None,
        textvariable: tk.StringVar | None = None,
        command=None,
        **kwargs,
    ) -> None:
        background = kwargs.pop("background", "#171b24")
        foreground = kwargs.pop("foreground", "#c2c9d6")
        font = kwargs.pop("font", ("Segoe UI", 9))
        super().__init__(master, bg=background, highlightthickness=0, bd=0, **kwargs)
        self._background = background
        self._foreground = foreground
        self._font = font
        self._variable = variable
        self._command = command
        self._state = "normal"

        self._canvas = tk.Canvas(
            self,
            width=self.TRACK_WIDTH,
            height=self.TRACK_HEIGHT,
            bg=background,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._canvas.pack(side="left", padx=(0, 10))
        self._label = tk.Label(
            self,
            text=text,
            textvariable=textvariable,
            bg=background,
            fg=foreground,
            activebackground=background,
            activeforeground=foreground,
            font=font,
            anchor="w",
            cursor="hand2",
        )
        self._label.pack(side="left", fill="x", expand=True)

        for widget in (self, self._canvas, self._label):
            widget.bind("<Button-1>", self._on_click, add="+")
        self._trace_id = self._variable.trace_add("write", self._on_variable_changed)
        self._draw()

    def _on_variable_changed(self, *_args) -> None:
        self._draw()

    def _draw(self) -> None:
        if not self.winfo_exists():
            return
        self._canvas.delete("all")
        enabled = self._state != "disabled"
        value = bool(self._variable.get())
        if not enabled:
            track = "#242a36"
            knob = "#657084"
        elif value:
            track = "#26b976"
            knob = "#f4fffa"
        else:
            track = "#303848"
            knob = "#9aa5b5"

        # Draw a pill-shaped track without relying on platform-specific ttk
        # theme assets.
        self._canvas.create_oval(1, 1, 21, 23, fill=track, outline=track)
        self._canvas.create_rectangle(11, 1, 31, 23, fill=track, outline=track)
        self._canvas.create_oval(21, 1, 41, 23, fill=track, outline=track)
        knob_left = 4 if not value else 21
        self._canvas.create_oval(knob_left, 4, knob_left + 16, 20, fill=knob, outline="")
        self._canvas.configure(cursor="hand2" if enabled else "arrow")
        self._label.configure(
            fg=self._foreground if enabled else "#657084",
            cursor="hand2" if enabled else "arrow",
        )

    def _on_click(self, _event=None) -> str:
        if self._state == "disabled":
            return "break"
        self._variable.set(not bool(self._variable.get()))
        if self._command is not None:
            self._command()
        return "break"

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        if state is not None:
            self._state = str(state)
            self._draw()
        return super().configure(cnf, **kwargs)

    config = configure


class TrayController:
    """Own the notification-area icon without making Tk cross-thread unsafe."""

    def __init__(self, app) -> None:
        self.app = app
        self.pystray = None
        self.Image = None
        self.ImageDraw = None
        self.icon = None
        self.thread: threading.Thread | None = None
        self.notification_clear_after_id: str | None = None
        self.available = False
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError as error:
            write_error_log("加载通知区域依赖失败", (type(error), error, error.__traceback__))
            return
        self.pystray = pystray
        self.Image = Image
        self.ImageDraw = ImageDraw
        try:
            self.icon = pystray.Icon(
                APP_NAME,
                self.make_image(False),
                APP_DISPLAY_NAME,
                self.make_menu(),
            )
            self.available = True
        except Exception:
            write_error_log("创建通知区域图标失败", sys.exc_info())

    def make_image(self, active: bool):
        """Draw the simple cursor-in-boundary utility mark."""
        background = "#102b26" if active else "#182236"
        rim = "#2ebd83" if active else "#2f405b"
        inner = "#194436" if active else "#22314b"
        boundary = "#5cf0a7" if active else "#93a4bd"
        image = self.Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = self.ImageDraw.Draw(image)
        draw.rounded_rectangle((3, 3, 60, 60), radius=15, fill=background, outline=rim, width=2)
        draw.rounded_rectangle((7, 7, 56, 56), radius=12, outline=inner, width=1)
        draw.line((15, 24, 15, 15, 24, 15), fill=boundary, width=4, joint="curve")
        draw.line((40, 15, 49, 15, 49, 24), fill=boundary, width=4, joint="curve")
        draw.line((15, 40, 15, 49, 24, 49), fill=boundary, width=4, joint="curve")
        draw.line((40, 49, 49, 49, 49, 40), fill=boundary, width=4, joint="curve")
        cursor = ((25, 16), (25, 43), (31, 36), (37, 48), (43, 45), (37, 33), (47, 33))
        shadow = tuple((x + 2, y + 2) for x, y in cursor)
        draw.polygon(shadow, fill="#090617")
        draw.polygon(cursor, fill="#f5f8fc", outline="#ffffff")
        draw.line((28, 21, 28, 35), fill="#b8d3f2", width=2)
        draw.ellipse((48, 8, 56, 16), fill="#75ffaf" if active else "#71839e", outline=background, width=1)
        return image

    def make_menu(self):
        item = self.pystray.MenuItem
        return self.pystray.Menu(
            item(tr("tray_show_settings"), self.show_window, default=True),
            item(lambda _: tr("tray_unlock" if self.app.active else "tray_lock"), self.toggle_lock),
            self.pystray.Menu.SEPARATOR,
            item(tr("tray_exit"), self.quit_app),
        )

    def start(self) -> None:
        if not self.available:
            return
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run_icon, name="tray-icon", daemon=True)
        self.thread.start()

    def _run_icon(self) -> None:
        try:
            self.icon.run()
        except BaseException:
            write_error_log("通知区域图标线程异常", sys.exc_info())
            try:
                self.app.root.after(0, self.app.on_tray_failure)
            except tk.TclError:
                pass

    def show_window(self, *_args) -> None:
        self.app.root.after(0, self.app.show_window)

    def toggle_lock(self, *_args) -> None:
        self.app.root.after(0, self.app.toggle_lock)

    def quit_app(self, *_args) -> None:
        self.app.root.after(0, self.app.close)

    def refresh(self, active: bool) -> None:
        if not self.available or self.icon is None:
            return
        try:
            self.icon.icon = self.make_image(active)
            self.icon.title = tr(
                "tray_status",
                status=tr("status_active_label" if active else "status_inactive_label"),
            )
            self.icon.update_menu()
        except Exception:
            # The tray backend can still be starting or stopping. Its next
            # refresh will use the current state, so this needs no escalation.
            write_error_log("通知区域图标状态刷新失败", sys.exc_info())

    def notify(self, message: str, title: str | None = None) -> bool:
        """Show a native notification-area balloon when the backend supports it.

        pystray maps this to ``Shell_NotifyIcon(NIM_MODIFY, NIF_INFO)`` on
        Windows.  That API is available on Windows versions well before the
        Windows 10 toast system, so Windows 7/8 use the classic compatible
        balloon while newer systems may present it as a toast/notification.
        Notification failure must never affect locking itself.
        """
        if not self.available or self.icon is None:
            return False
        try:
            # Clear the previous balloon first.  Reusing the same tray icon
            # then makes a rapid lock/unlock sequence show the latest state
            # instead of leaving an outdated notification visible.
            self.clear_notification()
            self.icon.notify(message, title or APP_DISPLAY_NAME)
            # Windows controls the native balloon timeout on some versions and
            # ignores the legacy uTimeout field on others.  Explicitly remove
            # it after a short interval so the behavior is consistent across
            # shells, including Windows 7/8 and vendor-modified desktops.
            self.notification_clear_after_id = self.app.root.after(
                NOTIFICATION_DISPLAY_MS,
                self._clear_notification_timer,
            )
            return True
        except Exception:
            write_error_log("状态通知发送失败", sys.exc_info())
            return False

    def _clear_notification_timer(self) -> None:
        self.notification_clear_after_id = None
        self.clear_notification()

    def clear_notification(self) -> None:
        """Best-effort removal of the current native notification balloon."""
        if self.notification_clear_after_id is not None:
            try:
                self.app.root.after_cancel(self.notification_clear_after_id)
            except tk.TclError:
                pass
            self.notification_clear_after_id = None
        if not self.available or self.icon is None:
            return
        try:
            self.icon.remove_notification()
        except Exception:
            write_error_log("状态通知清理失败", sys.exc_info())

    def stop(self) -> None:
        self.clear_notification()
        if not self.available or self.icon is None:
            return
        try:
            self.icon.stop()
        except Exception:
            pass


class HotkeyWorker:
    """Read a global hotkey on a worker thread without touching Tk.

    RegisterHotKey is useful when Windows accepts a key, but unmodified lock
    keys are inconsistent across Windows builds.  The worker therefore uses
    GetAsyncKeyState edge detection as the single source of truth.  Events are
    delivered to the Tk thread through a queue, so no Win32 callback ever
    enters Tk or mutates application state from another thread.
    """

    def __init__(self, config_getter, event_queue: queue.Queue) -> None:
        self.config_getter = config_getter
        self.event_queue = event_queue
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, name="hotkey-worker", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        thread = self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        self.thread = None

    @staticmethod
    def key_down(vk: int) -> bool:
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    def combination_down(self, modifiers: int, vk: int) -> bool:
        modifier_vks = (
            (MOD_CONTROL, (0x11, 0xA2, 0xA3)),
            (MOD_ALT, (0x12, 0xA4, 0xA5)),
            (MOD_SHIFT, (0x10, 0xA0, 0xA1)),
            (MOD_WIN, (VK_LWIN, VK_RWIN)),
        )
        for flag, candidates in modifier_vks:
            if modifiers & flag and not any(self.key_down(candidate) for candidate in candidates):
                return False
        return self.key_down(vk)

    def run(self) -> None:
        previous = False
        previous_toggle: bool | None = None
        try:
            while not self.stop_event.is_set():
                hotkey = self.config_getter()
                modifiers = int(hotkey.get("modifiers", 0))
                vk = int(hotkey.get("vk", 0))
                if modifiers == 0 and vk in LOCK_KEY_INFO:
                    # Lock-key toggle state is stable even when the short
                    # down bit is consumed before another process samples it.
                    current_toggle = lock_key_toggle_state(vk)
                    if previous_toggle is None:
                        previous_toggle = current_toggle
                    elif current_toggle != previous_toggle:
                        previous_toggle = current_toggle
                        self.event_queue.put_nowait(("toggle", int(user32.GetForegroundWindow() or 0)))
                    previous = False
                else:
                    previous_toggle = None
                    down = self.combination_down(modifiers, vk)
                    if down and not previous:
                        self.event_queue.put_nowait(("toggle", int(user32.GetForegroundWindow() or 0)))
                    previous = down
                self.stop_event.wait(HOTKEY_POLL_MS / 1000.0)
        except BaseException:
            write_error_log("全局快捷键线程异常", sys.exc_info())


class CursorBoundaryGuard:
    """Reapply the active ClipCursor rectangle outside the Tk event loop.

    Some high-FPS games briefly replace or release the process-wide cursor
    clip while processing a frame.  A 40 ms ``after`` callback leaves enough
    time for a fast pointer movement and click to escape.  This guard only
    runs while a lock is active, checks the native rectangle every few
    milliseconds, and reapplies the cached boundary when another process has
    changed it.  It never moves the pointer, injects input, or installs a
    mouse hook.  Windows scheduling and a game that writes the clip at the
    same instant can still win a small race, so this is best-effort by design.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._boundary: tuple[int, int, int, int] | None = None
        self._active = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="cursor-boundary-guard", daemon=True)
        self._thread.start()

    def set_boundary(self, boundary: tuple[int, int, int, int]) -> bool:
        """Publish and immediately apply a new boundary atomically."""
        with self._lock:
            self._boundary = boundary
            self._active = True
            left, top, right, bottom = boundary
            return set_cursor_clip(RECT(left, top, right, bottom))

    def clear(self) -> None:
        """Stop reapplication and release the native clip without a race."""
        with self._lock:
            self._active = False
            self._boundary = None
            set_cursor_clip(None)

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        self._thread = None
        self.clear()

    def _run(self) -> None:
        try:
            while not self._stop_event.wait(CURSOR_REAPPLY_MS / 1000.0):
                # Holding the lock across the native call prevents a stale
                # worker call from happening after ``clear`` has released the
                # system clip during deactivation.
                with self._lock:
                    if not self._active or self._boundary is None:
                        continue
                    boundary = self._boundary
                    if get_cursor_clip() == boundary:
                        continue
                    left, top, right, bottom = boundary
                    set_cursor_clip(RECT(left, top, right, bottom))
        except BaseException:
            write_error_log("光标边界看门狗线程异常", sys.exc_info())


class CursorFenceApp:
    """Application state and native cursor-boundary operations."""

    def __init__(
        self,
        root: tk.Tk,
        startup_foreground: int | None = None,
        launched_at_startup: bool = False,
    ) -> None:
        self.root = root
        # Capture the foreground window before this utility has a chance to
        # become active.  This makes "启动时自动启用" useful in window mode
        # instead of accidentally locking to the utility's own settings window.
        self.startup_foreground = startup_foreground
        self.launched_at_startup = launched_at_startup
        self.config_path = config_file_path()
        appdata = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
        # Older releases stored JSON under APPDATA even for portable builds;
        # keep both locations discoverable so upgrading never loses settings.
        self.legacy_config_paths = [self.config_path.with_name("config.json")]
        legacy_appdata = appdata / "config.json"
        if legacy_appdata not in self.legacy_config_paths:
            self.legacy_config_paths.append(legacy_appdata)
        self.config = self.load_config()
        self.active = False
        self.target_hwnd: int | None = None
        self.self_hwnd = 0
        self.last_external_foreground: int | None = startup_foreground
        self.last_rect: tuple[int, int, int, int] | None = None
        # In screen mode the monitor is captured once when locking starts.
        # Re-reading the monitor from the cursor on every watchdog tick can
        # select a different display after the cursor reaches an edge.
        self.screen_boundary: tuple[int, int, int, int] | None = None
        self.boundary_guard = CursorBoundaryGuard()
        self.hotkey_events: queue.Queue = queue.Queue()
        self.hotkey_worker = HotkeyWorker(lambda: self.config.get("hotkey", {}), self.hotkey_events)
        self.hotkey_poll_after_id: str | None = None
        self.indicator_sync_after_id: str | None = None
        self.hidden_to_tray = False
        self.closing = False
        self.recording = False
        self.record_modifiers = 0
        self.record_modifier_names: set[str] = set()
        self.status_message = tr("status_ready")
        self.installed_build = bool(getattr(sys, "frozen", False) and (Path(sys.executable).resolve().parent / "installer.marker").is_file())
        self.update_check_in_progress = False

        self.mode_var = tk.StringVar(value=self.config["mode"])
        self.start_locked_var = tk.BooleanVar(value=self.config.get("start_locked", False))
        self.startup_var = tk.BooleanVar(value=startup_enabled())
        self.notifications_var = tk.BooleanVar(value=self.config.get("notifications_enabled", True))
        self.sync_indicator_var = tk.BooleanVar(value=self.config.get("sync_indicator", False))
        self.sync_indicator_label_var = tk.StringVar(value=tr("led_sync_generic"))
        self.indicator_warning_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value=tr("status_inactive_label"))
        self.detail_var = tk.StringVar(value=tr("detail_ready"))
        self.hotkey_var = tk.StringVar(value=self.config["hotkey"]["label"])
        self.record_button_var = tk.StringVar(value=tr("record_button"))
        self.build_ui()
        self.self_hwnd = get_top_level_hwnd(self.root)
        self.tray = TrayController(self)
        self.root.report_callback_exception = self.report_callback_exception
        self.root.after(20, self.apply_window_branding)
        self.root.after(100, self.start_services)
        self.root.after(250, self.watch_lock)
        if self.installed_build:
            # Keep startup responsive; GitHub may be unavailable or slow.
            # This also runs for the optional Windows startup launch, matching
            # the user's "check on every startup" preference.
            self.root.after(1400, self.check_updates_startup)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

    @staticmethod
    def default_config() -> dict:
        return {
            "hotkey": {"modifiers": 0, "vk": 0x91, "label": "ScrollLock"},
            "mode": "window",
            "start_locked": False,
            "notifications_enabled": True,
            "sync_indicator": False,
        }

    def start_services(self) -> None:
        self.tray.start()
        self.install_hotkey()
        self.boundary_guard.start()
        self.tray.refresh(False)
        self.hotkey_poll_after_id = self.root.after(20, self.poll_hotkey_events)
        if self.indicator_sync_supported() and self.sync_indicator_var.get():
            self.start_indicator_sync(delay_ms=350)

    def apply_window_branding(self) -> None:
        """Use the app icon and a dark DWM title bar instead of Tk's white chrome."""
        try:
            icon = resource_path("resources", "CursorFence.ico")
            if icon.is_file():
                self.root.iconbitmap(default=str(icon))
        except tk.TclError:
            pass
        apply_dark_window_chrome(self.root)

    def load_config(self) -> dict:
        config = self.default_config()
        try:
            saved = None
            if self.config_path.is_file():
                parser = configparser.ConfigParser(interpolation=None)
                parser.read(self.config_path, encoding="utf-8-sig")
                hot = parser["hotkey"] if parser.has_section("hotkey") else {}
                general = parser["general"] if parser.has_section("general") else parser.defaults()
                saved = {
                    "hotkey": {
                        "modifiers": parse_int(hot.get("modifiers"), config["hotkey"]["modifiers"]),
                        "vk": parse_int(hot.get("vk"), config["hotkey"]["vk"]),
                        "label": hot.get("label", config["hotkey"]["label"]),
                    },
                    "mode": general.get("mode", config["mode"]),
                    "start_locked": parse_bool(general.get("start_locked"), config["start_locked"]),
                    "notifications_enabled": parse_bool(general.get("notifications_enabled"), True),
                    "sync_indicator": parse_bool(general.get("sync_indicator"), False),
                }
            else:
                legacy_path = next((path for path in self.legacy_config_paths if path.is_file()), None)
                if legacy_path is None:
                    return config
                # Upgrade legacy JSON settings transparently on next save.
                with legacy_path.open("r", encoding="utf-8-sig") as handle:
                    saved = json.load(handle)
            if isinstance(saved, dict):
                hotkey = saved.get("hotkey", {})
                vk = parse_int(hotkey.get("vk"), config["hotkey"]["vk"]) if isinstance(hotkey, dict) else config["hotkey"]["vk"]
                if isinstance(hotkey, dict) and 0 < vk < 256:
                    config["hotkey"].update(
                        {
                            "modifiers": parse_int(hotkey.get("modifiers"), 0) & (MOD_ALT | MOD_CONTROL | MOD_SHIFT | MOD_WIN),
                            "vk": vk,
                            "label": str(hotkey.get("label", "ScrollLock")) or "ScrollLock",
                        }
                    )
                if saved.get("mode") in ("window", "screen"):
                    config["mode"] = saved["mode"]
                config["start_locked"] = parse_bool(saved.get("start_locked", False))
                # New installations default notifications on.  Keeping the
                # default here also upgrades older config files seamlessly.
                config["notifications_enabled"] = parse_bool(saved.get("notifications_enabled", True), True)
                config["sync_indicator"] = parse_bool(saved.get("sync_indicator", False))
        except (OSError, ValueError, TypeError, configparser.Error, json.JSONDecodeError):
            write_error_log(f"读取配置失败：{self.config_path}")
            pass
        return config

    def save_config(self) -> None:
        self.config["mode"] = self.mode_var.get()
        self.config["start_locked"] = bool(self.start_locked_var.get())
        self.config["notifications_enabled"] = bool(self.notifications_var.get())
        self.config["sync_indicator"] = bool(self.sync_indicator_var.get())
        temporary = self.config_path.with_suffix(".tmp")
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            parser = configparser.ConfigParser(interpolation=None)
            parser["general"] = {
                "mode": self.config["mode"],
                "start_locked": "true" if self.config["start_locked"] else "false",
                "notifications_enabled": "true" if self.config["notifications_enabled"] else "false",
                "sync_indicator": "true" if self.config["sync_indicator"] else "false",
            }
            hotkey = self.config.get("hotkey", {})
            parser["hotkey"] = {
                "modifiers": str(int(hotkey.get("modifiers", 0))),
                "vk": str(int(hotkey.get("vk", 0x91))),
                "label": str(hotkey.get("label", "ScrollLock")),
            }
            parser["about"] = {"version": APP_VERSION, "note": tr("config_note")}
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                handle.write(tr("config_header"))
                parser.write(handle)
            temporary.replace(self.config_path)
        except (OSError, configparser.Error):
            write_error_log(f"保存配置失败：{self.config_path}", sys.exc_info())
            try:
                temporary.unlink()
            except OSError:
                pass

    def build_ui(self) -> None:
        self.root.title(APP_DISPLAY_NAME)
        # Keep every control visible without a scroll bar. This is still a
        # compact utility window, but it needs room for the startup options.
        self.root.geometry("560x850")
        self.root.minsize(520, 800)
        self.root.configure(bg="#0f1117")
        self.root.option_add("*Font", ("Segoe UI", 10))

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background="#0f1117")
        style.configure("Card.TFrame", background="#171b24")
        style.configure("Title.TLabel", background="#0f1117", foreground="#f4f7fb", font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background="#0f1117", foreground="#8791a3", font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background="#171b24", foreground="#f4f7fb", font=("Segoe UI", 11, "bold"))
        style.configure("Body.TLabel", background="#171b24", foreground="#c2c9d6", font=("Segoe UI", 9))
        style.configure("Status.TLabel", background="#171b24", foreground="#67e8a5", font=("Segoe UI", 15, "bold"))
        style.configure("Hint.TLabel", background="#171b24", foreground="#8791a3", font=("Segoe UI", 9))
        style.configure("Warning.TLabel", background="#171b24", foreground="#f3c969", font=("Segoe UI", 9))
        style.configure("Primary.TButton", background="#4f7cff", foreground="white", borderwidth=0, padding=(14, 8), font=("Segoe UI", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#6a91ff"), ("disabled", "#3b4b72")])
        style.configure("Secondary.TButton", background="#252c3a", foreground="#e6ebf3", borderwidth=0, padding=(12, 7))
        style.map("Secondary.TButton", background=[("active", "#30394b")])
        style.configure("Mode.TRadiobutton", background="#171b24", foreground="#e6ebf3", font=("Segoe UI", 10), padding=(0, 4))
        style.map("Mode.TRadiobutton", background=[("active", "#171b24")], foreground=[("disabled", "#657084")])
        outer = ttk.Frame(self.root, style="App.TFrame", padding=(28, 24, 28, 20))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="App.TFrame")
        header.pack(fill="x")
        title_block = ttk.Frame(header, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text=APP_DISPLAY_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_block, text=tr("subtitle"), style="Subtitle.TLabel").pack(anchor="w", pady=(3, 18))

        status_card = ttk.Frame(outer, style="Card.TFrame", padding=(18, 16))
        status_card.pack(fill="x", pady=(0, 12))
        top = ttk.Frame(status_card, style="Card.TFrame")
        top.pack(fill="x")
        self.status_dot = tk.Canvas(top, width=13, height=13, bg="#171b24", highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 9), pady=(2, 0))
        self.status_dot_id = self.status_dot.create_oval(2, 2, 11, 11, fill="#697386", outline="")
        ttk.Label(top, textvariable=self.status_var, style="Status.TLabel").pack(side="left")
        ttk.Button(top, text=tr("toggle_now"), style="Primary.TButton", command=self.toggle_lock).pack(side="right")
        ttk.Label(status_card, textvariable=self.detail_var, style="Hint.TLabel").pack(anchor="w", pady=(9, 0))

        hotkey_card = ttk.Frame(outer, style="Card.TFrame", padding=(18, 16))
        hotkey_card.pack(fill="x", pady=(0, 12))
        ttk.Label(hotkey_card, text=tr("hotkey_title"), style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(hotkey_card, text=tr("hotkey_body"), style="Body.TLabel").pack(anchor="w", pady=(4, 12))
        hotkey_line = ttk.Frame(hotkey_card, style="Card.TFrame")
        hotkey_line.pack(fill="x")
        key_display = tk.Label(hotkey_line, textvariable=self.hotkey_var, bg="#0f1117", fg="#f4f7fb", font=("Consolas", 11, "bold"), padx=12, pady=8, anchor="w")
        key_display.pack(side="left", fill="x", expand=True)
        self.record_button = ttk.Button(hotkey_line, textvariable=self.record_button_var, style="Secondary.TButton", command=self.begin_recording)
        self.record_button.pack(side="right", padx=(10, 0))
        ttk.Label(hotkey_card, text=tr("hotkey_hint"), style="Hint.TLabel").pack(anchor="w", pady=(10, 0))
        self.sync_indicator_check = ToggleRow(
            hotkey_card,
            variable=self.sync_indicator_var,
            textvariable=self.sync_indicator_label_var,
            command=self.on_sync_indicator_changed,
            background="#171b24",
            foreground="#c2c9d6",
            font=("Segoe UI", 9),
        )
        self.sync_indicator_check.pack(anchor="w", pady=(12, 0))
        ttk.Label(hotkey_card, textvariable=self.indicator_warning_var, style="Warning.TLabel", wraplength=470, justify="left").pack(anchor="w", pady=(4, 0))

        mode_card = ttk.Frame(outer, style="Card.TFrame", padding=(18, 16))
        mode_card.pack(fill="x", pady=(0, 12))
        ttk.Label(mode_card, text=tr("mode_title"), style="CardTitle.TLabel").pack(anchor="w")
        ttk.Radiobutton(mode_card, text=tr("mode_window"), value="window", variable=self.mode_var, style="Mode.TRadiobutton", command=self.on_mode_changed).pack(anchor="w", pady=(8, 0))
        ttk.Label(mode_card, text=tr("mode_window_hint"), style="Hint.TLabel").pack(anchor="w", padx=(25, 0))
        ttk.Radiobutton(mode_card, text=tr("mode_screen"), value="screen", variable=self.mode_var, style="Mode.TRadiobutton", command=self.on_mode_changed).pack(anchor="w", pady=(10, 0))
        ttk.Label(mode_card, text=tr("mode_screen_hint"), style="Hint.TLabel").pack(anchor="w", padx=(25, 0))

        options = ttk.Frame(outer, style="Card.TFrame", padding=(18, 12))
        options.pack(fill="x")
        ttk.Label(options, text=tr("options_title"), style="CardTitle.TLabel").pack(anchor="w", pady=(0, 5))
        ToggleRow(
            options,
            text=tr("startup_toggle"),
            variable=self.startup_var,
            command=self.on_startup_changed,
            background="#171b24",
            foreground="#c2c9d6",
            font=("Segoe UI", 9),
        ).pack(anchor="w")
        ToggleRow(
            options,
            text=tr("start_locked_toggle"),
            variable=self.start_locked_var,
            command=self.save_config,
            background="#171b24",
            foreground="#c2c9d6",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(6, 0))
        ToggleRow(
            options,
            text=tr("notifications_toggle"),
            variable=self.notifications_var,
            command=self.on_notifications_changed,
            background="#171b24",
            foreground="#c2c9d6",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(6, 0))

        footer = ttk.Frame(outer, style="App.TFrame")
        footer.pack(fill="x", pady=(14, 0))
        ttk.Label(footer, text=tr("footer_hint"), style="Subtitle.TLabel").pack(side="left")
        ttk.Button(footer, text=tr("minimize_tray"), style="Secondary.TButton", command=self.hide_window).pack(side="right")
        if self.installed_build:
            ttk.Button(footer, text=tr("check_updates"), style="Secondary.TButton", command=self.check_updates_manual).pack(side="right", padx=(0, 8))
        ttk.Label(outer, text=tr("disclaimer"), style="Subtitle.TLabel", wraplength=490, justify="left").pack(anchor="w", pady=(10, 0))
        self.update_indicator_sync_ui()

    def _fetch_update(self, manual: bool = False) -> None:
        """Fetch release metadata off the Tk thread (installer builds only)."""
        if not self.installed_build or self.update_check_in_progress or self.closing:
            return
        self.update_check_in_progress = True
        self.detail_var.set(tr("update_checking"))

        def worker() -> None:
            try:
                from updater import fetch_latest_release, is_newer_version

                release = fetch_latest_release()
                newer = bool(release and is_newer_version(APP_VERSION, release.tag))
                self.root.after(0, lambda: self._update_result(release, newer, manual))
            except Exception:
                write_error_log("检查更新失败", sys.exc_info())
                self.root.after(0, lambda: self._update_result(None, False, manual))

        threading.Thread(target=worker, name="update-check", daemon=True).start()

    def check_updates_startup(self) -> None:
        try:
            from updater import cleanup_old_downloads

            cleanup_old_downloads()
        except Exception:
            write_error_log("清理旧更新文件失败", sys.exc_info())
        self._fetch_update(manual=False)

    def check_updates_manual(self) -> None:
        self._fetch_update(manual=True)

    def _update_result(self, release, newer: bool, manual: bool) -> None:
        self.update_check_in_progress = False
        if self.closing:
            return
        if not release:
            self.detail_var.set(tr("update_unavailable") if manual else self.status_message)
            if manual:
                messagebox.showwarning(tr("update_error_title"), tr("update_unavailable_detail"), parent=self.root)
            return
        if not newer:
            self.detail_var.set(tr("update_latest", version=APP_VERSION))
            if manual:
                messagebox.showinfo(tr("update_error_title"), tr("update_latest_detail", version=APP_VERSION), parent=self.root)
            return
        if not messagebox.askyesno(
            tr("update_dialog_title"),
            tr("update_dialog_message", tag=release.tag),
            parent=self.root,
        ):
            self.detail_var.set(tr("update_skipped", version=APP_VERSION))
            return
        self._download_update(release)

    def _download_update(self, release) -> None:
        self.update_check_in_progress = True
        self.detail_var.set(tr("update_downloading", tag=release.tag))

        def worker() -> None:
            try:
                from updater import download_installer

                installer = download_installer(release)
                self.root.after(0, lambda: self._launch_update(installer))
            except Exception:
                write_error_log("下载更新失败", sys.exc_info())
                self.root.after(0, lambda: self._update_download_failed())

        threading.Thread(target=worker, name="update-download", daemon=True).start()

    def _update_download_failed(self) -> None:
        self.update_check_in_progress = False
        if not self.closing:
            self.detail_var.set(tr("update_download_failed"))
            messagebox.showerror(tr("update_failed_title"), tr("update_download_failed_detail"), parent=self.root)

    def _launch_update(self, installer: Path) -> None:
        try:
            from updater import launch_installer

            launch_installer(installer)
            # close() releases ClipCursor, stops worker threads and exits;
            # Inno Setup then replaces the installed files silently.
            self.close()
        except Exception:
            self.update_check_in_progress = False
            write_error_log("启动更新安装程序失败", sys.exc_info())
            self.detail_var.set(tr("update_launch_failed"))
            messagebox.showerror(tr("update_failed_title"), tr("update_launch_failed_detail"), parent=self.root)

    def on_mode_changed(self) -> None:
        self.save_config()
        if self.active:
            if self.mode_var.get() == "screen":
                # Switching to screen mode while active captures the monitor
                # under the cursor at the moment of the switch.
                self.screen_boundary = self.get_screen_boundary()
            else:
                self.screen_boundary = None
            self.apply_current_boundary(force=True)

    def indicator_sync_supported(self) -> bool:
        hotkey = self.config.get("hotkey", {})
        return int(hotkey.get("modifiers", 0)) == 0 and int(hotkey.get("vk", 0)) in LOCK_KEY_INFO

    def update_indicator_sync_ui(self) -> None:
        hotkey = self.config.get("hotkey", {})
        vk = int(hotkey.get("vk", 0))
        if vk in LOCK_KEY_INFO and int(hotkey.get("modifiers", 0)) == 0:
            key_name, pretty = LOCK_KEY_INFO[vk]
            self.sync_indicator_label_var.set(tr("led_sync_active", pretty=pretty))
            self.indicator_warning_var.set(tr("led_warning_active"))
            self.sync_indicator_check.configure(state="normal")
        else:
            self.sync_indicator_label_var.set(tr("led_sync_generic"))
            self.indicator_warning_var.set(tr("led_warning_generic"))
            self.sync_indicator_check.configure(state="disabled")
            self.sync_indicator_var.set(False)
            self.config["sync_indicator"] = False
            self.stop_indicator_sync()

    def on_sync_indicator_changed(self) -> None:
        self.update_indicator_sync_ui()
        if self.sync_indicator_var.get() and self.indicator_sync_supported():
            key_name, pretty = LOCK_KEY_INFO[int(self.config["hotkey"]["vk"])]
            consequence_key = "consequence_caps" if key_name == "CapsLock" else "consequence_num" if key_name == "NumLock" else "consequence_scroll"
            consequence = tr(consequence_key)
            enabled = messagebox.askyesno(
                tr("led_confirm_title"),
                tr("led_confirm_message", pretty=pretty, consequence=consequence),
                parent=self.root,
            )
            if not enabled:
                self.sync_indicator_var.set(False)
            else:
                # The application state is authoritative when the user turns
                # this option on from the settings window.  This avoids an
                # already-lit key unexpectedly locking the settings dialog.
                desired = self.active
                vk = int(self.config["hotkey"]["vk"])
                if lock_key_toggle_state(vk) != desired:
                    flip_lock_key(vk)
        if self.sync_indicator_var.get() and self.indicator_sync_supported():
            self.start_indicator_sync()
        else:
            self.stop_indicator_sync()
        self.save_config()

    def offer_indicator_sync_for_selected_key(self) -> None:
        """Ask once after the user records a Lock key as the hotkey."""
        if self.indicator_sync_supported() and not self.sync_indicator_var.get():
            self.sync_indicator_var.set(True)
            self.on_sync_indicator_changed()

    def start_indicator_sync(self, delay_ms: int = 120) -> None:
        """Start the LED reconciliation loop exactly once."""
        if self.closing or not self.indicator_sync_supported() or not self.sync_indicator_var.get():
            return
        if self.indicator_sync_after_id is None:
            self.indicator_sync_after_id = self.root.after(delay_ms, self.sync_lock_state_from_indicator)

    def stop_indicator_sync(self) -> None:
        if self.indicator_sync_after_id is None:
            return
        try:
            self.root.after_cancel(self.indicator_sync_after_id)
        except tk.TclError:
            pass
        self.indicator_sync_after_id = None

    def sync_lock_state_from_indicator(self) -> None:
        # The callback has fired, so its old id is no longer cancellable.
        self.indicator_sync_after_id = None
        if self.closing:
            return
        if self.indicator_sync_supported() and self.sync_indicator_var.get():
            self.reconcile_lock_state_from_indicator()
            self.start_indicator_sync()

    def reconcile_lock_state_from_indicator(self) -> None:
        """Make lock state follow the physical LED state without key injection."""
        if not (self.indicator_sync_supported() and self.sync_indicator_var.get()):
            return
        indicator_on = lock_key_toggle_state(int(self.config["hotkey"]["vk"]))
        if indicator_on != self.active:
            if indicator_on:
                self.activate_lock(from_indicator=True)
            else:
                self.deactivate_lock(from_indicator=True)

    def on_tray_failure(self) -> None:
        self.detail_var.set(tr("tray_failure"))
        write_error_log("通知区域图标线程报告异常")

    def notify_state(self, active: bool, mode_text: str | None = None) -> None:
        """Tell the user about every successful lock-state transition.

        The notification is deliberately best-effort.  A missing/disabled
        notification area, an old shell, or a vendor-modified shell must not
        block the actual cursor operation or terminate the process.
        """
        if not self.notifications_var.get():
            return
        if active:
            mode_text = mode_text or (tr("mode_window") if self.mode_var.get() == "window" else tr("mode_screen"))
            message = tr("notify_lock", mode=mode_text, hotkey=self.hotkey_var.get())
        else:
            message = tr("notify_unlock")
        if not self.tray.notify(message):
            # Classic notification balloons can be disabled globally.  A very
            # short system beep is a non-blocking fallback on legacy Windows;
            # the in-window status remains the authoritative visual state.
            try:
                user32.MessageBeep(0x40 if active else 0x30)
            except (AttributeError, OSError):
                pass

    def report_callback_exception(self, exc, value, tb) -> None:
        if exc is KeyboardInterrupt:
            return
        write_error_log("Tkinter 回调异常", (exc, value, tb))
        if not self.closing:
            self.detail_var.set(tr("callback_error"))

    def on_startup_changed(self) -> None:
        requested = bool(self.startup_var.get())
        if set_startup_enabled(requested):
            self.detail_var.set(tr("startup_enabled" if requested else "startup_disabled"))
            self.root.after(2200, self.refresh_detail)
            return
        self.startup_var.set(not requested)
        messagebox.showerror(
            tr("startup_error_title"),
            tr("startup_error_message"),
            parent=self.root,
        )

    def on_notifications_changed(self) -> None:
        if not self.notifications_var.get():
            # Do not leave a previously emitted balloon visible after the user
            # explicitly disabled notifications.
            self.tray.clear_notification()
        self.save_config()

    def hide_window(self) -> None:
        if self.closing:
            return
        if self.recording:
            self.cancel_recording()
        self.root.withdraw()
        self.hidden_to_tray = True

    def show_window(self) -> None:
        if self.closing:
            return
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()
        self.hidden_to_tray = False

    def begin_recording(self) -> None:
        if self.recording:
            self.cancel_recording()
            return
        self.recording = True
        self.record_modifiers = 0
        self.record_modifier_names.clear()
        self.record_button_var.set(tr("record_prompt"))
        self.record_button.configure(state="normal")
        self.root.bind("<KeyPress>", self.capture_hotkey, add="+")
        self.root.focus_force()

    def cancel_recording(self) -> None:
        self.recording = False
        self.root.unbind("<KeyPress>")
        self.record_button_var.set(tr("record_button"))

    def capture_hotkey(self, event: tk.Event) -> str:
        keysym = str(event.keysym)
        if keysym == "Escape":
            self.cancel_recording()
            return "break"
        modifier = MODIFIER_KEYSYMS.get(keysym)
        if modifier:
            name, flag = modifier
            self.record_modifiers |= flag
            self.record_modifier_names.add(name)
            self.record_button_var.set("+".join([name for name, _ in MODIFIER_ORDER if name in self.record_modifier_names]) + "+…")
            return "break"
        resolved = key_from_event(event)
        if resolved is None:
            return "break"
        vk, label = resolved
        self.config["hotkey"] = {"modifiers": self.record_modifiers, "vk": vk, "label": label}
        self.hotkey_var.set(format_hotkey(self.record_modifiers, label))
        self.update_indicator_sync_ui()
        self.cancel_recording()
        self.save_config()
        self.install_hotkey()
        self.root.after_idle(self.offer_indicator_sync_for_selected_key)
        return "break"

    def install_hotkey(self) -> None:
        """Start the global hotkey watcher.

        The worker reads the physical key state only, never suppresses input,
        and works for modifier combinations as well as Scroll/Caps/Num Lock.
        """
        self.hotkey_worker.stop()
        self.hotkey_worker.start()
        if self.start_locked_var.get() and not self.active:
            self.root.after(300, lambda: self.activate_lock(startup=True))

    def poll_hotkey_events(self) -> None:
        if self.closing:
            return
        try:
            while True:
                event = self.hotkey_events.get_nowait()
                if not (self.indicator_sync_supported() and self.sync_indicator_var.get()):
                    target_hwnd = int(event[1]) if isinstance(event, tuple) and len(event) > 1 else None
                    self.toggle_lock(from_hotkey=True, target_hwnd=target_hwnd)
        except queue.Empty:
            pass
        except Exception:
            write_error_log("全局快捷键事件处理异常", sys.exc_info())
            self.detail_var.set(tr("hotkey_error"))
        if not self.closing:
            self.hotkey_poll_after_id = self.root.after(20, self.poll_hotkey_events)

    def toggle_lock(self, from_hotkey: bool = False, target_hwnd: int | None = None) -> None:
        if self.recording:
            return
        if self.indicator_sync_supported() and self.sync_indicator_var.get():
            # Physical key presses already update the LED. Only the UI button
            # or tray command needs to synthesize a lock-key toggle.
            if not from_hotkey:
                flip_lock_key(int(self.config["hotkey"]["vk"]))
                self.root.after(30, self.reconcile_lock_state_from_indicator)
            else:
                self.reconcile_lock_state_from_indicator()
            return
        if self.active:
            self.deactivate_lock()
        else:
            self.activate_lock(target_hwnd=target_hwnd)

    def activate_lock(
        self,
        startup: bool = False,
        from_indicator: bool = False,
        target_hwnd: int | None = None,
    ) -> None:
        if self.active:
            return
        if startup and self.startup_foreground:
            self.target_hwnd = self.startup_foreground
            self.startup_foreground = None
        else:
            current = int(user32.GetForegroundWindow() or 0)
            if target_hwnd and target_hwnd != self.self_hwnd:
                self.target_hwnd = target_hwnd
            elif current and current != self.self_hwnd:
                self.target_hwnd = current
            else:
                self.target_hwnd = self.last_external_foreground or current
        if self.mode_var.get() == "screen":
            # Capture the monitor once.  The watchdog must not recalculate it
            # from the cursor position after clipping has already begun.
            self.screen_boundary = self.get_screen_boundary()
        else:
            self.screen_boundary = None
        self.last_rect = None
        if self.mode_var.get() == "window":
            if not self.target_hwnd or not user32.IsWindow(self.target_hwnd) or user32.IsIconic(self.target_hwnd):
                self.status_message = tr("no_target")
                self.detail_var.set(self.status_message)
                return
        if self.apply_current_boundary(force=True):
            self.active = True
            if self.last_rect is not None:
                self.boundary_guard.set_boundary(self.last_rect)
            mode_text = tr("mode_window") if self.mode_var.get() == "window" else tr("mode_screen")
            self.status_var.set(tr("status_active_label"))
            self.detail_var.set(tr("detail_active", mode=mode_text, hotkey=self.hotkey_var.get()))
            self.status_dot.itemconfigure(self.status_dot_id, fill="#67e8a5")
            self.tray.refresh(True)
            self.notify_state(True, mode_text)
            if self.sync_indicator_var.get() and self.indicator_sync_supported() and not from_indicator:
                desired = True
                if lock_key_toggle_state(int(self.config["hotkey"]["vk"])) != desired:
                    flip_lock_key(int(self.config["hotkey"]["vk"]))
            self.save_config()

    def deactivate_lock(self, from_indicator: bool = False) -> None:
        self.boundary_guard.clear()
        self.active = False
        self.target_hwnd = None
        self.last_rect = None
        self.screen_boundary = None
        self.status_var.set(tr("status_inactive_label"))
        self.detail_var.set(tr("detail_ready"))
        self.status_dot.itemconfigure(self.status_dot_id, fill="#697386")
        self.tray.refresh(False)
        self.notify_state(False)
        if self.sync_indicator_var.get() and self.indicator_sync_supported() and not from_indicator:
            desired = False
            if lock_key_toggle_state(int(self.config["hotkey"]["vk"])) != desired:
                flip_lock_key(int(self.config["hotkey"]["vk"]))

    def get_window_boundary(self) -> tuple[int, int, int, int] | None:
        if not self.target_hwnd or not user32.IsWindow(self.target_hwnd) or user32.IsIconic(self.target_hwnd):
            return None
        rect = RECT()
        if not user32.GetWindowRect(self.target_hwnd, ctypes.byref(rect)):
            return None
        return rect_tuple(rect)

    def get_screen_boundary(self) -> tuple[int, int, int, int] | None:
        point = POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return None
        monitor = user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST)
        if not monitor:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        # Use the monitor work area instead of the physical monitor rectangle.
        # ``rcMonitor`` includes the taskbar, so a bottom taskbar could leave
        # the cursor apparently stuck in that strip after ScrollLock.  The
        # work area excludes an always-visible taskbar (and similarly handles
        # taskbars docked to the top or sides) while still covering the usable
        # desktop area.
        return rect_tuple(info.rcWork)

    def apply_current_boundary(self, force: bool = False) -> bool:
        if self.mode_var.get() == "window":
            boundary = self.get_window_boundary()
        else:
            boundary = self.screen_boundary
            # This fallback is useful when a caller switches modes before the
            # activation path has had a chance to capture a monitor.
            if boundary is None:
                boundary = self.get_screen_boundary()
                self.screen_boundary = boundary
        if boundary is None:
            if self.active:
                self.deactivate_lock()
                self.detail_var.set(tr("detail_auto_unlock"))
            return False
        left, top, right, bottom = boundary
        if right - left < 2 or bottom - top < 2:
            return False
        # Some games and window managers release the global clip when focus
        # changes. Re-apply when the system rectangle differs, even if the
        # target window itself has not moved.
        if force or boundary != self.last_rect or get_cursor_clip() != boundary:
            native_rect = RECT(left, top, right, bottom)
            if not set_cursor_clip(native_rect):
                self.status_message = tr("clip_failure")
                self.detail_var.set(self.status_message)
                write_error_log(f"ClipCursor 设置失败，目标边界={boundary}")
                return False
            self.last_rect = boundary
            if self.active:
                self.boundary_guard.set_boundary(boundary)
        return True

    def watch_lock(self) -> None:
        if self.closing:
            return
        if not self.active:
            foreground = int(user32.GetForegroundWindow() or 0)
            if foreground and foreground != self.self_hwnd and user32.IsWindow(foreground):
                self.last_external_foreground = foreground
        if self.active:
            self.apply_current_boundary()
        self.root.after(BOUNDARY_REFRESH_MS, self.watch_lock)

    def refresh_detail(self) -> None:
        if not self.active and self.status_message:
            self.detail_var.set(self.status_message)

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        if self.recording:
            self.cancel_recording()
        # Always release the system-wide cursor boundary even if application
        # state was interrupted before `active` was updated.
        self.boundary_guard.stop()
        self.active = False
        self.screen_boundary = None
        if self.indicator_sync_supported() and self.sync_indicator_var.get():
            vk = int(self.config["hotkey"]["vk"])
            if lock_key_toggle_state(vk):
                # In LED-sync mode, quitting is also an unlock. Leave the
                # physical indicator in the matching (off) state.
                flip_lock_key(vk)
        if self.hotkey_poll_after_id is not None:
            try:
                self.root.after_cancel(self.hotkey_poll_after_id)
            except tk.TclError:
                pass
            self.hotkey_poll_after_id = None
        self.stop_indicator_sync()
        self.hotkey_worker.stop()
        self.save_config()
        self.tray.stop()
        self.root.destroy()


def main() -> None:
    mutex = acquire_single_instance()
    launched_at_startup = "--startup" in sys.argv
    if mutex is None:
        if not launched_at_startup:
            user32.MessageBoxW(
                None,
                tr("duplicate_instance"),
                APP_DISPLAY_NAME,
                0x40,
            )
        return
    try:
        startup_foreground = int(user32.GetForegroundWindow() or 0)
        root = tk.Tk()
        if launched_at_startup:
            root.withdraw()
        previous_thread_hook = threading.excepthook

        def log_thread_exception(args) -> None:
            write_error_log(f"后台线程异常：{args.thread.name}", (args.exc_type, args.exc_value, args.exc_traceback))
            previous_thread_hook(args)

        threading.excepthook = log_thread_exception
        CursorFenceApp(root, startup_foreground, launched_at_startup=launched_at_startup)
        root.mainloop()
    except BaseException:
        # A --windowed EXE normally has no console to show a traceback. Keep
        # the system cursor usable and give the user a stable error location.
        set_cursor_clip(None)
        write_error_log("应用主线程异常", sys.exc_info())
        user32.MessageBoxW(
            None,
            tr("fatal_error", path=LOG_DIRECTORY / "error.log"),
            APP_DISPLAY_NAME,
            0x10,
        )
    finally:
        kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
