import base64
import os
import sys
from io import BytesIO
from pathlib import Path

import requests

# ============ User configuration (after copying from the template, only edit this block) ============
CLAUDE_CONFIG_KEY = 'claude_config141'   # name of the Claude config variable inside credentials.py
OPENAI_CONFIG_KEY = 'oai_config1'        # name of the OpenAI config variable inside credentials.py
MODELSCOPE_API_KEY = ''                  # paste your ModelScope token directly
DEFAULT_BACKEND = 'claude'               # default backend: 'claude' / 'openai' / 'modelscope'
# =====================================================================================================

MODELSCOPE_API_BASE = 'https://api-inference.modelscope.cn'
MODELSCOPE_MODEL = 'Qwen/Qwen3-VL-235B-A22B-Instruct'

_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in [os.path.join(_DIR, '..'), os.path.join(_DIR, '../..')]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


def ask_vision(image_input, prompt="Describe the contents of this image in detail.",
               timeout=60, max_pixels=1440000, backend=DEFAULT_BACKEND):
    try:
        b64 = _prepare_image(image_input, max_pixels)
    except Exception as e:
        return f"Error: image preprocessing failed - {type(e).__name__}: {e}"
    try:
        if backend == 'claude':
            return _call_claude(b64, prompt, timeout)
        elif backend == 'openai':
            mk = _load_config()
            cfg = getattr(mk, OPENAI_CONFIG_KEY)
            return _call_openai_compat(
                b64, prompt, timeout,
                apibase=cfg['apibase'], apikey=cfg['apikey'], model=cfg['model'], proxy=cfg.get('proxy'),
            )
        elif backend == 'modelscope':
            return _call_openai_compat(
                b64, prompt, timeout,
                apibase=MODELSCOPE_API_BASE, apikey=MODELSCOPE_API_KEY, model=MODELSCOPE_MODEL, proxy=None,
            )
        else:
            return f"Error: unknown backend '{backend}', expected one of: claude, openai, modelscope"
    except requests.exceptions.Timeout:
        return f"Error: request timed out (>{timeout}s)"
    except requests.exceptions.RequestException as e:
        return f"Error: API request failed - {type(e).__name__}: {e}"
    except (KeyError, ValueError) as e:
        return f"Error: response parsing failed - {e}"


# ===================== internal helpers =====================

def _prepare_image(image_input, max_pixels=1440000):
    """Load, resize and base64-encode an image; returns the base64 string."""
    from PIL import Image
    if isinstance(image_input, Image.Image):
        img = image_input
    elif isinstance(image_input, (str, Path)):
        img = Image.open(image_input)
    else:
        raise TypeError(f"image_input must be a file path or PIL Image, got: {type(image_input).__name__}")
    w, h = img.size
    if w * h > max_pixels:
        scale = (max_pixels / (w * h)) ** 0.5
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        print(f"  resize: {w}x{h} -> {new_w}x{new_h}")
    if img.mode in ('RGBA', 'LA', 'P'):
        rgb = Image.new('RGB', img.size, (255, 255, 255))
        rgb.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = rgb
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=80, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    print(f"  base64: {len(buf.getvalue()) / 1024:.1f}KB")
    return b64


def _load_config():
    import credentials
    return credentials


def _call_claude(b64, prompt, timeout, max_tokens=1024):
    mk = _load_config()
    cfg = getattr(mk, CLAUDE_CONFIG_KEY)
    resp = requests.post(
        cfg['apibase'] + '/v1/messages',
        json={'model': cfg['model'], 'max_tokens': max_tokens, 'messages': [{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}},
                {'type': 'text', 'text': prompt},
            ],
        }]},
        headers={'x-api-key': cfg['apikey'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()['content'][0]['text']


def _call_openai_compat(b64, prompt, timeout, *, apibase, apikey, model, proxy=None):
    proxies = {'https': proxy, 'http': proxy} if proxy else None
    resp = requests.post(
        apibase.rstrip('/') + '/v1/chat/completions',
        json={'model': model, 'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}},
            ],
        }]},
        headers={'Authorization': f"Bearer {apikey}", 'Content-Type': 'application/json'},
        proxies=proxies, timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']


if __name__ == '__main__':
    pass
