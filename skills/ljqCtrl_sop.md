# ljqCtrl Usage and Coordinate Conversion SOP

> **must call update working ckp**: `ljqCtrl always uses physical coordinates | no pyautogui | activate the window before any operation`

## 0. API quick reference (signatures)
- `ljqCtrl.dpi_scale`: float (scale factor = logical width / physical width)
- `ljqCtrl.SetCursorPos(z)`: move the cursor to logical coordinate z=(x, y)
- `ljqCtrl.Click(x, y=None)`: simulate a click. Accepts `Click((x, y))` or `Click(x, y)`
- `ljqCtrl.Press(cmd, staytime=0)`: simulate a key combination, e.g. `Press('ctrl+c')`
- `ljqCtrl.FindBlock(fn, wrect=None, threshold=0.8)`: template match. Returns `((center_x, center_y), is_found)`
- `ljqCtrl.MouseDClick(staytime=0.05)`: double-click

## 1. Importing
The skills package lives under `photoagents/skills/`, so import directly from there:
```python
import pygetwindow as gw
from photoagents.skills import ljqCtrl
```

## 2. Core: high-DPI physical coordinate conversion
`ljqCtrl`'s `Click`/`MoveTo` interfaces take **physical pixel** coordinates.
When tools such as `pygetwindow` give you a window position (logical coordinates), divide by the DPI scale.

- **Conversion formula**: `physical = logical / ljqCtrl.dpi_scale`.
- **Note**: 3840 (4K) is just an example from the dev machine; the real physical bounds depend on the system. Code should always compute through `dpi_scale`.

## 3. Window operations and click flow
1. **Activate the window**: use `gw.getWindowsWithTitle('title')` to fetch it, then call `restore()` and `activate()`.
2. **Compute coordinates**:
```python
win = gw.getWindowsWithTitle('WeChat')[0]
# Logical coordinates (lx, ly) of some point inside the window
# Convert to physical and click
px, py = lx / ljqCtrl.dpi_scale, ly / ljqCtrl.dpi_scale
ljqCtrl.Click(px, py)
```

## 4. Pitfall guide
- **Always use physical coordinates**: coordinates passed to `ljqCtrl.Click`/`SetCursorPos` must be physical (= screenshot pixel coordinates). Logical coordinates from `pygetwindow` must be `/ dpi_scale` first. Never pass logical coordinates.
- **Physical verification**: before any simulated input, the window must already be activated to the foreground via `activate()`.
- **Offsets**: relative pixel offsets ("move 10 px right") must also be divided by `dpi_scale`.
- **Coordinate alignment**: physical coordinates equal screenshot coordinates; `ljqCtrl` handles the DPI conversion itself, do not double-convert.
- **Window-coordinate trap**: `win32gui.GetWindowRect(hwnd)` includes the title bar and border, but a screenshot only shows the client area. To click an element inside a screenshot you must compute the client-area origin via `win32gui.ClientToScreen(hwnd, (0, 0))` and add the in-screenshot coordinates. Never use the GetWindowRect top-left + screenshot coordinates directly.
- **win32 DPI trap**: without calling `SetProcessDPIAware()`, `GetWindowRect`/`ClientToScreen`/`GetClientRect` return **logical** coordinates. If subsequent screenshots or `ljqCtrl` use physical pixels, divide by `ljqCtrl.dpi_scale` consistently. Equivalent fix: call `SetProcessDPIAware()` once and use raw physical coordinates everywhere; never mix logical and physical.
- **Text input**: `ljqCtrl` has no `TypeText`/`SendKeys`. To type into an input field: click/triple-click to select the field, then `pyperclip.copy('text'); ljqCtrl.Press('ctrl+v')`.
