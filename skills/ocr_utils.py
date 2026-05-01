"""
Local OCR utilities.

- OCR engine: rapidocr-onnxruntime (~1s per call, good Chinese/English accuracy, returns bboxes).
- Gotcha (rapid): result[i][2] confidence is a str, not a float.
- Gotcha (rapid): when no text is detected, result is None instead of an empty list.
- Gotcha: enhance (upscale + heavy contrast) hurts already-clear text; disabled by default.
- Gotcha (remote desktop): ImageGrab/mss return a black screen after RDP disconnect; use
  ocr_window(hwnd) instead.
"""
import re

from PIL import ImageGrab, Image, ImageEnhance

_LANG = 'zh-Hans-CN'
_rapid_engine = None


def _get_rapid():
    global _rapid_engine
    if _rapid_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapid_engine = RapidOCR()
    return _rapid_engine


def _preprocess(img, scale=3, contrast=3.0):
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = img.resize((img.width * scale, img.height * scale))
    return img


def _strip_cjk_spaces(t):
    return re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', t)


def _ocr_rapid(img):
    import numpy as np
    engine = _get_rapid()
    arr = np.array(img)
    result, elapse = engine(arr)
    if not result:
        return {'text': '', 'lines': [], 'details': []}
    lines = [r[1] for r in result]
    details = [{'bbox': r[0], 'text': r[1], 'conf': float(r[2])} for r in result]
    text = _strip_cjk_spaces('\n'.join(lines))
    return {'text': text, 'lines': [_strip_cjk_spaces(l) for l in lines], 'details': details}


def ocr_image(image_input, lang=_LANG, enhance=False, engine=None):
    """Run OCR on a PIL Image.

    :param image_input: PIL Image instance or a file path (str).
    :param lang: reserved parameter, currently unused.
    :param enhance: apply preprocessing before OCR.
    :param engine: reserved parameter; only ``rapid``/None is supported today.
    :return: dict ``{'text': full_text, 'lines': [line_text], 'details': [bbox+conf]}``.
    """
    if isinstance(image_input, str):
        image_input = Image.open(image_input)
    if enhance:
        image_input = _preprocess(image_input)
    if engine not in (None, 'rapid'):
        raise ValueError("Only rapid OCR is supported")
    return _ocr_rapid(image_input)


def ocr_screen(bbox=None, lang=_LANG, enhance=False, engine=None):
    """Capture a screen region and run OCR on it.

    :param bbox: ``(x1, y1, x2, y2)`` in pixels; ``None`` means full screen.
    :return: dict ``{'text': full_text, 'lines': [line_text], 'details': [bbox+conf] (rapid only)}``.
    """
    img = ImageGrab.grab(bbox=bbox)
    return ocr_image(img, lang, enhance, engine)


def ocr_window(hwnd, lang=_LANG, enhance=False, engine=None):
    """Capture a window via the PrintWindow API and run OCR on it.

    Works even when a remote desktop session has been disconnected.

    :param hwnd: window handle (int).
    :return: dict ``{'text': full_text, 'lines': [line_text], 'details': [bbox+conf] (rapid only)}``.
    """
    import win32gui
    import win32ui
    from ctypes import windll
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    w, h = r - l, b - t
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)
    windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)
    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    return ocr_image(img, lang, enhance, engine)


if __name__ == "__main__":
    r = ocr_screen((0, 0, 400, 100))
    print(f"Recognized text: {r['text']}")
    for line in r['lines']:
        print(f"  line: {line}")
    if 'details' in r:
        for d in r['details']:
            print(f"  [{d['conf']:.3f}] {d['text']}")
