import os, sys, subprocess
from urllib.request import urlopen
from urllib.parse import quote
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
try: sys.stdout.reconfigure(errors='replace')
except: pass
try: sys.stderr.reconfigure(errors='replace')
except: pass
script_dir = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(script_dir, '..', '..')))
sys.path.append(os.path.abspath(script_dir))

import streamlit as st
import time, json, re, threading, queue
from photoagents.cli.runtime import PhotoAgentsRuntime as GeneraticAgent
from photoagents.clients import client_common  # activates /continue command (monkey-patches runtime)
from photoagents.clients.resume_cmd import handle_frontend_command, reset_conversation, list_sessions, extract_ui_messages

st.set_page_config(page_title="Photo Agents", layout="wide")

# --- Photo Agents theme matching the photo-agents.com dashboard ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@200;300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    :root {
        --pa-ink: #0e1210;
        --pa-paper: #b6b6b6;
        --pa-canvas: #f6f5f1;
        --pa-line: #e6e4dd;
        --pa-line-strong: rgba(14, 18, 16, 0.10);
        --pa-muted: #77756d;
        --pa-surface-2: #efede6;
        --pa-shadow-card: 0 8px 24px -12px rgba(14, 18, 16, 0.30);
    }
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-color: var(--pa-paper) !important;
        color: var(--pa-ink) !important;
        font-family: 'Manrope', ui-sans-serif, system-ui, sans-serif !important;
        font-weight: 300 !important;
        letter-spacing: -0.01em !important;
        -webkit-font-smoothing: antialiased !important;
    }
    [data-testid="stSidebar"] {
        background-color: var(--pa-canvas) !important;
        border-right: 1px solid var(--pa-line) !important;
        box-shadow: 1px 0 0 var(--pa-line-strong) !important;
        width: 300px !important;
        min-width: 300px !important;
        max-width: 300px !important;
        flex-basis: 300px !important;
        resize: none !important;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarResizeHandle"],
    [data-testid="stSidebar"] > div[class*="resize" i],
    [data-testid="stSidebarUserContent"] ~ div[role="separator"] {
        display: none !important; pointer-events: none !important;
    }
    [data-testid="stHeader"] {
        background: rgba(182, 182, 182, 0.78) !important;
        backdrop-filter: saturate(180%) blur(10px) !important;
        border-bottom: 1px solid var(--pa-line-strong) !important;
        height: 56px !important;
        min-height: 56px !important;
    }
    #MainMenu, [data-testid="stDecoration"], [data-testid="stStatusWidget"],
    [data-testid="stMainMenu"], [data-testid="stMainMenuButton"] {
        visibility: hidden !important; display: none !important;
    }
    header[data-testid="stHeader"] [data-testid="stToolbar"] {
        display: flex !important; visibility: visible !important; background: transparent !important;
    }
    header[data-testid="stHeader"] [data-testid="stToolbar"] > *:not(:has([data-testid="stExpandSidebarButton"])) { display: none !important; }
    [data-testid="stExpandSidebarButton"], [data-testid="stExpandSidebarButton"] *,
    [data-testid="stExpandSidebarButton"] button {
        display: inline-flex !important; visibility: visible !important; opacity: 1 !important;
        width: auto !important; height: auto !important;
    }
    [data-testid="stExpandSidebarButton"] button {
        background: var(--pa-canvas) !important;
        border: 1px solid var(--pa-line) !important;
        color: var(--pa-ink) !important;
        border-radius: 10px !important;
        box-shadow: var(--pa-shadow-card) !important;
        width: 36px !important; height: 36px !important; padding: 6px !important;
    }
    [data-testid="stExpandSidebarButton"] button svg { color: var(--pa-ink) !important; fill: var(--pa-ink) !important; }
    [data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapseButton"] *,
    [data-testid="stSidebarCollapseButton"] button {
        display: inline-flex !important; visibility: visible !important; opacity: 1 !important;
    }
    [data-testid="stSidebarCollapseButton"] button { color: var(--pa-muted) !important; background: transparent !important; }
    body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stBottom"] { left: 0 !important; }
    [data-testid="stMain"] { background-color: var(--pa-paper) !important; }
    [data-testid="stMainBlockContainer"], .main .block-container {
        max-width: 880px !important;
        padding: 2.25rem 2.5rem 7rem 2.5rem !important;
        background-color: var(--pa-canvas) !important;
        border: 1px solid var(--pa-line) !important;
        border-radius: 20px !important;
        box-shadow: var(--pa-shadow-card) !important;
        margin-top: 1.25rem !important;
        margin-bottom: 1rem !important;
        min-height: calc(100vh - 56px - 6.5rem) !important;
    }
    h1, .stTitle, [data-testid="stHeading"] h1 {
        color: var(--pa-ink) !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 200 !important;
        letter-spacing: -0.04em !important;
        font-size: 2.25rem !important;
    }
    h2 { font-weight: 300 !important; letter-spacing: -0.03em !important; }
    h3, h4, h5, h6 { font-weight: 500 !important; letter-spacing: -0.02em !important; }
    p, .stMarkdown p { color: var(--pa-ink) !important; font-weight: 300 !important; line-height: 1.65 !important; }
    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--pa-muted) !important;
        font-size: 12px !important;
        letter-spacing: -0.005em !important;
        line-height: 1.55 !important;
        word-break: break-word !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        color: var(--pa-muted) !important;
        font-size: 10.5px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.18em !important;
        font-weight: 500 !important;
    }
    [data-testid="stChatMessage"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        padding: 0.25rem 0 1rem 0 !important;
        margin-bottom: 0.85rem !important;
        border-bottom: 1px solid var(--pa-line) !important;
    }
    [data-testid="stChatMessage"]:last-of-type { border-bottom: none !important; }
    [data-testid*="stChatMessageAvatar"] {
        background: var(--pa-canvas) !important;
        border: 1px solid var(--pa-line) !important;
        border-radius: 50% !important;
    }
    [data-testid*="stChatMessageAvatar"][data-testid*="user" i] {
        background: var(--pa-ink) !important;
        border-color: var(--pa-ink) !important;
    }
    [data-testid*="stChatMessageAvatar"][data-testid*="user" i] svg { color: var(--pa-canvas) !important; fill: var(--pa-canvas) !important; }
    code, pre, .stCodeBlock { font-family: 'JetBrains Mono', ui-monospace, monospace !important; }
    :not(pre) > code {
        background: var(--pa-surface-2) !important;
        border: 1px solid var(--pa-line) !important;
        border-radius: 4px !important;
        padding: 0.12em 0.4em !important;
        color: var(--pa-ink) !important;
    }
    [data-testid="stCodeBlock"], pre {
        background: var(--pa-surface-2) !important;
        border: 1px solid var(--pa-line) !important;
        border-radius: 12px !important;
    }
    [data-testid="stBottom"] {
        position: fixed !important;
        bottom: 0 !important;
        left: 300px !important;
        right: 0 !important;
        background: linear-gradient(to top, var(--pa-paper) 60%, rgba(182, 182, 182, 0)) !important;
        border-top: none !important;
        box-shadow: none !important;
        z-index: 50 !important;
        padding-top: 1.25rem !important;
    }
    [data-testid="stBottom"] > div { background: transparent !important; box-shadow: none !important; }
    [data-testid="stBottomBlockContainer"] {
        max-width: 880px !important;
        margin: 0 auto !important;
        padding: 0 2.5rem 1.25rem 2.5rem !important;
        background: transparent !important;
    }
    body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stBottom"] { left: 0 !important; }
    [data-testid="stChatInput"] > div {
        background: var(--pa-canvas) !important;
        border: 1px solid var(--pa-line) !important;
        border-radius: 16px !important;
        box-shadow: var(--pa-shadow-card) !important;
        padding: 0.55rem 0.55rem 0.55rem 1rem !important;
        align-items: center !important;
    }
    [data-testid="stChatInput"] > div:focus-within { border-color: var(--pa-ink) !important; }
    [data-testid="stChatInput"] > div *:not(button):not(svg):not(path) { background-color: transparent !important; }
    [data-testid="stChatInput"] textarea {
        background: transparent !important;
        color: var(--pa-ink) !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 300 !important;
        font-size: 0.95rem !important;
        line-height: 1.5 !important;
        padding: 0.35rem 0 !important;
        min-height: 28px !important;
    }
    [data-testid="stChatInput"] textarea::placeholder { color: var(--pa-muted) !important; opacity: 1 !important; }
    [data-testid="stChatInputSubmitButton"] {
        background: var(--pa-ink) !important;
        color: var(--pa-canvas) !important;
        border-radius: 10px !important;
        border: none !important;
        width: 38px !important; height: 38px !important;
        min-width: 38px !important; min-height: 38px !important;
        padding: 0 !important;
        display: inline-flex !important; align-items: center !important; justify-content: center !important;
        flex-shrink: 0 !important;
    }
    [data-testid="stChatInputSubmitButton"] svg { width: 18px !important; height: 18px !important; }
    [data-testid="stChatInputSubmitButton"] svg path { fill: var(--pa-canvas) !important; }
    [data-testid="stChatInputSubmitButton"]:hover { background: #2a2f2c !important; }
    [data-testid="stChatInputSubmitButton"]:disabled { background: var(--pa-muted) !important; opacity: 0.45 !important; }
    .stButton > button {
        background: var(--pa-canvas) !important;
        color: var(--pa-ink) !important;
        border: 1px solid var(--pa-line) !important;
        border-radius: 12px !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 400 !important;
        letter-spacing: -0.01em !important;
        padding: 0.55rem 0.95rem !important;
        box-shadow: none !important;
    }
    .stButton > button:hover { background: var(--pa-surface-2) !important; border-color: var(--pa-ink) !important; }
    .stButton > button[kind="primary"] {
        background: var(--pa-ink) !important;
        color: var(--pa-canvas) !important;
        border-color: var(--pa-ink) !important;
        box-shadow: var(--pa-shadow-card) !important;
    }
    .stButton > button[kind="primary"]:hover { background: #2a2f2c !important; border-color: #2a2f2c !important; }
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        font-size: 13px !important;
        padding: 0.55rem 0.8rem !important;
        min-height: 38px !important;
        line-height: 1.3 !important;
        white-space: normal !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: var(--pa-muted) !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.18em !important;
        margin: 0.5rem 0 0.75rem 0 !important;
    }
    hr { border: none !important; border-top: 1px solid var(--pa-line-strong) !important; margin: 1rem 0 !important; }
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(14, 18, 16, 0.18); border-radius: 5px; border: 2px solid var(--pa-paper); }
    ::-webkit-scrollbar-thumb:hover { background: rgba(14, 18, 16, 0.32); }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_resource
def init():
    agent = GeneraticAgent()
    if agent.llmclient is None:
        st.error("No usable LLM endpoint configured. Please set up credentials.py.")
        st.stop()
    else: threading.Thread(target=agent.run, daemon=True).start()
    return agent

agent = init()

st.title("Photo Agents")

st.session_state.setdefault('autonomous_enabled', False)

@st.fragment
def render_sidebar():
    st.session_state.setdefault('autonomous_enabled', False)
    llm_options = agent.list_llms()
    current_idx = agent.llm_no
    llm_labels = {idx: f"{idx}: {(name or '').strip()}" for idx, name, _ in llm_options}
    st.caption(f"LLM Core: {llm_labels.get(current_idx, str(current_idx))}", help="Switch backup link")
    selected_idx = st.selectbox("Backup link", [idx for idx, _, _ in llm_options], index=next((i for i, (idx, _, _) in enumerate(llm_options) if idx == current_idx), 0), format_func=llm_labels.get, label_visibility="collapsed", key="sidebar_llm_select")
    if selected_idx != current_idx:
        agent.next_llm(selected_idx); st.rerun(scope="fragment")
    last_reply_time = st.session_state.get('last_reply_time', 0)
    if last_reply_time > 0:
        st.caption(f"Idle time: {int(time.time()) - last_reply_time}s", help="If no reply for 30+ minutes, the system will run an automatic task")
    if st.button("Force stop task"):
        agent.abort(); st.toast("Stop signal sent"); st.rerun()
    if st.button("Re-inject tools"):
        agent.llmclient.last_tools = ''
        try:
            hist_path = os.path.join(script_dir, '..', '..', 'assets', 'tool_usable_history.json')
            with open(hist_path, 'r', encoding='utf-8') as f: tool_hist = json.load(f)
            agent.llmclient.backend.history.extend(tool_hist)
            st.toast(f"Re-injected tools, appended {len(tool_hist)} sample records")
        except Exception as e: st.toast(f"Failed to inject tool examples: {e}")
    if st.button("Desktop Companion"):
        kwargs = {'creationflags': 0x08} if sys.platform == 'win32' else {}
        companion_script = os.path.join(script_dir, 'companion_v2.pyw')
        if not os.path.exists(companion_script): companion_script = os.path.join(script_dir, 'companion.pyw')
        subprocess.Popen([sys.executable, companion_script], **kwargs)
        def _companion_req(q):
            def _do():
                try: urlopen(f'http://127.0.0.1:41983/?{q}', timeout=2)
                except Exception: pass
            threading.Thread(target=_do, daemon=True).start()
        agent._pet_req = _companion_req
        if not hasattr(agent, '_turn_end_hooks'): agent._turn_end_hooks = {}
        def _companion_hook(ctx):
            parts = [f"Turn {ctx.get('turn','?')}"]
            if ctx.get('summary'): parts.append(ctx['summary'])
            if ctx.get('exit_reason'): parts.append('Task complete')
            _companion_req(f'msg={quote(chr(10).join(parts))}')
            if ctx.get('exit_reason'): _companion_req('state=idle')
        agent._turn_end_hooks['pet'] = _companion_hook
        st.toast("Desktop companion launched")

    st.divider()
    if st.button("Start idle autonomous mode"):
        st.session_state.last_reply_time = int(time.time()) - 1800
        st.toast("Last reply time set to 1800s ago"); st.rerun()
    if st.session_state.autonomous_enabled:
        if st.button("Pause autonomous mode"):
            st.session_state.autonomous_enabled = False
            st.toast("Autonomous mode paused"); st.rerun()
        st.caption("Autonomous mode running; will trigger automatically 30 min after you leave")
    else:
        if st.button("Enable autonomous mode", type="primary"):
            st.session_state.autonomous_enabled = True
            st.toast("Autonomous mode enabled"); st.rerun()
        st.caption("Autonomous mode stopped")
with st.sidebar: render_sidebar()

def fold_turns(text):
    """Return list of segments: [{'type':'text','content':...}, {'type':'fold','title':...,'content':...}]"""
    # First protect 4+ backtick blocks via placeholders to avoid mis-splitting nested LLM Running tokens
    _ph = []
    safe = re.sub(r'`{4,}.*?`{4,}', lambda m: (_ph.append(m.group(0)), f'\x00PH{len(_ph)-1}\x00')[1], text, flags=re.DOTALL)
    # Streaming intermediate state: trailing unterminated 4+ backtick block also needs protection
    safe = re.sub(r'`{4,}[^`].*$', lambda m: (_ph.append(m.group(0)), f'\x00PH{len(_ph)-1}\x00')[1], safe, flags=re.DOTALL)
    parts = re.split(r'(\**LLM Running \(Turn \d+\) \.\.\.\*\**)', safe)
    parts = [re.sub(r'\x00PH(\d+)\x00', lambda m: _ph[int(m.group(1))], p) for p in parts]
    if len(parts) < 4: return [{'type': 'text', 'content': text}]
    segments = []
    if parts[0].strip(): segments.append({'type': 'text', 'content': parts[0]})
    turns = []
    for i in range(1, len(parts), 2):
        marker = parts[i]
        content = parts[i+1] if i+1 < len(parts) else ''
        turns.append((marker, content))
    for idx, (marker, content) in enumerate(turns):
        if idx < len(turns) - 1:
            _c = re.sub(r'`{3,}.*?`{3,}|<thinking>.*?</thinking>', '', content, flags=re.DOTALL)
            matches = re.findall(r'<summary>\s*((?:(?!<summary>).)*?)\s*</summary>', _c, re.DOTALL)
            if matches:
                title = matches[0].strip()
                title = title.split('\n')[0]
                if len(title) > 50: title = title[:50] + '...'
            else: title = marker.strip('*')
            segments.append({'type': 'fold', 'title': title, 'content': content})
        else: segments.append({'type': 'text', 'content': marker + content})
    return segments
def render_segments(segments, suffix=''):
    # Re-render the whole block: caller wraps in slot.container() to keep the DOM path stable across reruns
    # (avoids "ghost" gray regions). Heartbeats with unchanged segments leave the diff empty so the front-end
    # shows zero flicker; container/markdown calls still raise StopException, so abort still works.
    for seg in segments:
        if seg['type'] == 'fold':
            with st.expander(seg['title'], expanded=False): st.markdown(seg['content'])
        else:
            st.markdown(seg['content'] + suffix)

def agent_backend_stream(prompt):
    display_queue = agent.put_task(prompt, source="user")
    response = ''
    try:
        while True:
            try: item = display_queue.get(timeout=1)
            except queue.Empty:
                yield response   # heartbeat: lets outer st.markdown() run so Streamlit can check StopException
                continue
            if 'next' in item:
                response = item['next']; yield response
            if 'done' in item:
                yield item['done']; break
    finally: agent.abort()

if "messages" not in st.session_state: st.session_state.messages = []
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # slot=st.empty() + with slot.container(): ... keeps the DOM path identical to the streaming render so reruns line up
        slot = st.empty()
        with slot.container():
            if msg["role"] == "assistant": render_segments(fold_turns(msg["content"]))
            else: st.markdown(msg["content"])

# Scroll-height ghost fix: during streaming, expander open/close mid-animation can leave
# phantom height -> scrollbar long but can't scroll to bottom. Periodically detect & reflow.
try:
    from streamlit import iframe as _st_iframe  # 1.56+
    _embed_html = lambda html, **kw: _st_iframe(html, **{k: max(v, 1) if isinstance(v, int) else v for k, v in kw.items()})
except (ImportError, AttributeError):
    from streamlit.components.v1 import html as _embed_html  # <=1.55
_js_scroll_fix = ("!function(){var p=window.parent;if(p.__sfx)return;p.__sfx=1;"
    "var d=p.document;setInterval(function(){"
    "var m=d.querySelector('section.main');if(!m)return;"
    "var b=m.querySelector('.block-container');if(!b)return;"
    "if(m.scrollHeight>b.scrollHeight+150){"
    "m.style.overflow='hidden';void m.offsetHeight;m.style.overflow=''}"
    "},3000)}()")
# IME composition fix (macOS only) - prevents Enter from submitting during CJK input
_js_ime_fix = ("" if os.name == 'nt' else
    "!function(){if(window.parent.__imeFix)return;window.parent.__imeFix=1;"
    "var d=window.parent.document,c=0;"
    "d.addEventListener('compositionstart',()=>c=1,!0);"
    "d.addEventListener('compositionend',()=>c=0,!0);"
    "function f(){d.querySelectorAll('textarea[data-testid=stChatInputTextArea]')"
    ".forEach(t=>{t.__imeFix||(t.__imeFix=1,t.addEventListener('keydown',e=>{"
    "e.key==='Enter'&&!e.shiftKey&&(e.isComposing||c||e.keyCode===229)&&"
    "(e.stopImmediatePropagation(),e.preventDefault())},!0))})}"
    "f();new MutationObserver(f).observe(d.body,{childList:1,subtree:1})}()")
_embed_html(f'<script>{_js_scroll_fix};{_js_ime_fix}</script>', height=0)

if prompt := st.chat_input("any task?"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cmd = (prompt or "").strip()
    def _reset_and_rerun():
        st.session_state.streaming = False
        st.session_state.stopping = False
        st.session_state.display_queue = None
        st.session_state.partial_response = ""
        st.session_state.reply_ts = ""
        st.session_state.current_prompt = ""
        st.session_state.last_reply_time = int(time.time())
        st.rerun()
    if cmd == "/new":
        st.session_state.messages = [{"role": "assistant", "content": reset_conversation(agent), "time": ts}]
        _reset_and_rerun()
    if cmd.startswith("/continue"):
        m = re.match(r'/continue\s+(\d+)\s*$', cmd.strip())
        sessions = list_sessions(exclude_pid=os.getpid()) if m else []
        idx = int(m.group(1)) - 1 if m else -1
        # Resolve target path BEFORE handle (which snapshots the current log, shifting indices).
        target = sessions[idx][0] if 0 <= idx < len(sessions) else None
        result = handle_frontend_command(agent, cmd)
        history = extract_ui_messages(target) if target and result.startswith('Restored') else None
        tail = [{"role": "assistant", "content": result, "time": ts}]
        if history:
            st.session_state.messages = history + tail
        else:
            st.session_state.messages = list(st.session_state.messages) + \
                [{"role": "user", "content": cmd, "time": ts}] + tail
        _reset_and_rerun()
    st.session_state.messages.append({"role": "user", "content": prompt})
    if hasattr(agent, '_pet_req') and not prompt.startswith('/'): agent._pet_req('state=walk')
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        frozen = 0; live = st.empty(); response = ''
        CURSOR = ' .'
        for response in agent_backend_stream(prompt):
            segs = fold_turns(response)
            n_done = max(0, len(segs) - 1)
            while frozen < n_done:
                with live.container(): render_segments([segs[frozen]])
                live = st.empty(); frozen += 1
            with live.container(): render_segments([segs[-1]], suffix=CURSOR)
        segs = fold_turns(response)
        for i in range(frozen, len(segs)):
            with live.container(): render_segments([segs[i]])
            if i < len(segs) - 1: live = st.empty()
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.last_reply_time = int(time.time())

if st.session_state.autonomous_enabled:
    st.markdown(f"""<div id="last-reply-time" style="display:none">{st.session_state.get('last_reply_time', int(time.time()))}</div>""", unsafe_allow_html=True)
