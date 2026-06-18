# Setup Guide

## Prerequisites

1. **Terminal access** — macOS: Terminal.app or iTerm2; Windows: PowerShell or Windows Terminal. [2-min intro](https://www.youtube.com/watch?v=aKRYQsKR46I) if you've never used one.
2. **Xcode Command Line Tools** (macOS only) — run `xcode-select --install`.
3. **Claude Code** — **requires Cisco VPN** for installation and GitHub access. Follow the [claudegate getting started guide](https://wwwin-github.cisco.com/netascode/claudegate/blob/master/docs/getting-started.md) to install and authenticate. Once set up, the `claude` command should work in your terminal.
4. **Homebrew** (macOS only) — `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
5. **Python 3.11+** — `brew install python@3.11` (macOS) or [download](https://www.python.org/downloads/) (Windows).
6. **Node.js 18+** — `brew install node` (macOS) or [download](https://nodejs.org/) (Windows).

## Get the project

1. Click **Code** → **Download ZIP** from this repo page.
2. Unzip (double-click on macOS, right-click → "Extract All" on Windows).
3. Open a terminal and navigate into the folder:
   ```bash
   cd ~/Downloads/cii-assistant-haiku-fallback-routing
   ```
4. Start Claude Code:
   ```bash
   claude
   ```

## Option A: Claude Code skills (recommended)

Type these in the Claude Code prompt:

| | Command | What it does |
|--|---------|--------------|
| 🟢 Required | `/run-cii-dev` | Starts backend and frontend |
| 🟢 Required | `/reindex` | Populates the search index from docs.oort.io |
| ⚪ Optional | `/start-webex-webhook` | Sets up the Webex bot tunnel and webhook |

> Claude will ask you to approve commands — press **Enter** or type **y** to approve.

### Tips

- Always run `/reindex` after `/run-cii-dev` on first use.
- If the Webex bot stops responding, run `/start-webex-webhook` again.
- To stop everything, press **Ctrl+C**.

---

## Option B: Manual CLI commands

## Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # fill in ANTHROPIC_API_KEY and VOYAGE_API_KEY
```

Run the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Build the index (full crawl of docs.oort.io):

```bash
python scripts/reindex.py        # incremental (only re-embed changed pages)
python scripts/reindex.py --force  # full re-embed
```

Or kick off ingest via the API:

```bash
curl -X POST localhost:8000/api/ingest -H 'content-type: application/json' -d '{"force":false}'
curl localhost:8000/api/status
```

Chat (SSE):

```bash
curl -N -X POST localhost:8000/api/chat \
  -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"What is CII?"}]}'
```

## Frontend

```bash
cd frontend
npm install
npm run dev              # http://localhost:5173, proxies /api → http://localhost:8000
npm run dev -- --host    # bind 0.0.0.0 so other machines on the network can reach it
```

## Webex bot (dev mode)

The backend exposes `POST /api/webex/webhook` so the **CIIcompass** bot can answer questions
in DMs and group spaces. To find the bot, search for **CIIcompass** in Webex.

### 1. Configure the backend

Copy the example env file and fill in the Webex bot token:

```bash
cp backend/.env.example backend/.env
```

The Webex-related variables in `backend/.env`:

```
WEBEX_BOT_TOKEN=<paste the CIIcompass bot access token>
WEBEX_WEBHOOK_SECRET=<paste the existing webhook secret, or generate one with `openssl rand -hex 16`>
```

The other Webex settings (`WEBEX_MAX_CONCURRENT`, `WEBEX_ACK_MESSAGE`) have sensible defaults in `.env.example`.

`get_settings()` is `lru_cache`'d, so **restart uvicorn** after editing `.env`.

### 2. Expose the backend with a Cloudflare tunnel

```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:8000 --protocol http2
```

`--protocol http2` avoids QUIC, which is blocked on many corp networks.
The command prints a `https://<random>.trycloudflare.com` URL — copy it.
Note: this URL changes every time you restart `cloudflared`; for a stable
URL, set up a [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-local-tunnel/).

### 3. Register the webhook with Webex

```bash
cd backend
WEBEX_BOT_TOKEN=$(grep '^WEBEX_BOT_TOKEN=' .env | cut -d= -f2-)
WEBEX_WEBHOOK_SECRET=$(grep '^WEBEX_WEBHOOK_SECRET=' .env | cut -d= -f2-)
TUNNEL_URL="https://<your-tunnel>.trycloudflare.com"

curl -X POST https://webexapis.com/v1/webhooks \
  -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"CIICompass\",
    \"targetUrl\": \"$TUNNEL_URL/api/webex/webhook\",
    \"resource\": \"messages\",
    \"event\": \"created\",
    \"secret\": \"$WEBEX_WEBHOOK_SECRET\"
  }"
```

A `200` with `"status":"active"` means it's registered. To list / delete
existing webhooks (URLs go stale every time you restart the tunnel):

```bash
# list
curl -s -H "Authorization: Bearer $WEBEX_BOT_TOKEN" https://webexapis.com/v1/webhooks
# delete
curl -X DELETE -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
  https://webexapis.com/v1/webhooks/<webhook-id>
```

Or just run `/start-webex-webhook` in Claude Code to handle all of this automatically.

### 4. Test

In Webex, search for **CIIcompass**, DM it "What is CII?", and you should
see an acknowledgement followed by the doc-grounded answer with markdown citations.

### Operational notes

- In group spaces the bot only sees messages where it's `@mentioned`.
- Each Webex message is a fresh agent run (no per-user history yet).
- `WEBEX_MAX_CONCURRENT` caps simultaneous in-flight agent runs; excess
  questions get a queued notice and wait.
- Webhook signatures are verified with `WEBEX_WEBHOOK_SECRET` when set.
  Leave it blank to disable verification (not recommended).

## Architecture notes

- **Ingestion** (`app/ingest/`): sitemap-driven crawl → `markdownify` → heading-aware chunker (~800 tokens, 100 overlap, heading path prefixed) → Voyage `voyage-3` embeddings (batches of 128) → ChromaDB collection `cii_docs`. Incremental: per-URL content hash stored in `data/url_hashes.json`; unchanged pages are skipped on re-run.
- **Retrieval** (`app/rag/`): vector search over Chroma + BM25 rerank (60/40 blend) on the candidate pool.
- **Agent** (`app/agent/`): Claude `claude-opus-4-7` with adaptive thinking, prompt caching on system + tool definitions. Tools exposed: `search_docs`, `fetch_page`, `list_sections`. Server loops on `tool_use` stop reason until the model produces a final answer, streaming text deltas and citation events over SSE.
- **API** (`app/api/`): `POST /api/chat` (SSE), `POST /api/ingest` (background job, with progress + 30 min timeout), `GET /api/status`, `POST /api/webex/webhook` (Webex bot).
- **Scheduler** (`app/scheduler.py`): daily incremental re-index at 01:00 local. Env: `REINDEX_ENABLED`, `REINDEX_HOUR`.
