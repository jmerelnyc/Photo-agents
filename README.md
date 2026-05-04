# Photo Agents

Autonomous, self-evolving **Photo Agents** — a perceive / reason / act framework for photo-aware agents that operate your computer the way you do.

> "100% autonomous, self-evolving agents."
> [photo-agents.com](https://photo-agents.com)

## What it is

Photo Agents is a single Python package that bundles:

- A streaming **agent loop** (`photoagents.core.loop.run_agent_session`) that drives any tool-calling LLM through a perceive → reason → act cycle.
- A **multi-provider LLM router** (`photoagents.llm.router`) with first-class support for Anthropic Claude (native), OpenAI GPT (native), and a mixin failover session.
- A **physical-execution toolset**: file I/O, sandboxed code execution (Python / PowerShell / bash), browser automation via a Chrome DevTools Protocol bridge, and a layered memory system (working / global / SOP / session archive).
- Pluggable **clients**: a polished Streamlit web app, a PyQt desktop app, a desktop companion, and ready-to-run bots for Telegram, QQ, Feishu, WeCom, and DingTalk.
- Optional **observability** via Langfuse and a cron-style scheduler.

The whole thing is gated by a remote-validated **Photo Agents API key** so usage stays accountable.

## Install

```bash
pip install photoagents
# or, with every optional client and integration
pip install "photoagents[all]"
```

Photo Agents needs Python 3.10+.

## Get an API key

Photo Agents requires a license key, validated against `https://photo-agents.com/v1/keys/validate`. Sign in and create one at:

> **https://photo-agents.com/account/keys**

Then make it available to the runtime in any of these ways (checked in order):

1. Environment variable: `PHOTOAGENTS_API_KEY=pk_live_...`
2. Saved config: `~/.photoagents/config.json` field `api_key`
3. Interactive prompt on first run (offered to be saved automatically)

A successful validation is cached for 24 hours so the gate stays fast.

## LLM credentials

Copy the credentials template and fill in your provider key:

```bash
# from the repo root
cp photoagents/config/keys_template.py credentials.py
# then edit credentials.py and uncomment one of the provider configs
```

The runtime also accepts a JSON form (`credentials.json`) with the same shape.

## Run

```bash
# Interactive REPL on your terminal
python -m photoagents

# One-shot file-IO mode
python -m photoagents --task my_task --input "List the largest files in this directory."

# Reflect / watchdog mode (your check() function fires the next task)
python -m photoagents --reflect photoagents/evolution/scheduler.py
```

## GUI clients

Photo Agents ships several optional frontends. Pick whichever fits your workflow:

| Client                         | Launch command                                      |
| ------------------------------ | --------------------------------------------------- |
| Streamlit web app + webview    | `pythonw -m photoagents.cli.launcher`               |
| Service hub (start/stop)       | `pythonw -m photoagents.cli.hub`                    |
| Desktop app (PyQt)             | `python -m photoagents.clients.desktop_app`         |
| Desktop companion              | `pythonw -m photoagents.clients.companion_v2`      |
| Telegram bot                   | `python -m photoagents.clients.telegram_client`     |
| Feishu / WeCom / DingTalk / QQ | `python -m photoagents.clients.<feishu|wecom|...>_client` |

The launcher and hub both call the same API key gate before starting any service, so they will refuse to launch anything if your key is missing or revoked.

## On-disk state

| Path                              | What lives there                                  |
| --------------------------------- | -------------------------------------------------- |
| `~/.photoagents/config.json`      | API key + license validation cache                 |
| `~/.photoagents/global_mem.txt`   | Long-term L2 facts                                 |
| `~/.photoagents/sessions/`        | L4 raw session archives                            |
| `~/.photoagents/skill_index/`     | Vector index for skill / SOP search                |
| `~/.photoagents/temp/`            | Per-task scratch (logs, intermediate output)       |

## Project layout

```
photoagents/
├── auth/        License gate (remote-validated API key)
├── cli/         python -m photoagents, GUI launcher, service hub
├── clients/     Web / desktop / chat-platform frontends
├── config/      credentials.py template
├── core/        Agent loop and tool dispatcher
├── evolution/   Reflection / scheduler scripts (the "self-evolving" loop)
├── integrations/Optional third-party hooks (Langfuse, etc.)
├── llm/         Multi-provider session router
├── resources/   System prompt, tool schema, CDP bridge, demo media
├── skills/      L3 SOPs and helper modules (browser, vision, OCR, ...)
└── web/         DOM simplifier and Chrome DevTools Protocol driver
```

## License

MIT. See [LICENSE](LICENSE).

## Status

Status: beta. APIs may change before 1.0.

