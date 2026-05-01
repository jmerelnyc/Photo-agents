# Web Toolchain Initial Setup SOP

If `web_scan` and `web_execute_js` already work, this SOP is unnecessary.
Use this only on first install, when `code_run` is available but the web tools have not yet been configured.

## Goal
With only system-level access (`code_run`), establish web interaction (`web_scan` / `web_execute_js`).

## Pre-flight: detect the browser

## Install the tmwd_cdp_bridge extension
Extension path: `../assets/tmwd_cdp_bridge/` (Manifest V3 Chrome extension; provides CDP debugger + scripting + cookie capabilities).

### Auto-open the extension management page
`chrome://extensions` cannot be opened from the command line or JS; use the clipboard + address bar workaround.

### Install steps (Chrome's extension page is hard to automate)
1. Open the extensions page; turn on Developer Mode.
2. Click "Load unpacked" and pick `assets/tmwd_cdp_bridge/`, or have the user drag the folder in.
3. An "Error" message can be ignored — usually it is just because the extension has not connected to Photo Agents yet.

## Verify
WARNING: a "no available tabs" message from `web_scan` does not necessarily mean the extension failed to install — it can also mean the browser is closed or only has a blank page open.
Do not improvise: open a real page first with `start "" "https://www.baidu.com"`, then run `web_scan` again.
If it still does not work, automation cannot reliably detect which is the default browser, which browser the extension is installed in, or whether it is installed at all — at that point, ask the user for help.
