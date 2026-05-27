# CII Assistant

Agentic AI assistant for CII documentation at https://docs.oort.io.

- **Backend**: Python 3.11+ / FastAPI, ChromaDB (local persistent), Voyage embeddings, Anthropic Claude tool-use loop with SSE streaming.
- **Frontend**: Vite + React + TypeScript + Tailwind chat UI with streaming markdown + citations.

## Layout

```
cii-assistant/
├── backend/   # FastAPI + ingestion + agent
└── frontend/  # Vite React chat UI
```

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
npm run dev   # http://localhost:5173, proxies /api → http://localhost:8000
```

## Webex bot (dev mode)

The backend exposes `POST /api/webex/webhook` so a Webex bot can answer questions
in DMs and group spaces. Setup for local dev:

### 1. Create the bot

1. Go to https://developer.webex.com/my-apps → **Create a Bot**.
2. Copy the **bot access token**.

### 2. Configure the backend

Add to `backend/.env`:

```
WEBEX_BOT_TOKEN=<bot access token>
WEBEX_WEBHOOK_SECRET=<any random string, e.g. `openssl rand -hex 16`>
WEBEX_MAX_CONCURRENT=8            # max parallel in-flight agent runs
WEBEX_ACK_MESSAGE=Got it — searching the CII docs, one moment…
```

`get_settings()` is `lru_cache`'d, so **restart uvicorn** after editing `.env`.

### 3. Expose the backend with a Cloudflare tunnel

```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:8000 --protocol http2
```

`--protocol http2` avoids QUIC, which is blocked on many corp networks.
The command prints a `https://<random>.trycloudflare.com` URL — copy it.
Note: this URL changes every time you restart `cloudflared`; for a stable
URL, set up a [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-local-tunnel/).

### 4. Register the webhook with Webex

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

### 5. Test

In Webex, search the bot username (`<botname>@webex.bot`), DM it
"What is CII?", and you should see an acknowledgement followed by the
doc-grounded answer with markdown citations.

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

## Deferred

- Auth on the API.
- Production deployment target.
- Retrieval eval harness.
