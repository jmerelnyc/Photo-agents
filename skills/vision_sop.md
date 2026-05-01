# Vision API SOP

## Pre-flight rules (must follow)

1. **Enumerate windows first**: before calling vision, use `pygetwindow` to enumerate window titles and confirm the target window exists and is in the foreground. If the window is not there, do not screenshot.
2. **No full-screen screenshots**: always use ljqCtrl to capture a window region. If you can capture a sub-region (e.g. a title bar), do not capture the whole window; if you can capture the window, do not capture the screen. Full-screen screenshots are never allowed.
3. **Do not use vision unless you have to**: if the window title or local OCR (`ocr_utils.py`) can give you the info you need, do not call the vision API — it saves tokens and is more reliable. Vision is a last resort.

## Quick usage

```python
from vision_api import ask_vision
result = ask_vision(image, prompt="Describe the image", backend="claude", timeout=60, max_pixels=1_440_000)
# image: file path (str/Path) or PIL Image
# backend: 'claude' (default) | 'openai' | 'modelscope'
# Returns str: model reply on success, 'Error: ...' on failure
```

## When `vision_api.py` is missing — first-time setup

1. Copy `photoagents/skills/vision_api_template.py` -> `photoagents/skills/vision_api.py`.
2. Only edit the "user configuration" block at the top: scan `credentials.py` for variable names (warning: only look at names — never print apikey values), pick a usable config name and put it in `CLAUDE_CONFIG_KEY` / `OPENAI_CONFIG_KEY`, choose `DEFAULT_BACKEND`, and test.
3. Fallback: if no usable config exists, get a token from `https://modelscope.cn/my/myaccesstoken` and put it in `MODELSCOPE_API_KEY`.
