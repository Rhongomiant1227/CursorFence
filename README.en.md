# CursorFence

### Stop your cursor from going rogue across monitors

<p align="center"><img src="resources/CursorFence.png" alt="CursorFence icon" width="128"></p>

![Windows](https://img.shields.io/badge/Windows-8.1%2B-0078D6?logo=windows)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-26b976)
![Release](https://img.shields.io/github/v/release/Rhongomiant1227/CursorFence?display_name=tag&sort=semver)

**Your cursor keeps escaping to the other screen? Give it a boundary.**

CursorFence is a small, open-source, portable Windows utility for windowed games, remote desktops, presentations, recordings, and any multi-monitor workflow where one quick movement sends the cursor somewhere it should not be.

Press a hotkey to keep the cursor inside the current window or monitor work area. Press it again to release.

The idea is not new. Projects such as cursorlock already show that people need it. CursorFence focuses on the details that make a tiny utility pleasant to use: mixed-DPI desktops, predictable monitor boundaries, visible state feedback, reliable hotkeys, and a release that simply runs after extraction.

[中文版 README](README.md) · [Issues](https://github.com/Rhongomiant1227/CursorFence/issues) · [Releases](https://github.com/Rhongomiant1227/CursorFence/releases)

Bilibili video production plan: [`docs/VIDEO_BILIBILI.md`](docs/VIDEO_BILIBILI.md)

## Up and running in 30 seconds

1. Download `CursorFence-Portable-windows-x64.zip` or `CursorFence-Installer.exe` from [Releases](https://github.com/Rhongomiant1227/CursorFence/releases/latest).
2. For a portable run, extract the ZIP and launch `CursorFence-Portable.exe`. For a normal install, run the installer and launch CursorFence from the Start menu.
3. Place the cursor over the target window or monitor and press `ScrollLock`.
4. The status turns green. Press `ScrollLock` again to release.

Python is not required. The single-file portable build is useful on a USB drive or temporary machine; the installer registers a normal per-user installation in Windows' installed-apps list.

## What it is good for

| | Feature |
| --- | --- |
| **Two boundary modes** | Active window, or the monitor work area captured at activation time |
| **Configurable hotkey** | `ScrollLock` by default; record `Ctrl / Alt / Shift / Win + any key` |
| **ScrollLock indicator** | Optional LED synchronization: LED on means locked |
| **Visible state** | Status dot, tray icon, and optional Windows notification |
| **Portable utility** | Runs from an extracted folder; optional per-user startup |
| **Mouse-safe design** | No cursor movement, DPI changes, polling-rate changes, or mouse driver |
| **Multi-monitor ready** | Different resolutions, negative coordinates, portrait displays, and mixed scaling |

## Download

Open [Releases](https://github.com/Rhongomiant1227/CursorFence/releases), download the portable ZIP or installer. The portable ZIP contains a single EXE:

```text
CursorFence-Portable.exe
```

The installer places the onedir build in the current user's programs directory and adds a normal Start menu shortcut and uninstall entry. The onedir layout keeps installed startup predictable and gives security software normal files to inspect.

### First run

1. Place the cursor over the window or monitor you want to constrain.
2. Press `ScrollLock`.
3. The status turns green and the cursor stays inside the selected boundary.
4. Press `ScrollLock` again to release it.

Monitor mode uses the Windows work area (`rcWork`). It includes the entire usable desktop down to the work-area edge, but excludes a taskbar docked to the bottom, top, or side. The monitor is captured once when locking starts, so moving toward an edge cannot silently switch the target display.

## Run from source

Requires Windows, PowerShell, and Python 3.10+:

```powershell
Set-Location <repository>
.\setup.ps1
.\run.ps1
```

The scripts create a project-local `.venv`. Useful checks:

```powershell
.\.venv\Scripts\python.exe -m py_compile cursor_fence.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Build and package

```powershell
.\build.ps1
```

The script creates both the onedir folder and a ready-to-upload ZIP:

```text
dist\CursorFence\CursorFence.exe
dist\CursorFence-Portable.exe
dist\CursorFence-Portable-windows-x64.zip
dist\CursorFence-Installer.exe
```

When Inno Setup 6 is installed locally, the script also creates the installer; the portable build still completes without it. GitHub Actions prepares Inno Setup automatically. Push a version tag such as `v0.2.2` to create a release with both assets.

## Why ScrollLock?

ScrollLock is rarely used, but many keyboards still have a dedicated indicator LED. That makes it difficult to trigger accidentally and easy to read at a glance. CursorFence listens to ScrollLock by default and optionally lets the LED mirror the lock state:

- LED on: cursor locked;
- LED off: cursor released;
- turn the option off if you do not want the application to change the LED;
- CapsLock and NumLock are also supported, with an explicit warning because they retain their normal system behavior.

## How it works

CursorFence calls the native Windows `ClipCursor` API with a rectangle:

- active window: `GetForegroundWindow` + `GetWindowRect`;
- current monitor: `GetCursorPos` + `MonitorFromPoint` + `GetMonitorInfoW`;
- mixed DPI: Per-Monitor DPI Awareness V2 where available, keeping Win32 coordinates in one physical-pixel virtual-desktop space;
- hotkeys: a small worker thread reads `GetAsyncKeyState` and sends events to the Tk main thread through a queue;
- watchdog: while locked, it checks whether another program released the system clip and reapplies the same boundary if necessary.

It does not move or inject mouse input, change DPI, polling/report rate, acceleration, button or wheel behavior, install a driver, inject into another process, or read game memory. Only an explicit LED-sync UI/tray action synthesizes a lock-key press/release to update the keyboard indicator.

This is not a guarantee about every game's anti-cheat policy. For competitive games or games with strict anti-cheat, exit CursorFence before launching the game. It is best suited to desktop work, remote desktops, multi-monitor workflows, and offline games.

## Compatibility, performance, and recovery

- The current release is built with Python 3.10 and is intended for Windows 8.1/10/11 x64. The notification API uses classic tray balloons on older Windows and may appear as a toast on Windows 10/11.
- Common monitor configurations are supported: 1080p, 1440p, 4K, ultrawide, portrait displays, negative-coordinate layouts, and mixed scaling factors. The actual rectangle always comes from the current Windows monitor configuration.
- Hotkeys are sampled about every 8 ms. While locked, an independent boundary guard rechecks the native clip at roughly 2 ms intervals; moving-window geometry is refreshed about every 40 ms. There is no permanent high-frequency mouse hook, service, or driver.
- Some high-FPS games rewrite their own `ClipCursor` range every frame. The guard greatly shortens the escape window, but Windows scheduling and simultaneous writes still leave a tiny race, so absolute interception cannot be promised. Prefer the game's borderless-window or built-in cursor-lock option when available.
- Notification failures, disabled notification areas, closed/minimized target windows, and third-party clip releases are handled as recoverable conditions. Details are written to `%LOCALAPPDATA%\CursorFence\logs\error.log`.
- If security software flags the portable build, inspect the complete release folder as one application. Do not delete DLLs from `_internal`.

## Project layout

```text
cursor_fence.py          # application, UI, and Win32 boundary logic
run.ps1 / setup.ps1      # source run and virtual-environment setup
build.ps1                # PyInstaller onedir build
tools/create_icon.py     # icon generator
resources/               # icon and version metadata
tests/                   # core unit tests
installer/               # Inno Setup installer script
.github/workflows/       # CI build and release ZIP
```

## Contributing

Issues and pull requests are welcome. Changes involving Win32 boundaries should be tested on different resolutions, DPI scales, monitor orientations, and multi-monitor layouts. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

CursorFence is released under the [MIT License](LICENSE).
