# CursorFence · Keep Your Cursor Where It Belongs

![Windows](https://img.shields.io/badge/Windows-8.1%2B-0078D6?logo=windows)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-26b976)
![Release](https://img.shields.io/github/v/release/Rhongomiant1227/CursorFence?display_name=tag&sort=semver)

**Keep your cursor where it belongs.**

CursorFence is a small, open-source Windows utility that confines the cursor to the active window or to the usable work area of the current monitor. Press a hotkey to lock; press it again to release. It is useful for windowed games, remote desktops, presentations, recording, and multi-monitor workflows where the cursor tends to escape to another screen.

CursorFence is not the first cursor-boundary tool. It follows the same general idea as projects such as cursorlock, while focusing on the practical pain points people often encounter: mixed-DPI desktops, different monitor layouts, reliable state feedback, stable hotkey handling, and a clean portable release.

[中文版 README](README.md) · [Issues](https://github.com/Rhongomiant1227/CursorFence/issues) · [Releases](https://github.com/Rhongomiant1227/CursorFence/releases)

Bilibili video production plan: [`docs/VIDEO_BILIBILI.md`](docs/VIDEO_BILIBILI.md)

## What it does

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

Open [Releases](https://github.com/Rhongomiant1227/CursorFence/releases), download `CursorFence-windows-x64.zip`, extract the complete folder, and run:

```text
CursorFence\CursorFence.exe
```

Keep the folder intact; do not copy only the EXE. Releases use PyInstaller **onedir** packaging, so the application does not unpack a large temporary archive every time it starts. This makes startup more predictable and gives security software normal files to inspect. Python is not required for the release build.

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
dist\CursorFence-windows-x64.zip
```

The GitHub Actions workflow runs tests, creates the Windows onedir build, and uploads the ZIP as an artifact/release asset. Push a version tag such as `v0.1.0` to create a release asset.

## Why ScrollLock?

ScrollLock is uncommon on modern keyboards, but it often still has a dedicated indicator LED. That makes it a useful “hard to press by accident, easy to see” toggle. CursorFence listens to ScrollLock by default and optionally lets the LED mirror the lock state:

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
- Hotkeys are sampled about every 8 ms. The boundary watchdog runs about every 40 ms and only while locked. There is no permanent high-frequency mouse hook, service, or driver.
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
.github/workflows/       # CI build and release ZIP
```

## Contributing

Issues and pull requests are welcome. Changes involving Win32 boundaries should be tested on different resolutions, DPI scales, monitor orientations, and multi-monitor layouts. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

CursorFence is released under the [MIT License](LICENSE).
