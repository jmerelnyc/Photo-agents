# Photo Agents Companion

A floating desktop companion for the Photo Agents runtime. Runs in the system tray, animates between idle / walk / run states, and surfaces a chat bubble that talks to your local agent.

## Run

```bash
pythonw -m photoagents.clients.companion_v2
```

Requires the runtime to be reachable (same machine; the companion talks to it over IPC). The runtime in turn requires a valid Photo Agents API key — see the top-level [README](../../README.md).

## Skins

Drop a folder under `photoagents/clients/skins/<name>/` containing:

- `skin.json` — frame metadata (idle, walk, run sequences)
- `skin.png` — sprite atlas
- `pet.png` — tray icon

The companion auto-discovers any folder structured this way.

## Files

| File                  | Purpose                                  |
| --------------------- | ---------------------------------------- |
| `companion.pyw`       | Single-file legacy companion (v1)        |
| `companion_v2.pyw`    | Skin-aware companion (recommended)       |
| `companion.gif`       | Default animated sprite (fallback)       |
| `chat_bubble.png`     | Speech-bubble decoration for chat replies|
| `skins/`              | All available skins                       |

## Tips

- The companion respects the system DPI; on Windows it activates the target window before injecting clicks.
- Right-click the tray icon to switch skins, mute idle chatter, or quit.
