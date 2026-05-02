"""`/continue` command: list & restore past model_responses sessions.
Pure functions + one `install(cls)` monkey-patch entry. No side effects at import.
"""
import ast, glob, json, os, re, time
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'temp', 'model_responses')
_LOG_GLOB = os.path.join(_LOG_DIR, 'model_responses_*.txt')
_BLOCK_RE = re.compile(r'^=== (Prompt|Response) ===.*?\n(.*?)(?=^=== (?:Prompt|Response) ===|\Z)',
                       re.DOTALL | re.MULTILINE)
_SUMMARY_RE = re.compile(r'<summary>\s*(.*?)\s*</summary>', re.DOTALL)

def _rel_time(mtime):
    d = int(time.time() - mtime)
    if d < 60: return f'{d}s ago'
    if d < 3600: return f'{d // 60}m ago'
    if d < 86400: return f'{d // 3600}h ago'
    return f'{d // 86400}d ago'

def _pairs(content):
    blocks, pairs, pending = _BLOCK_RE.findall(content or ''), [], None
    for label, body in blocks:
        if label == 'Prompt': pending = body.strip()
        elif pending is not None:
            pairs.append((pending, body.strip())); pending = None
    return pairs

def _first_user(pairs):
    for p, _ in pairs:
        try: msg = json.loads(p)
        except Exception: continue
        if not isinstance(msg, dict): continue
        for blk in msg.get('content', []) or []:
            if isinstance(blk, dict) and blk.get('type') == 'text':
                t = (blk.get('text') or '').strip()
                if t and '<history>' not in t and not t.startswith('### [WORKING MEMORY]'):
                    return t
    for p, _ in pairs[:1]:
        for line in p.splitlines():
            s = line.strip()
            if s and not s.startswith('###'): return s
    return ''


def _last_summary(pairs):
    for _, response_body in reversed(pairs):
        try:
            blocks = ast.literal_eval(response_body)
        except Exception:
            continue
        if not isinstance(blocks, list):
            continue
        text_parts = []
        for block in blocks:
            if isinstance(block, dict) and block.get('type') == 'text':
                text = block.get('text', '')
                if isinstance(text, str) and text:
                    text_parts.append(text)
        match = _SUMMARY_RE.search('\n'.join(text_parts))
        if match:
            summary = match.group(1).strip()
            if summary:
                return summary
    return ''


def _preview_text(pairs):
    return _last_summary(pairs) or _first_user(pairs)

def _parse_native_history(pairs):
    history = []
    for p, r in pairs:
        try: user_msg = json.loads(p)
        except Exception: return None
        try: blocks = ast.literal_eval(r)
        except Exception: return None
        if not (isinstance(user_msg, dict) and user_msg.get('role') == 'user'): return None
        if not isinstance(blocks, list): return None
        history.append(user_msg)
        history.append({'role': 'assistant', 'content': blocks})
    return history

def list_sessions(exclude_pid=None):
    """Newest-first list of (path, mtime, first_user_text, n_rounds)."""
    files = glob.glob(_LOG_GLOB)
    if exclude_pid is not None:
        tag = f'model_responses_{exclude_pid}.txt'
        files = [f for f in files if not f.endswith(tag)]
    out = []
    for f in files:
        try:
            with open(f, encoding='utf-8', errors='replace') as fh:
                content = fh.read()
        except Exception: continue
        pairs = _pairs(content)
        if not pairs: continue
        out.append((f, os.path.getmtime(f), _preview_text(pairs), len(pairs)))
    out.sort(key=lambda x: x[1], reverse=True)
    return out
_MD_ESCAPE_RE = re.compile(r'([\\`*_\[\]])')
def _escape_md(s): return _MD_ESCAPE_RE.sub(r'\\\1', s)


def _agent_clients(agent):
    clients = []
    for client in getattr(agent, 'llmclients', []) or []:
        if client not in clients:
            clients.append(client)
    current = getattr(agent, 'llmclient', None)
    if current is not None and current not in clients:
        clients.insert(0, current)
    return clients


def _replace_backend_history(agent, history):
    backend = getattr(getattr(agent, 'llmclient', None), 'backend', None)
    if backend is not None and hasattr(backend, 'history'):
        backend.history = list(history or [])


def _current_log_path(pid=None):
    pid = os.getpid() if pid is None else pid
    return os.path.join(_LOG_DIR, f'model_responses_{pid}.txt')


def _snapshot_current_log(pid=None):
    """Persist current PID log as a standalone recoverable snapshot, then clear it."""
    path = _current_log_path(pid)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            content = fh.read()
    except Exception:
        return None
    if not _pairs(content):
        return None
    os.makedirs(_LOG_DIR, exist_ok=True)
    pid = os.getpid() if pid is None else pid
    stamp = time.strftime('%Y%m%d_%H%M%S')
    snapshot = os.path.join(_LOG_DIR, f'model_responses_snapshot_{pid}_{stamp}_{time.time_ns() % 1_000_000_000:09d}.txt')
    with open(snapshot, 'w', encoding='utf-8', errors='replace') as fh:
        fh.write(content)
    with open(path, 'w', encoding='utf-8', errors='replace'):
        pass
    return snapshot


def reset_conversation(agent, message='New conversation started, current context cleared'):
    """Abort current work and clear all known frontend-visible conversation state."""
    try:
        agent.abort()
    except Exception:
        pass
    _snapshot_current_log()
    if hasattr(agent, 'history'):
        agent.history = []
    for client in _agent_clients(agent):
        backend = getattr(client, 'backend', None)
        if backend is not None and hasattr(backend, 'history'):
            backend.history = []
        if hasattr(client, 'last_tools'):
            client.last_tools = ''
    if hasattr(agent, 'handler'):
        agent.handler = None
    return message

def format_list(sessions, limit=20):
    if not sessions: return 'No restorable sessions'
    lines = ['**Restorable sessions** (type `/continue N` to restore session N):', '']
    for i, (_, mtime, first, n) in enumerate(sessions[:limit], 1):
        preview = _escape_md((first or '(no preview)').replace('\n', ' ')[:60])
        lines.append(f'{i}. `{_rel_time(mtime)}` * **{n} rounds** * {preview}')
    return '\n'.join(lines)

def restore(agent, path):
    """Restore session at path. Returns (msg, is_full)."""
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            content = fh.read()
    except Exception as e: return f'Read failed: {e}', False
    pairs = _pairs(content)
    if not pairs: return f'{os.path.basename(path)} is empty or has invalid format', False
    history = _parse_native_history(pairs)
    name = os.path.basename(path)
    if history is not None:
        agent.abort()
        _replace_backend_history(agent, history)
        return f'Restored {len(pairs)} full conversation rounds ({name})\n(Written to backend.history; you can continue directly)', True
    from photoagents.clients.client_common import _restore_native_history, _restore_text_pairs
    summary = _restore_text_pairs(content) or _restore_native_history(content)
    if not summary: return f'{name} could not be parsed (not native and no summary extractable)', False
    agent.abort()
    agent.history.extend(summary)
    n = sum(1 for l in summary if l.startswith('[USER]: '))
    return f'Non-native format, fell back to summary restore of {n} rounds ({name})\n(Please send a new question to continue)', False

def handle(agent, query, display_queue):
    """Dispatch /continue or /continue N. Returns None if consumed else original query."""
    s = (query or '').strip()
    if s == '/continue':
        display_queue.put({'done': format_list(list_sessions(exclude_pid=os.getpid())), 'source': 'system'})
        return None
    m = re.match(r'/continue\s+(\d+)\s*$', s)
    if m:
        sessions = list_sessions(exclude_pid=os.getpid())
        idx = int(m.group(1)) - 1
        if not (0 <= idx < len(sessions)):
            display_queue.put({'done': f'Index out of range (valid 1-{len(sessions)})', 'source': 'system'})
            return None
        reset_conversation(agent, message=None)
        msg, _ = restore(agent, sessions[idx][0])
        display_queue.put({'done': msg, 'source': 'system'})
        return None
    return query


def _user_text(prompt_body):
    """User-typed text from a prompt JSON; '' if this is an agent auto-continuation."""
    try: msg = json.loads(prompt_body)
    except Exception: return ''
    if not isinstance(msg, dict): return ''
    for blk in msg.get('content', []) or []:
        if isinstance(blk, dict) and blk.get('type') == 'text':
            t = (blk.get('text') or '').strip()
            if t and not t.startswith('### [WORKING MEMORY]'): return t
    return ''


def _assistant_text(response_body):
    """Joined text from a response blocks repr; '' on parse failure."""
    try: blocks = ast.literal_eval(response_body)
    except Exception: return ''
    if not isinstance(blocks, list): return ''
    return '\n'.join(b['text'] for b in blocks
                     if isinstance(b, dict) and b.get('type') == 'text'
                     and isinstance(b.get('text'), str) and b['text'].strip())


_TURN_MARK = '**LLM Running (Turn {}) ...**\n\n'


def extract_ui_messages(path):
    """Parse a model_responses log into [{role, content}, ...] for UI replay.

    Auto-continuation turns are folded into one assistant bubble with Turn markers,
    matching live chat rendering via fold_turns().
    """
    try:
        with open(path, encoding='utf-8', errors='replace') as f: content = f.read()
    except Exception: return []

    rounds = []
    for prompt, response in _pairs(content):
        user = _user_text(prompt)
        if user or not rounds: rounds.append((user, []))
        rounds[-1][1].append(_assistant_text(response))

    out = []
    for user, turns in rounds:
        if not user or not any(turns): continue
        body = '\n\n'.join(t if i == 0 else _TURN_MARK.format(i + 1) + t
                           for i, t in enumerate(turns))
        out += [{'role': 'user', 'content': user},
                {'role': 'assistant', 'content': body}]
    return out


def handle_frontend_command(agent, query, exclude_pid=None):
    """Frontend-friendly /continue entry that returns text directly."""
    s = (query or '').strip()
    exclude_pid = os.getpid() if exclude_pid is None else exclude_pid
    if s == '/continue':
        return format_list(list_sessions(exclude_pid=exclude_pid))
    m = re.match(r'/continue\s+(\d+)\s*$', s)
    if not m:
        return 'Usage: /continue or /continue N'
    sessions = list_sessions(exclude_pid=exclude_pid)
    idx = int(m.group(1)) - 1
    if not (0 <= idx < len(sessions)):
        return f'Index out of range (valid 1-{len(sessions)})'
    reset_conversation(agent, message=None)
    msg, _ = restore(agent, sessions[idx][0])
    return msg


def install(cls):
    """Wrap cls._handle_slash_cmd so /continue is handled before original dispatch."""
    orig = cls._handle_slash_cmd
    if getattr(orig, '_continue_patched', False): return
    def patched(self, raw_query, display_queue):
        if (raw_query or '').startswith('/continue'):
            r = handle(self, raw_query, display_queue)
            if r is None: return None
        return orig(self, raw_query, display_queue)
    patched._continue_patched = True
    cls._handle_slash_cmd = patched
