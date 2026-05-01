# TMWebDriver SOP

- Use the `web_scan` / `web_execute_js` tools directly. This file only documents quirks and pitfalls.
- Underlying layer: `photoagents/web/driver.py` controls the user's Chrome via an extension (preserving login/Cookies).
- It is not Selenium/Playwright — it keeps the user's browser session.

## General behavior
- WARNING: when using `await` inside `web_execute_js`, you must explicitly `return` to get the value (the wrapper is async; without `return` you get null).
- `web_scan` automatically pierces same-origin iframes; cross-origin iframes need CDP or postMessage (see below).

## Limitations (`isTrusted`)
- JS events have `isTrusted=false`; sensitive operations (file upload, certain buttons) may be blocked. Prefer **the CDP bridge** for those.
- WARNING: clicking a button in JS may fail to open a new tab — likely popup blocker; try a CDP click.
- File upload: JS cannot fill an `<input type=file>`. Prefer a CDP batch: `getDocument` -> `querySelector` -> `DOM.setFileInputFiles`. Fallback: physical click via ljqCtrl.
- When converting to physical coordinates: `physX = (screenX + rectCenterX) * dpr`, `physY = (screenY + chromeH + rectCenterY) * dpr`; where `chromeH = outerHeight - innerHeight`.

## Navigation
- `web_scan` only reads the current page; switch sites via `web_execute_js` + `location.href='url'`.

## Google image search
- Class names are obfuscated; do not hard-code them. Click results via the `[role=button]` div.
- Use web_scan to filter sidebars; once a result is open use JS: text via `document.body.innerText`; for the big image, iterate `img` and pick the largest by `naturalWidth`.
- "Visit" link: iterate `a`, find the one whose `textContent.includes('visit')`, take its `href`.
- Thumbnails: extract `img[src^="data:image"]` directly; the big image's src may be truncated, use `return img.src`.

## Chrome PDF download
Scenario: a PDF link is previewed in the browser instead of downloaded.
```js
fetch('PDF_URL').then(r=>r.blob()).then(b=>{
  const a=document.createElement('a');
  a.href=URL.createObjectURL(b);
  a.download='filename.pdf';
  a.click();
});
```
Note: needs same origin or CORS; if cross-origin, navigate to the target domain first.

## Chrome background-tab throttling
- In a background tab, `setTimeout` is intensively throttled by Chrome to >= 1 min; avoid setTimeout-based polling in extension scripts.
- Some SPA pages need CDP `Page.bringToFront` to load their data.

## CDP bridge (tmwd_cdp_bridge extension) — preferred
Extension path: `assets/tmwd_cdp_bridge/` (must be installed; declares debugger permission).
WARNING: the TID identifier is auto-generated on first run into `assets/tmwd_cdp_bridge/config.js` (gitignored); the extension references it via the manifest.
Calling: `web_execute_js`'s `script` accepts a JSON string directly (the tool layer detects the object form, routes via WS -> background.js cmd dispatch).
```js
// pass a JSON string directly as the script parameter; no DOM manipulation needed
web_execute_js script='{"cmd": "cookies"}'
web_execute_js script='{"cmd": "tabs"}'
web_execute_js script='{"cmd": "cdp", "tabId": N, "method": "...", "params": {...}}'
web_execute_js script='{"cmd": "batch", "commands": [...]}'
// the return value is the raw JSON result
```
Communication paths: JSON-string-direct (preferred) | TID DOM (TID element + MutationObserver, what web_scan/execute_js depend on under the hood).
Single command: `{cmd:'tabs'}` | `{cmd:'cookies'}` | `{cmd:'cdp', tabId:N, method:'...', params:{...}}` | `{cmd:'management', method:'list|reload|disable|enable', extId:'...'}`.
- management: `list` returns all extensions; `reload`/`disable`/`enable` need `extId`.
- batch (mixed): `{cmd:'batch', commands:[{cmd:'cookies'},{cmd:'tabs'},{cmd:'cdp',...},...]}`.
  - Returns `{ok:true, results:[...]}`; multiple commands per request, CDP lazily attaches and reuses the session.
  - Sub-commands inherit the outer batch's `tabId` (e.g. cookies returns the URL of the current page).
  - `$N.path` references field `path` in result N (0-indexed), e.g. `"nodeId":"$2.root.nodeId"`.
  - WARNING: if an earlier batch command fails, downstream `$N` references silently become undefined; check the `ok` status of each result entry.
  - Typical file upload: getDocument(**depth:1**) -> querySelector(`input[type=file]`) -> setFileInputFiles.
  - Notes:
    - Within a single chain, keep nodeId sources consistent — do not mix querySelector paths with performSearch paths.
    - After upload, the front-end framework may not notice; if needed, dispatch `input`/`change` events from JS.
    - Before upload, check `input.accept`; with multiple inputs, distinguish via accept and parent container semantics.
    - When waiting for an element, prefer `DOM.performSearch('input[type=file]')` lightweight polling.
    - For transient inputs, the goal is to **shorten the gap between discovery and setFileInputFiles**: prefer same-batch completion; otherwise use a DOM event listener; monkey-patching is a last resort.
  - WARNING about `tabId`: CDP defaults to `sender.tab.id` (the injected page); for cross-tab work pass `tabId` explicitly or query tabs in the same batch first.
- Cross-tab without bringing to front: pass `tabId` to drive any background tab.

## CDP click full lifecycle (unverified, BBS#23)
- Generic clicks need a **three-event sequence**: `mouseMoved` -> `mousePressed` -> `mouseReleased` (50-100ms apart).
  - Skipping `mouseMoved` breaks hover-dependent components (MUI Tooltip, Ant Design Dropdown, ...).
  - WARNING: autofill release is special — only `mousePressed` is needed (see autofill section).
- Coordinate correction (when the page uses transform:scale or zoom):
  ```js
  var scale = window.visualViewport ? window.visualViewport.scale : 1;
  var zoom = parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
  var realX = x * zoom; var realY = y * zoom;
  ```
- Clicking an element inside an iframe: composite the coordinates `finalX = iframeRect.x + elRect.x`.
  - Cross-origin iframe cannot expose `contentDocument`:
  - WARNING: `Target.getTargets`/`Target.attachToTarget` return "Not allowed" through the CDP bridge (chrome.debugger limitation).
  - Verified workaround: `Page.getFrameTree` to find the iframe frameId -> `Page.createIsolatedWorld({frameId})` to get a contextId -> `Runtime.evaluate({expression, contextId})` to run JS inside the iframe.
  - Batch chain: `$0.frameTree.childFrames` to find the frame whose URL matches, `$1.executionContextId` to feed `evaluate`.
  - The postMessage relay only works when a content script has been injected into the iframe; third-party payment iframes typically have none.

## CDP text input (unverified, BBS#23)
- `insertText` is fast but emits no key events; controlled components need a manual `input` dispatch.
- For full keyboard simulation, use `dispatchKeyEvent` per key.

## CDP DOM piercing through closed Shadow DOM (unverified, BBS#24/#25)
- `DOM.getDocument({depth:-1, pierce:true})` pierces every shadow boundary (including closed).
- `DOM.querySelector({nodeId, selector})` to locate -> `DOM.getBoxModel({nodeId})` for coordinates.
- `getBoxModel` returns content as eight values [x1,y1,...x4,y4]; the center is the **average of all four points**: `centerX = sum(x)/4, centerY = sum(y)/4`.
  - WARNING: do not simplify to a diagonal average — under transform:rotate/skew the four points are not a rectangle.
- `querySelector` **cannot cross shadow boundaries with combined selectors**; do it stepwise: find the host first, then look for the child inside its shadow.
- WARNING: `nodeId` becomes invalid after DOM mutations -> use `backendNodeId` (more stable) or refresh via getDocument.

## autofill capture and login
Detection: web_scan output shows the input has `data-autofilled="true"` and the value displays as a protected placeholder (not the real value — Chrome's protection requires a click to release).
- WARNING **prerequisite: must call CDP `Page.bringToFront` first**. Chrome only releases autofill values on the foreground tab; physical clicks on a background tab do not work.
- One-shot release + login: `bringToFront` -> `mousePressed` on any field (no Released needed; one release frees the whole page) -> wait 500ms -> dispatch `input`/`change` events -> click login.

## Captcha / page screenshots
- Preferred CDP screenshot: `Page.captureScreenshot` (format:'png') -> base64; works without bringing the tab to front; full-page hi-res.
- Captcha canvas/img: `canvas.toDataURL()` from JS gives the cleanest base64.

## simphtml + TMWebDriver debugging
- simphtml debugging must inject JS into the real browser via `code_run` (the Python side cannot simulate the DOM).
- `d=TMWebDriver()`, `d.set_session('url_pattern')`, `d.execute_js(code)` -> returns `{'data': value}`.
- simphtml: `str(simphtml.optimize_html_for_tokens(html))` — returns a BS4 Tag, must be `str()`'d.

## Cannot connect troubleshooting
When `web_scan` fails, troubleshoot in order (auto-detect first, user assistance last):
1. Browser not open? Check the browser process (tasklist/ps); if missing, start it and open a real URL (warning: `about:blank` etc. do not load extensions).
2. WS background dead? If port 18766 on this host is not listening it is dead -> manually run **and keep alive in the background** `from photoagents.web.driver import TMWebDriver; TMWebDriver()`.
3. Extension not installed? Read `Secure Preferences` in the Chrome user dir -> look in `extensions.settings` for an entry whose `path` contains `tmwd_cdp_bridge`.
   Found -> extension is installed, look elsewhere; not found -> follow web_setup_sop.
4. If everything looks right but it still cannot connect -> ask the user for help.
