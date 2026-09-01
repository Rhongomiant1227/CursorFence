# Contributing

感谢参与 CursorFence。请先在 Issue 中描述较大的功能或行为变更，再提交 Pull Request。

## 本地开发

```powershell
.\setup.ps1
.\.venv\Scripts\Activate.ps1
python -m py_compile cursor_fence.py
python -m unittest discover -s tests -v
```

运行 `.\run.ps1` 可打开带托盘图标的源码版。涉及 Win32 行为的改动请在真实 Windows 桌面、至少一个高 DPI 或多显示器环境中手动验证，包括不同分辨率、缩放比例、横竖屏和负坐标排列。

## Pull Request 检查清单

- 说明用户可见行为和兼容性影响。
- 不通过模拟鼠标移动改变 DPI、回报率或输入事件。
- 更新 README / CHANGELOG（如果行为发生变化）。
- `py_compile`、单元测试和 `build.ps1` 均通过。
