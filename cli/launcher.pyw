"""Photo Agents desktop launcher.

A thin pywebview wrapper around the Streamlit web client. Owns the optional
side processes (Telegram / QQ / Feishu / WeCom / DingTalk bots, scheduler).

Run as: ``pythonw -m photoagents.cli.launcher``
"""

import argparse
import atexit
import ctypes
import os
import random
import socket
import subprocess
import sys
import threading
import time

import webview

# Gate before doing anything else.
from photoagents.auth import ensure_authenticated

ensure_authenticated()


WINDOW_WIDTH = 600
WINDOW_HEIGHT = 900
RIGHT_PADDING = 0
TOP_PADDING = 100

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_DIR = os.path.dirname(_HERE)
_REPO_DIR = os.path.dirname(_PKG_DIR)
_CLIENTS_DIR = os.path.join(_PKG_DIR, "clients")


def find_free_port(lo: int = 18_501, hi: int = 18_599) -> int:
    ports = list(range(lo, hi + 1))
    random.shuffle(ports)
    for p in ports:
        try:
            s = socket.socket()
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            continue
    raise RuntimeError(f"No free port in {lo}-{hi}")


def get_screen_width() -> int:
    try:
        return ctypes.windll.user32.GetSystemMetrics(0)
    except Exception:
        return 1920


def start_streamlit(port: int) -> None:
    global proc
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        os.path.join(_CLIENTS_DIR, "web_app_lite.py"),
        "--server.port", str(port),
        "--server.address", "localhost",
        "--server.headless", "true",
    ]
    proc = subprocess.Popen(cmd, cwd=_REPO_DIR)
    atexit.register(proc.kill)


def inject(text: str) -> None:
    """Inject ``text`` into the Streamlit chat input via native setter + React event chain."""
    window.evaluate_js(f"""
        const textarea = document.querySelector('textarea[data-testid="stChatInputTextArea"]');
        if (textarea) {{
            const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value').set;
            nativeTextAreaValueSetter.call(textarea, {text!r});
            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
            textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
            setTimeout(() => {{
                const btn = document.querySelector('[data-testid="stChatInputSubmitButton"]');
                if (btn) {{ btn.click(); console.log('Submitted:', {text!r}); }}
            }}, 200);
        }}""")


def get_last_reply_time() -> int:
    last = window.evaluate_js("""
        const el = document.getElementById('last-reply-time');
        el ? parseInt(el.textContent) : 0;
    """) or 0
    return last or int(time.time())


PASTE_HOOK_JS = """if (!window._pasteHooked) { window._pasteHooked = true;
    document.addEventListener('paste', e => {
        const items = e.clipboardData?.items; if (!items) return;
        let t = null;
        for (const item of items) { if (item.kind === 'file') {
            t = item.type.startsWith('image/') ? 'image in clipboard, ' : 'file in clipboard, ';
            break; } }
        if (!t) return;
        e.preventDefault(); e.stopImmediatePropagation();
        const el = document.querySelector('textarea[data-testid="stChatInputTextArea"]') || document.activeElement;
        if (el && (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT')) {
            const s = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set
                   || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
            s.call(el, el.value + t); el.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }, true);
}"""


def idle_monitor() -> None:
    """If the user is silent for >30 min, fire the autonomous trigger."""
    last_trigger_time = 0
    while True:
        time.sleep(5)
        try:
            window.evaluate_js(PASTE_HOOK_JS)
            now = time.time()
            if now - last_trigger_time < 120:
                continue
            last_reply = get_last_reply_time()
            if now - last_reply > 1800:
                print("[Idle Monitor] Detected idle state, injecting task...")
                inject(
                    "[AUTO] User has been idle for over 30 minutes. As an autonomous "
                    "agent, read the autonomous-operations SOP and execute background tasks."
                )
                last_trigger_time = now
        except Exception as exc:  # noqa: BLE001
            print(f"[Idle Monitor] Error: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("port", nargs="?", default="0")
    parser.add_argument("--tg", action="store_true", help="start the Telegram bot")
    parser.add_argument("--qq", action="store_true", help="start the QQ bot")
    parser.add_argument("--feishu", "--fs", dest="feishu", action="store_true",
                        help="start the Feishu bot")
    parser.add_argument("--wecom", action="store_true", help="start the WeCom bot")
    parser.add_argument("--dingtalk", "--dt", dest="dingtalk", action="store_true",
                        help="start the DingTalk bot")
    parser.add_argument("--sched", action="store_true", help="start the task scheduler")
    parser.add_argument("--llm_no", type=int, default=0, help="LLM index to start with")
    args = parser.parse_args()

    port = str(find_free_port()) if args.port == "0" else args.port
    print(f"[Launch] Using port {port}")
    threading.Thread(target=start_streamlit, args=(port,), daemon=True).start()

    def _spawn(name: str, script: str) -> None:
        sub = subprocess.Popen(
            [sys.executable, os.path.join(_CLIENTS_DIR, script)],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            cwd=_REPO_DIR,
        )
        atexit.register(sub.kill)
        print(f"[Launch] {name} started")

    if args.tg:        _spawn("Telegram bot", "telegram_client.py")
    else:              print("[Launch] Telegram bot not enabled (use --tg to start)")
    if args.qq:        _spawn("QQ bot", "qq_client.py")
    else:              print("[Launch] QQ bot not enabled (use --qq to start)")
    if args.feishu:    _spawn("Feishu bot", "feishu_client.py")
    else:              print("[Launch] Feishu bot not enabled (use --feishu to start)")
    if args.wecom:     _spawn("WeCom bot", "wecom_client.py")
    else:              print("[Launch] WeCom bot not enabled (use --wecom to start)")
    if args.dingtalk:  _spawn("DingTalk bot", "dingtalk_client.py")
    else:              print("[Launch] DingTalk bot not enabled (use --dingtalk to start)")

    if args.sched:
        scheduler = subprocess.Popen(
            [sys.executable, "-m", "photoagents",
             "--reflect", os.path.join(_PKG_DIR, "evolution", "scheduler.py"),
             "--llm_no", str(args.llm_no)],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            cwd=_REPO_DIR,
        )
        atexit.register(scheduler.kill)
        print("[Launch] Task scheduler started (duplicate prevented by scheduler port lock)")
    else:
        print("[Launch] Task scheduler not enabled (--sched)")

    threading.Thread(target=idle_monitor, daemon=True).start()
    if os.name == "nt":
        x_pos = get_screen_width() - WINDOW_WIDTH - RIGHT_PADDING
    else:
        x_pos = 100
    time.sleep(2)
    window = webview.create_window(
        title="Photo Agents", url=f"http://localhost:{port}",
        width=WINDOW_WIDTH, height=WINDOW_HEIGHT, x=x_pos, y=TOP_PADDING,
        resizable=True, text_select=True,
    )
    webview.start()
