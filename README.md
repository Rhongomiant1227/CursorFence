# CursorFence · 光标围栏

![Windows](https://img.shields.io/badge/Windows-8.1%2B-0078D6?logo=windows)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-26b976)
![Release](https://img.shields.io/github/v/release/Rhongomiant1227/CursorFence?display_name=tag&sort=semver)

**把鼠标留在该在的地方。**

CursorFence 是一个轻量、开源的 Windows 光标边界工具：按一次快捷键，把鼠标限制在当前窗口或当前显示器的可用工作区；再按一次立即解除。它面向窗口化游戏、远程桌面、多显示器办公、演示和录屏等场景，解决“鼠标一不小心滑到旁边屏幕”的小痛点。

> 这个项目不是第一个做“鼠标边界锁定”的工具。CursorFence 借鉴了 cursorlock 等同类工具的思路，重点解决它们在混合 DPI、多显示器、状态反馈、稳定性和发布体验上的常见痛点。

[English README](README.en.md) · [Issues](https://github.com/Rhongomiant1227/CursorFence/issues) · [Releases](https://github.com/Rhongomiant1227/CursorFence/releases)

B 站视频制作方案：[`docs/VIDEO_BILIBILI.md`](docs/VIDEO_BILIBILI.md)

## 亮点

| | 能做什么 |
| --- | --- |
| **两种边界** | 当前窗口，或激活瞬间所在显示器的可用工作区 |
| **快捷键** | 默认 `ScrollLock`，也可录制 `Ctrl / Alt / Shift / Win + 任意主键` |
| **ScrollLock 设计** | 不常用但有键盘灯的按键，既适合切换，也能作为状态指示 |
| **键盘灯同步** | 可选让 ScrollLock / CapsLock / NumLock 灯亮代表“已锁定” |
| **清晰反馈** | 状态点、托盘图标、右下角通知；通知可关闭 |
| **常驻工具** | 关闭窗口后驻留通知区域，支持当前用户开机启动 |
| **不碰鼠标硬件** | 不移动光标、不改 DPI/回报率/加速度、不安装鼠标驱动 |
| **多显示器友好** | 支持不同分辨率、负坐标、横竖屏排列和混合缩放 |

## 下载与运行

打开 [Releases](https://github.com/Rhongomiant1227/CursorFence/releases)，下载类似 `CursorFence-windows-x64.zip` 的发布包，解压后运行：

```text
CursorFence\CursorFence.exe
```

请保留整个目录，不要只复制其中的 EXE。发布包采用 PyInstaller **目录型（onedir）** 模式：启动时不需要解压大型临时文件，启动更稳定，也更容易被安全软件检查。程序不需要安装 Python。

### 第一次使用

1. 把鼠标放到希望锁定的窗口或显示器上。
2. 按默认的 `ScrollLock`。
3. 状态变为绿色后，鼠标不能越过边界。
4. 再按一次 `ScrollLock` 解除。

“当前显示器”使用的是系统工作区 `rcWork`：允许移动到工作区最底部，但不会把底部、顶部或侧边任务栏纳入可移动区域。边界在激活瞬间捕获，不会因为鼠标靠近边缘而跳到另一块屏幕。

## 从源码运行

需要 Windows、PowerShell 和 Python 3.10+：

```powershell
Set-Location <仓库目录>
.\setup.ps1
.\run.ps1
```

脚本会创建项目专用的 `.venv`，不会污染系统 Python。开发检查：

```powershell
.\.venv\Scripts\python.exe -m py_compile cursor_fence.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 构建与发布

```powershell
.\build.ps1
```

脚本会同时生成目录和可直接上传 Release 的 ZIP：

```text
dist\CursorFence\CursorFence.exe
dist\CursorFence-windows-x64.zip
```

GitHub Actions 会在 Windows Runner 上自动执行测试、构建和 ZIP 打包；推送版本标签（例如 `v0.1.0`）即可生成 Release 附件。

## 为什么选择 ScrollLock？

ScrollLock 在现代键盘上使用频率较低，却通常保留独立的键盘灯。它非常适合做“不会误触、又能一眼确认状态”的切换键。CursorFence 默认监听 ScrollLock，并提供可选的“让激活状态与 ScrollLock 指示灯保持一致”：

- 灯亮：光标已锁定；
- 灯灭：光标未锁定；
- 不喜欢改变键盘灯时，可以关闭此选项；
- CapsLock / NumLock 也支持相同逻辑，但会弹出提示，因为它们还有原本的系统功能。

## 技术原理与安全边界

CursorFence 只调用 Windows 原生 `ClipCursor` 设置系统光标可移动矩形：

- 当前窗口：`GetForegroundWindow` + `GetWindowRect`；
- 当前显示器：`GetCursorPos` + `MonitorFromPoint` + `GetMonitorInfoW`；
- 混合 DPI：尽可能使用 `Per-Monitor DPI Awareness V2`，让 Win32 坐标保持在同一个物理像素坐标系；
- 快捷键：后台线程读取 `GetAsyncKeyState`，通过线程安全队列交给 Tk 主线程；
- 锁定看门狗：仅在锁定期间定期确认边界是否被其他程序释放。

程序不会移动或注入鼠标输入，不修改鼠标 DPI、轮询/回报率、加速度、按键和滚轮行为，不安装驱动、不注入其他进程、不读取游戏内存。只有用户明确启用键盘灯同步并从 UI/托盘切换时，程序才会合成一次锁定键按下/抬起，用于更新键盘灯。

这不是对所有游戏反作弊策略的保证。竞技游戏或使用严格反作弊的游戏，建议启动游戏前退出 CursorFence；普通桌面、多屏办公、远程桌面和单机游戏场景更适合使用。

## 兼容性、性能与故障恢复

- 当前发布包使用 Python 3.10 构建，建议 Windows 8.1/10/11 x64；通知接口在 Windows 7/8 使用经典通知区域气泡，在 Windows 10/11 可能显示为系统 Toast。
- 支持任意常见显示器分辨率和排列：1080p、1440p、4K、超宽屏、竖屏、负坐标副屏，以及不同缩放比例的混合 DPI 桌面。最终边界由 Windows 当前显示器配置返回。
- 快捷键检查约每 8 ms 一次；锁定看门狗约每 40 ms 一次，且只在锁定时工作。没有常驻高频鼠标 Hook、后台服务或驱动。
- 通知失败、通知区域被禁用、窗口关闭/最小化、第三方程序释放边界等情况都会安全降级；异常记录在 `%LOCALAPPDATA%\CursorFence\logs\error.log`。
- 如果安全软件提示风险，请将整个发布目录作为一个程序检查。不要删除 `_internal` 中的 DLL。

## 项目结构

```text
cursor_fence.py          # 应用主体、UI 与 Win32 边界逻辑
run.ps1 / setup.ps1      # 源码运行与虚拟环境准备
build.ps1                # PyInstaller 目录型打包
tools/create_icon.py     # 生成应用图标
resources/               # 图标与版本信息
tests/                   # 核心单元测试
.github/workflows/       # 自动测试、构建和 Release ZIP
```

## 参与贡献

欢迎提交 Issue 和 Pull Request。涉及 Win32 边界行为的改动，请至少在不同分辨率、不同 DPI 缩放或多显示器环境中手动验证。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

本项目使用 [MIT License](LICENSE)。
