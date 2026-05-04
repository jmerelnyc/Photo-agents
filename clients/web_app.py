import os, sys
import html
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
try: sys.stdout.reconfigure(errors='replace')
except: pass
try: sys.stderr.reconfigure(errors='replace')
except: pass
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import streamlit as st
try:
    from streamlit import iframe as _st_iframe  # 1.56+
    _embed_html = lambda html, **kw: _st_iframe(html, **{k: max(v, 1) if isinstance(v, int) else v for k, v in kw.items()})
except (ImportError, AttributeError):
    from streamlit.components.v1 import html as _embed_html  # <=1.55
import time, json, re, threading, queue
from datetime import datetime
from photoagents.cli.runtime import PhotoAgentsRuntime as GeneraticAgent

_FAVICON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resources', 'favicon.png'))
st.set_page_config(
    page_title="Photo Agents",
    page_icon=_FAVICON_PATH if os.path.exists(_FAVICON_PATH) else None,
    layout="wide",
)

# --- Photo Agents Theme (matches photo-agents.com) ---
# Variable names kept as --anthropic-* for backwards-compat with the rest of
# the stylesheet; values point at the photo-agents.com palette.
ANTHROPIC_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@200;300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined&display=swap');

/* =============================================================================
   Photo Agents — Streamlit theme matching the photo-agents.com dashboard.
   Layout philosophy:
     - paper #b6b6b6 = outer canvas (main bg + sidebar)
     - canvas #f6f5f1 = surfaces (chat bubbles, active nav, cards)
     - ink #0e1210 = primary text + buttons
     - line #e6e4dd = hairline borders
     - muted #77756d = secondary text
   Variable names kept --anthropic-* for downstream backwards-compat.
============================================================================= */
:root {
    --pa-ink: #0e1210;
    --pa-paper: #b6b6b6;
    --pa-canvas: #f6f5f1;
    --pa-line: #e6e4dd;
    --pa-line-strong: rgba(14, 18, 16, 0.10);
    --pa-muted: #77756d;
    --pa-surface: #f6f5f1;
    --pa-surface-2: #efede6;
    --pa-shadow-card: 0 8px 24px -12px rgba(14, 18, 16, 0.30);

    --anthropic-bg: var(--pa-paper);
    --anthropic-bg-secondary: var(--pa-canvas);
    --anthropic-code-bg: var(--pa-surface-2);
    --anthropic-text: var(--pa-ink);
    --anthropic-text-secondary: var(--pa-muted);
    --anthropic-border: var(--pa-line);
    --anthropic-sidebar-bg: var(--pa-paper);
    --anthropic-accent: var(--pa-ink);
    --anthropic-primary: var(--pa-ink);
    --anthropic-primary-hover: #2a2f2c;
    --anthropic-success: #3f7a44;
    --anthropic-warning: #8a6a2f;
    --anthropic-error: #a8423f;
    --anthropic-info: #3f6a7a;
    --anthropic-font: 'Manrope', ui-sans-serif, system-ui, sans-serif;
    --anthropic-mono: 'JetBrains Mono', 'Source Code Pro', ui-monospace, monospace;
}

/* ===== Global ===== */
html, body, [data-testid="stAppViewContainer"], .stApp {
    background-color: var(--pa-paper) !important;
    color: var(--pa-ink) !important;
    font-family: var(--anthropic-font) !important;
    font-weight: 300 !important;
    letter-spacing: -0.01em !important;
    -webkit-font-smoothing: antialiased !important;
    -moz-osx-font-smoothing: grayscale !important;
}

/* Streamlit 1.5x sidebar / toolbar buttons use Material Symbols ligatures
   (e.g. "keyboard_double_arrow_left"). Our global Manrope on .stApp breaks
   the icon font and the ligature name shows as plain text. Restore the
   correct font on chrome buttons only. */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapseButton"] button span,
[data-testid="stExpandSidebarButton"] button,
[data-testid="stExpandSidebarButton"] button span,
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stSidebarCollapsedControl"] button span,
[data-testid="stSidebarHeader"] button,
[data-testid="stSidebarHeader"] button span,
button[kind="headerNoPadding"],
button[kind="headerNoPadding"] span {
    font-family: "Material Symbols Outlined", "Material Icons", sans-serif !important;
    font-weight: normal !important;
    letter-spacing: normal !important;
    font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24 !important;
    -webkit-font-smoothing: antialiased !important;
}

/* Hide Streamlit chrome we don't want (deploy menu, decoration, status widget),
   but DO NOT touch the toolbar itself — the sidebar expand button lives inside it. */
#MainMenu, [data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stMainMenu"], [data-testid="stMainMenuButton"] {
    visibility: hidden !important;
    display: none !important;
}
/* Keep the toolbar visible so the sidebar expand button is reachable when
   the sidebar is collapsed. Hide every direct child of the toolbar EXCEPT
   the expand-sidebar button. */
header[data-testid="stHeader"] [data-testid="stToolbar"] {
    display: flex !important;
    visibility: visible !important;
    background: transparent !important;
}
header[data-testid="stHeader"] [data-testid="stToolbar"] > *:not(:has([data-testid="stExpandSidebarButton"])) {
    display: none !important;
}
[data-testid="stExpandSidebarButton"],
[data-testid="stExpandSidebarButton"] *,
[data-testid="stExpandSidebarButton"] button,
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapsedControl"] * {
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    width: auto !important;
    height: auto !important;
}
[data-testid="stExpandSidebarButton"] button,
[data-testid="stSidebarCollapsedControl"] button {
    background: var(--pa-canvas) !important;
    border: 1px solid var(--pa-line) !important;
    color: var(--pa-ink) !important;
    border-radius: 10px !important;
    box-shadow: var(--pa-shadow-card) !important;
    z-index: 100 !important;
    width: 36px !important;
    height: 36px !important;
    padding: 6px !important;
}
[data-testid="stExpandSidebarButton"] button svg,
[data-testid="stSidebarCollapsedControl"] button svg {
    color: var(--pa-ink) !important;
    fill: var(--pa-ink) !important;
}
/* In-sidebar collapse button (chevron in the sidebar corner) */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] *,
[data-testid="stSidebarCollapseButton"] button {
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}
[data-testid="stSidebarCollapseButton"] button {
    color: var(--pa-muted) !important;
    background: transparent !important;
}
[data-testid="stSidebarCollapseButton"] button:hover {
    color: var(--pa-ink) !important;
    background: var(--pa-surface-2) !important;
}
/* When sidebar is collapsed, our fixed chat input spans the full width */
body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stBottom"],
body:has([data-testid="stExpandSidebarButton"]) [data-testid="stBottom"] {
    left: 0 !important;
}

/* ===== Top header bar ===== */
[data-testid="stHeader"] {
    background: rgba(182, 182, 182, 0.78) !important;
    backdrop-filter: saturate(180%) blur(10px) !important;
    -webkit-backdrop-filter: saturate(180%) blur(10px) !important;
    border-bottom: 1px solid var(--pa-line-strong) !important;
    height: 56px !important;
    min-height: 56px !important;
}

/* ===== Sidebar (left nav) — cream rail, matches dashboard ===== */
[data-testid="stSidebar"], section[data-testid="stSidebar"] {
    background-color: var(--pa-canvas) !important;
    border-right: 1px solid var(--pa-line) !important;
    padding-top: 0.5rem !important;
    box-shadow: 1px 0 0 var(--pa-line-strong) !important;
    /* Lock the sidebar width — collapse/expand only, no drag-resize */
    width: 300px !important;
    min-width: 300px !important;
    max-width: 300px !important;
    flex-basis: 300px !important;
    resize: none !important;
}
/* ---- Kill Streamlit's sidebar drag-resize handle (every known variant) ---- */
/* The handle's testid/class changes across Streamlit versions, so we cast a
   wide net AND blanket-block the right edge of the sidebar with an overlay. */
[data-testid="stSidebar"] [data-testid="stSidebarResizeHandle"],
[data-testid="stSidebar"] [data-testid*="ResizeHandle" i],
[data-testid="stSidebar"] [data-testid*="resize" i],
[data-testid="stSidebar"] [class*="resize" i],
[data-testid="stSidebar"] [class*="Resize" i],
[data-testid="stSidebar"] [class*="dragHandle" i],
[data-testid="stSidebar"] [class*="DragHandle" i],
[data-testid="stSidebar"] > div[role="separator"],
[data-testid="stSidebarUserContent"] ~ div[role="separator"],
[data-testid="stSidebar"] [aria-orientation="vertical"][role="separator"] {
    display: none !important;
    width: 0 !important;
    pointer-events: none !important;
    cursor: default !important;
    visibility: hidden !important;
}
/* Belt-and-suspenders: cover the right-edge resize zone with an invisible
   overlay that swallows pointer events and forces the default cursor.
   Sidebar is position:relative by Streamlit, so this anchors correctly. */
[data-testid="stSidebar"] {
    position: relative !important;
    overflow-x: hidden !important;
}
[data-testid="stSidebar"]::after {
    content: "";
    position: absolute;
    top: 0;
    right: -1px;
    width: 8px;
    height: 100%;
    z-index: 9999;
    cursor: default !important;
    pointer-events: auto;
    background: transparent;
}
/* Make sure the cursor never turns into ew-resize anywhere in the sidebar */
[data-testid="stSidebar"], [data-testid="stSidebar"] * {
    cursor: default;
}
[data-testid="stSidebar"] button,
[data-testid="stSidebar"] [role="button"],
[data-testid="stSidebar"] a,
[data-testid="stSidebar"] [data-baseweb="select"],
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [role="combobox"],
[data-testid="stSidebar"] [role="option"] {
    cursor: pointer;
}
[data-testid="stSidebar"] input[type="text"],
[data-testid="stSidebar"] textarea {
    cursor: text;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1rem !important; }
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {
    color: var(--pa-ink) !important;
    font-family: var(--anthropic-font) !important;
}
[data-testid="stSidebar"] hr,
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] hr,
hr {
    border: none !important;
    border-top: 1px solid var(--pa-line-strong) !important;
    margin: 1rem 0 !important;
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    color: var(--pa-muted) !important;
    font-size: 12px !important;
    letter-spacing: -0.005em !important;
    font-weight: 400 !important;
    line-height: 1.55 !important;
    word-break: break-word !important;
}
/* Sidebar section eyebrow (the small uppercase label above the picker) */
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
    color: var(--pa-muted) !important;
    font-size: 10.5px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.18em !important;
    font-weight: 500 !important;
}

/* Sidebar selectbox (LLM picker) — ink text on cream pill */
[data-testid="stSidebar"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-baseweb="select"] * {
    color: var(--pa-ink) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: var(--pa-canvas) !important;
    border: 1px solid var(--pa-line) !important;
    border-radius: 12px !important;
    min-height: 44px !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within {
    border-color: var(--pa-ink) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div,
[data-testid="stSidebar"] [data-baseweb="select"] input {
    color: var(--pa-ink) !important;
    background-color: transparent !important;
    font-family: var(--anthropic-font) !important;
    font-weight: 400 !important;
    -webkit-text-fill-color: var(--pa-ink) !important;
}
/* Selected value renderer (the visible text in the closed select) */
[data-testid="stSidebar"] [data-baseweb="select"] [class*="ValueContainer" i],
[data-testid="stSidebar"] [data-baseweb="select"] [class*="SingleValue" i],
[data-testid="stSidebar"] [data-baseweb="select"] [aria-live],
[data-testid="stSidebar"] [data-baseweb="select"] [data-id*="selected" i] {
    color: var(--pa-ink) !important;
    background: transparent !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] svg {
    color: var(--pa-ink) !important;
    fill: var(--pa-ink) !important;
}
/* Dropdown popover (rendered in a portal at the body root, not inside sidebar) */
[data-baseweb="popover"], [data-baseweb="popover"] *,
[role="listbox"], [role="listbox"] * {
    color: var(--pa-ink) !important;
    -webkit-text-fill-color: var(--pa-ink) !important;
}
[data-baseweb="popover"] [role="listbox"], [role="listbox"] {
    background: var(--pa-canvas) !important;
    border: 1px solid var(--pa-line) !important;
    border-radius: 14px !important;
    box-shadow: var(--pa-shadow-card) !important;
    padding: 0.35rem !important;
}
[role="option"] {
    color: var(--pa-ink) !important;
    background: transparent !important;
    border-radius: 10px !important;
    font-family: var(--anthropic-font) !important;
    padding: 0.45rem 0.7rem !important;
}
[role="option"]:hover, [role="option"][aria-selected="true"] {
    background: var(--pa-surface-2) !important;
    color: var(--pa-ink) !important;
}

/* Sidebar buttons */
[data-testid="stSidebar"] .stButton > button {
    width: 100% !important;
    background: var(--pa-canvas) !important;
    color: var(--pa-ink) !important;
    border: 1px solid var(--pa-line) !important;
    border-radius: 10px !important;
    font-weight: 400 !important;
    font-size: 13px !important;
    font-family: var(--anthropic-font) !important;
    letter-spacing: -0.005em !important;
    padding: 0.55rem 0.8rem !important;
    min-height: 38px !important;
    line-height: 1.3 !important;
    white-space: normal !important;
    word-break: keep-all !important;
    box-shadow: none !important;
    transition: background-color 120ms ease, border-color 120ms ease !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--pa-surface-2) !important;
    border-color: var(--pa-ink) !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: var(--pa-muted) !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.18em !important;
    margin: 0.5rem 0 0.75rem 0 !important;
}

/* ===== Main content — chat well sits on the paper background ===== */
[data-testid="stMain"], [data-testid="stAppViewContainer"] > .main {
    background-color: var(--pa-paper) !important;
}
[data-testid="stMainBlockContainer"], .main .block-container {
    background-color: var(--pa-canvas) !important;
    border: 1px solid var(--pa-line) !important;
    border-radius: 20px !important;
    box-shadow: var(--pa-shadow-card) !important;
    padding: 2.25rem 2.5rem 7rem 2.5rem !important;
    max-width: 880px !important;
    margin-top: 1.25rem !important;
    margin-bottom: 1rem !important;
    min-height: calc(100vh - 56px - 6.5rem) !important;
}
/* Reserved earlier — keep only one rule for padding-bottom so input doesn't overlap content */
/* Chat bubbles drop their own surface treatment now that the well IS the surface */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0.25rem 0 1rem 0 !important;
    border-bottom: 1px solid var(--pa-line) !important;
    border-radius: 0 !important;
    margin-bottom: 0.85rem !important;
}
[data-testid="stChatMessage"]:last-of-type { border-bottom: none !important; }

/* ===== Headings ===== */
h1, .stTitle, [data-testid="stHeading"] h1 {
    color: var(--pa-ink) !important;
    font-family: var(--anthropic-font) !important;
    font-weight: 200 !important;
    letter-spacing: -0.04em !important;
    font-size: 2.25rem !important;
    margin-bottom: 0.25rem !important;
}
h2 {
    color: var(--pa-ink) !important;
    font-family: var(--anthropic-font) !important;
    font-weight: 300 !important;
    letter-spacing: -0.03em !important;
}
h3, h4, h5, h6 {
    color: var(--pa-ink) !important;
    font-family: var(--anthropic-font) !important;
    font-weight: 500 !important;
    letter-spacing: -0.02em !important;
}

/* Body text */
p, .stMarkdown p, [data-testid="stMarkdownContainer"] p {
    color: var(--pa-ink) !important;
    font-family: var(--anthropic-font) !important;
    font-weight: 300 !important;
    line-height: 1.65 !important;
}

/* Captions / muted */
.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--pa-muted) !important;
    font-family: var(--anthropic-font) !important;
}

/* ===== Chat messages (typography) ===== */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
    color: var(--pa-ink) !important;
}
.msg-timestamp {
    color: var(--pa-muted) !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.22em !important;
    margin-bottom: 0.5rem !important;
    font-weight: 400 !important;
}

/* Chat avatars: user = ink circle, assistant = white surface circle */
[data-testid*="stChatMessageAvatar"] {
    background: var(--pa-canvas) !important;
    border: 1px solid var(--pa-line) !important;
    border-radius: 50% !important;
    box-shadow: 0 2px 6px rgba(14, 18, 16, 0.06) !important;
}
[data-testid*="stChatMessageAvatar"]:has(svg[data-testid*="user" i]),
[data-testid*="stChatMessageAvatar"][data-testid*="user" i] {
    background: var(--pa-ink) !important;
    border-color: var(--pa-ink) !important;
}
[data-testid*="stChatMessageAvatar"][data-testid*="user" i] svg {
    color: var(--pa-canvas) !important;
    fill: var(--pa-canvas) !important;
}

/* ===== Code ===== */
code, pre, .stCodeBlock, .stCode {
    font-family: var(--anthropic-mono) !important;
}
:not(pre) > code {
    background: var(--pa-surface-2) !important;
    color: var(--pa-ink) !important;
    border: 1px solid var(--pa-line) !important;
    border-radius: 4px !important;
    padding: 0.12em 0.4em !important;
    font-size: 0.88em !important;
}
[data-testid="stCodeBlock"], pre {
    background: var(--pa-surface-2) !important;
    border: 1px solid var(--pa-line) !important;
    border-radius: 12px !important;
}
[data-testid="stCodeBlock"] code, pre code {
    background: transparent !important;
    color: var(--pa-ink) !important;
    border: none !important;
    padding: 0.85rem 1rem !important;
}

/* ===== Chat input docked footer (pinned to viewport bottom) ===== */
[data-testid="stBottom"] {
    position: fixed !important;
    bottom: 0 !important;
    left: 300px !important;   /* sidebar width */
    right: 0 !important;
    background: linear-gradient(to top, var(--pa-paper) 60%, rgba(182, 182, 182, 0)) !important;
    border-top: none !important;
    box-shadow: none !important;
    z-index: 50 !important;
    padding-top: 1.25rem !important;
}
[data-testid="stBottom"] > div {
    background: transparent !important;
    border-top: none !important;
    box-shadow: none !important;
}
/* Match the chat well's horizontal frame exactly so the input pill aligns
   with the messages above (same max-width, same horizontal padding). */
[data-testid="stBottomBlockContainer"] {
    max-width: 880px !important;
    width: 100% !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding: 0 2.5rem 1.25rem 2.5rem !important;
    background: transparent !important;
    box-sizing: border-box !important;
}
/* Streamlit nests the input inside an extra block — make sure none of the
   intermediate wrappers add their own margin/padding that breaks alignment. */
[data-testid="stBottomBlockContainer"] > div,
[data-testid="stBottom"] [data-testid="stVerticalBlock"] {
    width: 100% !important;
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
}
/* When sidebar is collapsed, the bottom should span full width */
[data-testid="stSidebar"][aria-expanded="false"] ~ [data-testid="stMain"] [data-testid="stBottom"],
body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stBottom"] {
    left: 0 !important;
}
[data-testid="stChatInput"] {
    background: transparent !important;
    border: none !important;
}
[data-testid="stChatInput"] > div {
    background: var(--pa-canvas) !important;
    border: 1px solid var(--pa-line) !important;
    border-radius: 16px !important;
    box-shadow: var(--pa-shadow-card) !important;
    padding: 0.55rem 0.55rem 0.55rem 1rem !important;
    align-items: center !important;
}
[data-testid="stChatInput"] > div:focus-within {
    border-color: var(--pa-ink) !important;
}
/* Streamlit wraps the textarea in BaseWeb divs with a hardcoded #f0f2f6 bg.
   Make every descendant background transparent so only our cream pill shows. */
[data-testid="stChatInput"] > div *:not(button):not(svg):not(path) {
    background-color: transparent !important;
}
[data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: var(--pa-ink) !important;
    font-family: var(--anthropic-font) !important;
    font-weight: 300 !important;
    font-size: 0.95rem !important;
    line-height: 1.6 !important;
    caret-color: var(--pa-ink) !important;
    padding: 0.45rem 0 !important;
    min-height: 28px !important;
    height: auto !important;
    resize: none !important;
    display: flex !important;
    align-items: center !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: var(--pa-muted) !important;
    opacity: 1 !important;
    font-weight: 300 !important;
    line-height: 1.6 !important;
}
[data-testid="stChatInput"] button[kind="primary"],
[data-testid="stChatInputSubmitButton"] {
    background: var(--pa-ink) !important;
    color: var(--pa-canvas) !important;
    border-radius: 10px !important;
    border: none !important;
    width: 38px !important;
    height: 38px !important;
    min-width: 38px !important;
    min-height: 38px !important;
    padding: 0 !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-shrink: 0 !important;
    transition: background-color 120ms ease !important;
}
[data-testid="stChatInputSubmitButton"] svg {
    width: 18px !important;
    height: 18px !important;
}
[data-testid="stChatInputSubmitButton"] svg path {
    fill: var(--pa-canvas) !important;
}
[data-testid="stChatInput"] button[kind="primary"]:hover,
[data-testid="stChatInputSubmitButton"]:hover {
    background: #2a2f2c !important;
}
[data-testid="stChatInputSubmitButton"]:disabled {
    background: var(--pa-muted) !important;
    opacity: 0.45 !important;
}

/* ===== Generic primary buttons (e.g. Stop generation) ===== */
.stButton > button[kind="primary"],
.stButton > button[kind="primary"] * {
    color: var(--pa-canvas) !important;   /* cream text on ink — high contrast */
}
.stButton > button[kind="primary"] {
    background: var(--pa-ink) !important;
    border: 1px solid var(--pa-ink) !important;
    border-radius: 12px !important;
    font-family: var(--anthropic-font) !important;
    font-weight: 500 !important;
    letter-spacing: -0.01em !important;
    box-shadow: var(--pa-shadow-card) !important;
    padding: 0.55rem 1.1rem !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover * {
    background: #2a2f2c !important;
    border-color: #2a2f2c !important;
    color: var(--pa-canvas) !important;
}
.stButton > button[kind="primary"]:focus,
.stButton > button[kind="primary"]:focus-visible {
    outline: 2px solid var(--pa-ink) !important;
    outline-offset: 2px !important;
    box-shadow: var(--pa-shadow-card) !important;
}
/* Generic (non-primary) main-area buttons sit on the cream well —
   give them a clear ink-on-canvas treatment so they're never invisible. */
[data-testid="stMainBlockContainer"] .stButton > button:not([kind="primary"]),
.main .stButton > button:not([kind="primary"]) {
    background: var(--pa-canvas) !important;
    color: var(--pa-ink) !important;
    border: 1px solid var(--pa-line) !important;
    border-radius: 10px !important;
    font-family: var(--anthropic-font) !important;
    font-weight: 400 !important;
    box-shadow: none !important;
}
[data-testid="stMainBlockContainer"] .stButton > button:not([kind="primary"]):hover,
.main .stButton > button:not([kind="primary"]):hover {
    background: var(--pa-surface-2) !important;
    border-color: var(--pa-ink) !important;
    color: var(--pa-ink) !important;
}
/* BaseWeb wraps button text in an inner div that can inherit theme colors —
   force button label color so it never becomes dark-on-dark. */
[data-testid="stChatInputSubmitButton"] *,
button[kind="primary"] [data-testid="stMarkdownContainer"],
button[kind="primary"] [data-testid="stMarkdownContainer"] * {
    color: var(--pa-canvas) !important;
}

/* ===== Toasts ===== */
[data-baseweb="toast"], [data-testid="stToast"],
[data-baseweb="toast"] *, [data-testid="stToast"] * {
    color: var(--pa-canvas) !important;
    -webkit-text-fill-color: var(--pa-canvas) !important;
}
[data-baseweb="toast"], [data-testid="stToast"] {
    background: var(--pa-ink) !important;
    border-radius: 12px !important;
    font-family: var(--anthropic-font) !important;
    border: none !important;
    box-shadow: var(--pa-shadow-card) !important;
}

/* ===== Tooltips (the bubble that appears on `help=` icons) ===== */
[data-baseweb="tooltip"],
[data-testid="stTooltipContent"],
div[role="tooltip"] {
    background: var(--pa-ink) !important;
    color: var(--pa-canvas) !important;
    border-radius: 8px !important;
    font-family: var(--anthropic-font) !important;
    font-size: 12px !important;
    font-weight: 400 !important;
    padding: 0.5rem 0.7rem !important;
    border: none !important;
    box-shadow: var(--pa-shadow-card) !important;
}
[data-baseweb="tooltip"] *,
[data-testid="stTooltipContent"] *,
div[role="tooltip"] * {
    color: var(--pa-canvas) !important;
    background: transparent !important;
}
/* Tooltip arrow */
[data-baseweb="tooltip"] [class*="Arrow" i] {
    background: var(--pa-ink) !important;
}
/* The (?) help icon itself */
[data-testid="stTooltipIcon"], [data-testid="stTooltipHoverTarget"] svg {
    color: var(--pa-muted) !important;
    fill: var(--pa-muted) !important;
}
[data-testid="stTooltipIcon"]:hover svg,
[data-testid="stTooltipHoverTarget"]:hover svg {
    color: var(--pa-ink) !important;
    fill: var(--pa-ink) !important;
}

/* ===== Alerts (st.error, st.warning, st.info, st.success) ===== */
[data-testid="stAlert"], [data-baseweb="notification"] {
    background: var(--pa-canvas) !important;
    border: 1px solid var(--pa-line) !important;
    border-left: 3px solid var(--pa-ink) !important;
    border-radius: 12px !important;
    color: var(--pa-ink) !important;
    box-shadow: var(--pa-shadow-card) !important;
    padding: 0.85rem 1rem !important;
}
[data-testid="stAlert"] *, [data-baseweb="notification"] * {
    color: var(--pa-ink) !important;
    background-color: transparent !important;
}
[data-testid="stAlertContentError"], [data-testid="stAlert"][data-baseweb="notification"][kind="negative"] {
    border-left-color: #a8423f !important;
}
[data-testid="stAlertContentWarning"], [data-testid="stAlert"][kind="warning"] {
    border-left-color: #8a6a2f !important;
}
[data-testid="stAlertContentSuccess"], [data-testid="stAlert"][kind="positive"] {
    border-left-color: #3f7a44 !important;
}
[data-testid="stAlertContentInfo"], [data-testid="stAlert"][kind="info"] {
    border-left-color: #3f6a7a !important;
}

/* ===== Disabled states ===== */
button:disabled, [aria-disabled="true"] {
    opacity: 0.5 !important;
    cursor: not-allowed !important;
}
[data-testid="stChatInput"] textarea:disabled {
    color: var(--pa-muted) !important;
    -webkit-text-fill-color: var(--pa-muted) !important;
    background: transparent !important;
}

/* ===== Misc ===== */
[data-testid="stStatusWidget"] { display: none !important; }
[data-testid="stMarkdownContainer"] strong { font-weight: 500 !important; }
[data-testid="stMarkdownContainer"] em { font-style: italic; color: var(--pa-muted) !important; }
[data-testid="stMarkdownContainer"] a {
    color: var(--pa-ink) !important;
    text-decoration: underline !important;
    text-decoration-color: var(--pa-muted) !important;
}
[data-testid="stMarkdownContainer"] a:hover {
    text-decoration-color: var(--pa-ink) !important;
}
[data-testid="stMarkdownContainer"] blockquote {
    border-left: 3px solid var(--pa-ink) !important;
    color: var(--pa-muted) !important;
    margin-left: 0 !important;
    padding-left: 1rem !important;
}

/* Scrollbars */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: rgba(14, 18, 16, 0.18);
    border-radius: 5px;
    border: 2px solid var(--pa-paper);
}
::-webkit-scrollbar-thumb:hover { background: rgba(14, 18, 16, 0.32); }

/* Hide the gear toggle the original theme injected — sidebar handles it */
#sidebar-gear-toggle { display: none !important; }
body:has([data-testid="stSidebar"][aria-expanded="true"]) #sidebar-gear-toggle {
    display: none !important;
}

/* The legacy JS injects a "Settings" <span> next to the collapse chevron;
   it overlaps the sidebar caption row. Hide it — the sidebar layout is
   self-explanatory now. */
#custom-sidebar-settings-title {
    display: none !important;
}

/* ---- Sidebar header cleanup (Streamlit 1.57+) ----
   The sidebar header container ships with a keyboard-shortcut hint and
   sometimes a screen-reader label that can render as duplicated text on top
   of the sidebar. Strip every non-button child out of the header. */
[data-testid="stSidebarHeader"] {
    background: transparent !important;
    padding: 0.25rem 0.5rem !important;
    min-height: 32px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
}
/* Hide every Streamlit-injected hint / shortcut label inside the sidebar header */
[data-testid="stSidebarHeader"] [data-testid*="Shortcut" i],
[data-testid="stSidebarHeader"] [data-testid*="Hint" i],
[data-testid="stSidebarHeader"] [data-testid*="keyboard" i],
[data-testid="stSidebarHeader"] [class*="shortcut" i],
[data-testid="stSidebarHeader"] [class*="Shortcut" i],
[data-testid="stSidebarHeader"] [class*="hint" i],
[data-testid="stSidebarHeader"] [class*="Hint" i],
[data-testid="stSidebarHeader"] kbd,
[data-testid="stSidebarHeader"] code,
[data-testid="stSidebarHeader"] [aria-live],
[data-testid="stSidebar"] kbd {
    display: none !important;
    visibility: hidden !important;
}
/* Same defensive hide outside the header — a stray <kbd> with "Ctrl+B"
   sometimes lands directly under stSidebar. */
[data-testid="stSidebar"] [data-testid*="Shortcut" i],
[data-testid="stSidebar"] [data-testid*="Keyboard" i],
[data-testid="stSidebar"] [class*="shortcut" i],
[data-testid="stSidebar"] [class*="keyboardShortcut" i] {
    display: none !important;
    visibility: hidden !important;
}
/* Hide screen-reader-only labels that may have lost their sr-only clip */
.stApp [class*="visuallyHidden" i],
.stApp .sr-only,
.stApp [aria-hidden="true"][class*="screen" i] {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
}
</style>
"""
ANTHROPIC_SELECTBOX_SCRIPT = """
<div></div>
<script>
(function() {
    const hostWin = window.parent;
    const doc = hostWin.document;
    const LABEL_TEXT = 'Backup link';
    const EXTRA_WIDTH = 56;
    const TIMER_KEY = '__anthropicSelectboxFixedWidthTimer';
    const FONT_LABELS = {
        '100': 'Default (100%)',
        '112.5': 'Larger (112.5%)',
        '125': 'Even larger (125%)',
        '137.5': 'Largest (137.5%)'
    };

    function measureTextWidth(text, sourceEl) {
        const canvas = hostWin.__anthropicSelectboxMeasureCanvas || (hostWin.__anthropicSelectboxMeasureCanvas = doc.createElement('canvas'));
        const ctx = canvas.getContext('2d');
        const style = sourceEl ? hostWin.getComputedStyle(sourceEl) : null;
        const font = style ? `${style.fontWeight} ${style.fontSize} ${style.fontFamily}` : '400 14px sans-serif';
        ctx.font = font;
        return Math.ceil(ctx.measureText(text || '').width);
    }

    function ensureSidebarSettingsTitle() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (!sidebar) return;
        const collapseBtn = sidebar.querySelector('button[kind="header"], [data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"]');
        if (!collapseBtn || !collapseBtn.parentElement) return;
        let title = doc.getElementById('custom-sidebar-settings-title');
        if (!title) {
            title = doc.createElement('span');
            title.id = 'custom-sidebar-settings-title';
            title.textContent = 'Settings';
            title.style.cssText = 'font-size:14px;font-weight:600;color:rgb(38,39,48);margin-right:8px;line-height:1;display:inline-flex;align-items:center;white-space:nowrap;';
        }
        if (collapseBtn.previousElementSibling !== title) {
            collapseBtn.parentElement.insertBefore(title, collapseBtn);
        }
    }

    function applyLiveFontPreview() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (!sidebar) return;
        const sliderLabel = Array.from(sidebar.querySelectorAll('label, p')).find((el) => el.textContent && el.textContent.trim() === 'Font size');
        if (!sliderLabel) return;
        const container = sliderLabel.closest('[data-testid="stWidgetLabel"]')?.parentElement?.parentElement || sliderLabel.closest('[data-testid="stSlider"]') || sliderLabel.closest('div');
        if (!container) return;
        const input = container.querySelector('input[type="range"]');
        if (!input) return;
        const caption = container.querySelector('[data-testid="stCaptionContainer"] p, p');

        const updateFont = () => {
            const raw = parseFloat(input.value);
            if (!Number.isFinite(raw)) return;
            doc.documentElement.style.setProperty('font-size', raw + '%', 'important');
            if (caption) {
                const key = String(raw % 1 === 0 ? raw.toFixed(0) : raw);
                caption.textContent = FONT_LABELS[key] || `${raw.toFixed(1)}%`;
            }
        };

        if (input.dataset.liveFontBound !== '1') {
            input.addEventListener('input', updateFont);
            input.addEventListener('change', updateFont);
            input.dataset.liveFontBound = '1';
        }
        updateFont();
    }

    function applyFixedWidth() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (!sidebar) return;
        const boxes = sidebar.querySelectorAll('[data-testid="stSelectbox"]');
        boxes.forEach((box) => {
            const labelNode = box.querySelector('label [data-testid="stMarkdownContainer"] p, label p');
            if (!labelNode || labelNode.textContent.trim() !== LABEL_TEXT) return;
            const selectRoot = box.querySelector('[data-baseweb="select"]');
            const trigger = selectRoot && selectRoot.firstElementChild;
            const maxLabelNode = box.querySelector('[data-testid="sidebar-llm-max-label"]');
            const text = ((maxLabelNode && maxLabelNode.textContent) || '').trim();
            if (!selectRoot || !trigger || !text) return;

            const textWidth = measureTextWidth(text, trigger);
            const targetWidth = Math.min(sidebar.clientWidth - 32, Math.max(96, textWidth + EXTRA_WIDTH));
            const valueWrap = trigger.firstElementChild;
            const arrowWrap = valueWrap && valueWrap.nextElementSibling;
            const valueNode = valueWrap && valueWrap.querySelector('[value]');

            box.style.setProperty('width', targetWidth + 'px', 'important');
            box.style.setProperty('max-width', targetWidth + 'px', 'important');
            box.style.setProperty('flex', '0 0 ' + targetWidth + 'px', 'important');

            selectRoot.style.setProperty('width', targetWidth + 'px', 'important');
            selectRoot.style.setProperty('min-width', targetWidth + 'px', 'important');
            selectRoot.style.setProperty('max-width', targetWidth + 'px', 'important');

            trigger.style.setProperty('width', targetWidth + 'px', 'important');
            trigger.style.setProperty('min-width', targetWidth + 'px', 'important');
            trigger.style.setProperty('max-width', targetWidth + 'px', 'important');
            trigger.style.setProperty('padding-right', '0px', 'important');
            trigger.style.setProperty('justify-content', 'flex-start', 'important');
            trigger.style.setProperty('box-sizing', 'border-box', 'important');

            if (valueWrap) {
                valueWrap.style.setProperty('flex', '1 1 auto', 'important');
                valueWrap.style.setProperty('min-width', '0px', 'important');
                valueWrap.style.setProperty('max-width', 'calc(100% - 24px)', 'important');
                valueWrap.style.setProperty('padding-right', '4px', 'important');
            }
            if (valueNode) {
                valueNode.style.setProperty('max-width', '100%', 'important');
            }
            if (arrowWrap) {
                arrowWrap.style.setProperty('margin-left', 'auto', 'important');
                arrowWrap.style.setProperty('padding-right', '0px', 'important');
                arrowWrap.style.setProperty('width', '24px', 'important');
                arrowWrap.style.setProperty('min-width', '24px', 'important');
                arrowWrap.style.setProperty('display', 'flex', 'important');
                arrowWrap.style.setProperty('justify-content', 'flex-end', 'important');
                arrowWrap.style.setProperty('align-items', 'center', 'important');
                arrowWrap.style.setProperty('overflow', 'visible', 'important');
            }
        });
        ensureSidebarSettingsTitle();
        applyLiveFontPreview();
    }

    if (hostWin[TIMER_KEY]) {
        hostWin.clearInterval(hostWin[TIMER_KEY]);
    }
    hostWin[TIMER_KEY] = hostWin.setInterval(applyFixedWidth, 300);
    hostWin.setTimeout(applyFixedWidth, 60);
    hostWin.setTimeout(applyFixedWidth, 300);
    hostWin.setTimeout(applyFixedWidth, 1000);
    applyFixedWidth();
})();
</script>
"""

@st.cache_resource
def init():
    agent = GeneraticAgent()
    if agent.llmclient is None:
        st.error("No usable LLM endpoint configured. Please add sider_cookie or oai_apikey + oai_apibase to credentials.py and restart.")
        st.stop()
    else:
        threading.Thread(target=agent.run, daemon=True).start()
    return agent


def build_dynamic_font_css(scale_percent: float) -> str:
    root_percent = max(100.0, min(200.0, float(scale_percent)))
    rem_scale = root_percent / 100.0
    return f"""
<style id="dynamic-font-scale-style">
:root, html, body, [data-testid="stAppViewContainer"], .stApp {{
    font-size: {root_percent:.1f}% !important;
}}
body, [data-testid="stAppViewContainer"], .stApp {{
    --app-font-scale: {rem_scale:.3f};
}}
[data-testid="stAppViewContainer"], .stApp, .stApp p, .stApp li, .stApp label,
.stApp div[data-testid="stMarkdownContainer"], .stApp textarea, .stApp input,
.stApp button, .stApp [data-testid="stChatMessageContent"], .stApp .stCaption {{
    font-size: calc(1rem * var(--app-font-scale, 1)) !important;
}}
</style>
"""


def build_dynamic_font_update_script(scale_percent: float) -> str:
    css = json.dumps(build_dynamic_font_css(scale_percent))
    return f"""
<script>
(() => {{
    const cssText = {css};
    const parser = new DOMParser();
    const parsed = parser.parseFromString(cssText, 'text/html');
    const nextStyle = parsed.querySelector('#dynamic-font-scale-style');
    if (!nextStyle) return;
    const hostDoc = window.parent && window.parent.document ? window.parent.document : document;
    const existing = hostDoc.querySelector('#dynamic-font-scale-style');
    if (existing) {{
        existing.textContent = nextStyle.textContent;
    }} else {{
        hostDoc.head.appendChild(nextStyle);
    }}
}})();
</script>
"""


def build_header_agent_badge_script() -> str:
    return """
<script>
(() => {
    const hostWin = window.parent || window;
    const hostDoc = hostWin.document || document;
    const BADGE_ID = 'photo-agents-header-badge';
    const STYLE_ID = 'photo-agents-header-badge-style';

    const ensureStyle = () => {
        if (hostDoc.getElementById(STYLE_ID)) return;
        const style = hostDoc.createElement('style');
        style.id = STYLE_ID;
        style.textContent = `
            #${BADGE_ID} {
                position: absolute;
                left: 50%;
                top: 50%;
                transform: translate(-50%, -50%);
                display: inline-flex;
                align-items: center;
                justify-content: center;
                white-space: nowrap;
                font-family: 'Manrope', ui-sans-serif, system-ui, sans-serif;
                font-size: 1.35rem;
                font-weight: 200;
                letter-spacing: -0.035em;
                line-height: 1;
                color: #0e1210;
                padding: 0;
                border-radius: 0;
                background: transparent;
                border: none;
                box-shadow: none;
                pointer-events: none;
                z-index: 20;
            }
        `;
        hostDoc.head.appendChild(style);
    };

    const findHeaderRoot = () => {
        const candidates = [
            'header[data-testid="stHeader"]',
            '[data-testid="stHeader"]',
            'header',
        ];
        for (const selector of candidates) {
            const root = hostDoc.querySelector(selector);
            if (root) return root;
        }
        return null;
    };

    const ensureBadge = () => {
        ensureStyle();
        const headerRoot = findHeaderRoot();
        if (!headerRoot) return;
        headerRoot.style.position = 'relative';

        let badge = hostDoc.getElementById(BADGE_ID);
        if (!badge) {
            badge = hostDoc.createElement('div');
            badge.id = BADGE_ID;
            badge.textContent = 'Photo Agents';
        }
        if (badge.parentElement !== headerRoot) {
            headerRoot.appendChild(badge);
        }

        // Typography is owned by the stylesheet above — do not sync from h1
        // (the chat title h1 is much larger and would blow the badge up).
    };

    if (hostWin.__photoAgentsHeaderBadgeTimer) {
        hostWin.clearInterval(hostWin.__photoAgentsHeaderBadgeTimer);
    }
    hostWin.__photoAgentsHeaderBadgeTimer = hostWin.setInterval(ensureBadge, 500);
    hostWin.setTimeout(ensureBadge, 80);
    hostWin.setTimeout(ensureBadge, 400);
    ensureBadge();
})();
</script>
"""

agent = init()

def init_session_state():
    for key, value in {
        'agent_name': 'Photo Agents', 'streaming': False, 'stopping': False, 'display_queue': None,
        'partial_response': '', 'reply_ts': '', 'current_prompt': '', 'selected_llm_idx': agent.llm_no,
        'autonomous_enabled': False, 'messages': [],
    }.items(): st.session_state.setdefault(key, value)

init_session_state()

# Inject Anthropic theme
st.markdown(ANTHROPIC_CSS, unsafe_allow_html=True)
st.markdown(build_dynamic_font_css(110.0), unsafe_allow_html=True)
_embed_html(ANTHROPIC_SELECTBOX_SCRIPT, height=0, width=0)
_embed_html(build_header_agent_badge_script(), height=0, width=0)

st.session_state.agent_name = 'Photo Agents'
with st.chat_message("assistant"):
    st.markdown(f'<div class="msg-timestamp">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>', unsafe_allow_html=True)
    st.write("Welcome to Photo Agents~")


@st.fragment
def render_sidebar():
    llm_options, current_idx = agent.list_llms(), agent.llm_no
    st.session_state.selected_llm_idx = current_idx
    llm_labels = {idx: f"{idx}: {(name or '').strip()}" for idx, name, _ in llm_options}
    st.caption(f"Current LLM: {current_idx}: {agent.get_llm_name()}", help="Choose a backup link below")
    st.markdown(f'<div data-testid="sidebar-llm-max-label" style="display:none">{html.escape(max(llm_labels.values(), key=len, default=""))}</div>', unsafe_allow_html=True)
    selected_idx = st.selectbox("Backup link", [idx for idx, _, _ in llm_options], index=next((i for i, (idx, _, _) in enumerate(llm_options) if idx == current_idx), 0), format_func=llm_labels.get, key="sidebar_llm_select")
    if selected_idx != current_idx:
        agent.next_llm(selected_idx)
        st.session_state.selected_llm_idx = selected_idx
        st.toast(f"Switched to backup link: {llm_labels[selected_idx]}")
        st.rerun()
    st.divider()
    if st.button("Re-inject System Prompt"):
        agent.llmclient.last_tools = ''
        st.toast("System Prompt will be re-injected on the next turn")

with st.sidebar: render_sidebar()


def start_agent_task(prompt):
    st.session_state.display_queue = agent.put_task(prompt, source="user")
    st.session_state.streaming, st.session_state.stopping, st.session_state.partial_response = True, False, ''
    st.session_state.reply_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.current_prompt = prompt


def poll_agent_output(max_items=20):
    q = st.session_state.display_queue
    if q is None:
        st.session_state.streaming = False
        return False
    done = False
    for _ in range(max_items):
        try:
            item = q.get_nowait()
        except queue.Empty:
            break
        if 'next' in item: st.session_state.partial_response = item['next']
        if 'done' in item:
            st.session_state.partial_response = item['done']
            done = True
            break
    if done: st.session_state.streaming = st.session_state.stopping = False; st.session_state.display_queue = None
    return done


def _get_response_segments(text):
    return [p for p in re.split(r'(?=\*\*LLM Running \(Turn \d+\) \.\.\.\*\*)', text) if p.strip()] or [text]

def render_message(role, content, ts='', unsafe_allow_html=True):
    with st.chat_message(role):
        if ts: st.markdown(f'<div class="msg-timestamp">{ts}</div>', unsafe_allow_html=True)
        st.markdown(content, unsafe_allow_html=unsafe_allow_html)

def finish_streaming_message():
    reply_ts = st.session_state.reply_ts
    st.session_state.messages.extend({"role": "assistant", "content": seg, "time": reply_ts} for seg in _get_response_segments(st.session_state.partial_response))
    st.session_state.last_reply_time = int(time.time())
    st.session_state.partial_response = st.session_state.reply_ts = st.session_state.current_prompt = ''

def render_streaming_area():
    if not st.session_state.streaming: return
    with st.container():
        st.markdown('<span class="stop-btn-anchor"></span>', unsafe_allow_html=True)
        if st.button("Stop generation", type="primary"):
            agent.abort(); st.session_state.stopping = True; st.toast("Stop signal sent"); st.rerun()
    reply_ts = st.session_state.reply_ts
    with st.empty().container():
        segments = _get_response_segments(st.session_state.partial_response)
        for i, seg in enumerate(segments): render_message("assistant", seg + ("" if i < len(segments) - 1 else " ."), ts=reply_ts, unsafe_allow_html=False)
    if poll_agent_output(): finish_streaming_message()
    else: time.sleep(0.2)
    st.rerun()

for msg in st.session_state.messages: render_message(msg["role"], msg["content"], ts=msg.get("time", ""), unsafe_allow_html=True)
if st.session_state.streaming: render_streaming_area()
if prompt := st.chat_input("Enter a command", disabled=st.session_state.streaming):
    st.session_state.messages.append({"role": "user", "content": prompt, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    start_agent_task(prompt)
    st.rerun()
