# LinkedIn Queue Assistant (Chrome extension)

Manifest V3, no build step, no dependencies. Reads whatever is currently
rendered on the LinkedIn feed or a Jobs page when you click **Scan this
page**, sends it to your local `server/` for scoring, and lets anything
that clears the bar land in today's queue. Nothing is scraped in the
background, nothing is clicked or visited automatically — it only reads
the DOM you already loaded, on your click.

## Setup

1. In `server/config.toml`, set `[extension].token` to any random string.
2. `chrome://extensions` → enable **Developer mode** (top right) → **Load
   unpacked** → select this `extension/` folder.
3. Make sure the server is running: `python -m webapp` from `server/`.
4. Click the extension icon, paste the same token into the **Token**
   field. **Server URL** defaults to `http://127.0.0.1:3000` (matches
   `config.toml`'s `[web]` section — change both together if you ever move
   the port).

## Use

Open `linkedin.com/feed/...` or a `linkedin.com/jobs/...` page, click the
extension icon, click **Scan this page**. Results show a score, and (if
you've imported a résumé via the `/profile` page) an LLM fit score and
note. Anything that clears the bar is already in today's queue — check
`/` on the web UI.

## If a scan comes back empty

LinkedIn's DOM/class names aren't public API and change without notice.
The selectors live at the top of `content/jobs.js` and `content/feed.js`
— open devtools on the live page, find the actual class names, and update
the `SELECTORS` object. The rest of the extension (messaging, scoring,
queueing) doesn't need to change.
