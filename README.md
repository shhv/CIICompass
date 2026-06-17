# CII Assistant

Agentic AI assistant for CII documentation at https://docs.oort.io.

## Problem Statement

**Finding answers in CII docs takes too long.**

Cisco Identity Intelligence documentation spans hundreds of pages across a complex, deeply nested site. Engineers, partners, and support teams routinely spend 10-15 minutes hunting for a single answer — jumping between sections, re-reading pages, and often giving up or escalating to a human expert. This wasted time multiplies across every person who touches CII, creating a drag on onboarding, incident response, and customer support.

## Solution Overview

**An AI agent that reads the docs so your team doesn't have to.**

CII Assistant is a fully agentic RAG system that ingests the entire CII doc site and delivers instant, citation-backed answers. No prompt engineering required — just ask a question in plain English.

Available in two interfaces:
- **Web chat UI** — open a browser, start asking
- **Webex bot (CIIcompass)** — get answers directly in your team space, no context switch

What makes it agentic (not just search):
- **Multi-step reasoning** — the AI agent decides what to search, reads the results, and fetches additional pages if the first answer is incomplete
- **Grounded citations** — every claim links back to the exact doc page, so you can verify in one click
- **Self-updating index** — daily incremental re-crawl keeps answers current as docs evolve

Tech under the hood:
- Sitemap-driven crawler + heading-aware chunker → Voyage embeddings → ChromaDB
- Hybrid retrieval: vector search + BM25 reranking (60/40 blend)
- Claude tool-use loop with adaptive thinking, streaming answers over SSE

## Setup & Run

If you have [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed, you can run the entire project without touching the terminal yourself. Claude Code has built-in **skills** (slash commands) that handle all the setup and orchestration for you.

### Prerequisites

1. **Claude Code** installed and working (`claude` command available in your terminal).
2. A `.env` file in the `backend/` folder with your API keys filled in (copy `backend/.env.example` and add your keys — ask a teammate if you're unsure which keys to use).
3. **Python 3.11+** and **Node.js 18+** installed on your machine.

### How to use it

1. Open your terminal and `cd` into this project folder.
2. Run `claude` to start a Claude Code session.
3. Type the following commands **in the Claude Code prompt** (not your regular terminal):

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `/run-cii-dev` | Starts the backend, frontend, and Cloudflare tunnel all at once. Wait until Claude reports all three are healthy. |
| 2 | `/reindex` | Crawls docs.oort.io and loads the content into the search index. Run this the first time, or whenever docs are updated. |
| 3 | `/restart-webex-webhook` | Restarts the Cloudflare tunnel and re-registers the Webex bot webhook. Use this if the bot stops responding in Webex. To chat with the bot, search for **CIIcompass** in Webex. |

### Typical first-time flow

```
/run-cii-dev          ← boots the whole stack
/reindex              ← populates the doc index (takes a few minutes)
```

After that, open **http://localhost:5173** in your browser to chat with the assistant.

### Tips

- **First-time users**: always run `/reindex` after `/run-cii-dev` to populate the doc index — the assistant can't answer questions without it.
- `/reindex` needs the backend to be running first — always run `/run-cii-dev` before `/reindex`.
- If the Webex bot stops responding, run `/restart-webex-webhook` to get a fresh tunnel URL and webhook.
- To stop everything, press **Ctrl+C** in the Claude Code session.
- You don't need to understand Python, Node.js, or any of the backend code — the skills handle it all.

---

## Running with CLI commands (for developers)

If you prefer running things manually or need more control, this section covers the full setup.

### Backend

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

### Frontend

```bash
cd frontend
npm install
npm run dev              # http://localhost:5173, proxies /api → http://localhost:8000
npm run dev -- --host    # bind 0.0.0.0 so other machines on the network can reach it
```

### Webex bot (dev mode)

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

Or just run `/restart-webex-webhook` in Claude Code to handle all of this automatically.

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

## Key Outcomes

- **10+ minutes → seconds** — answers that used to require manual searching are now instant
- **100% grounded** — every response cites the exact source page, eliminating hallucination risk
- **Zero context switch** — answers arrive in Webex where teams already work, or in a dedicated web UI
- **Always current** — automated daily re-indexing means the assistant never falls behind doc updates
- **Works out of the box** — one command (`/run-cii-dev`) boots the entire stack; no ML expertise needed

## Business Value

### Short-term: internal expert buddy

Anyone who supports CII — TAC engineers, partner support, SEs, new hires ramping up — gets an instant expert on demand. Instead of asking a senior engineer or spending 15 minutes digging through docs, they get a cited answer in seconds. Zero training, zero adoption friction (it's in Webex).

- Saves 30+ min/day per support engineer on doc lookups
- Accelerates onboarding for new hires touching CII
- Reduces escalations to senior engineers for documentation questions

### Long-term: customer-facing agent with monetization

Embed this agent directly into the CII dashboard as a premium feature. Customers and admins self-diagnose and self-remediate issues without opening a TAC case.

- **Case deflection** — every issue a customer self-solves is a TAC case that never gets opened
- **Premium SKU** — "CII with AI Agent" becomes a paid differentiator competitors don't have
- **ARR impact** — drives upsell to higher tiers and improves renewal rates through better self-service
- **CSAT lift** — customers prefer instant self-service over waiting in a support queue

> The tech is identical — the only difference is who's asking the question. Internal buddy today, revenue-generating product feature tomorrow.

## Demo

[abc](abc)

## Summary

**Problem:** CII documentation spans hundreds of pages. Engineers and support teams spend 10-15 minutes per question searching manually, slowing down case resolution, onboarding, and customer support.

**Solution:** An agentic AI assistant that ingests the full CII doc site and delivers instant, citation-backed answers. Available as a web chat UI and a Webex bot (CIIcompass). Uses multi-step reasoning — not just keyword search — to find, verify, and synthesize answers across multiple doc pages.

**Tech Used:** Python/FastAPI, Claude (agentic tool-use loop with adaptive thinking), Voyage embeddings, ChromaDB, hybrid retrieval (vector search + BM25 reranking), SSE streaming, Vite/React/TypeScript frontend, Webex bot integration, Cloudflare tunnel, Claude Code skills for one-command setup.

**Impact:** Reduces answer time from 10+ minutes to seconds. Every response is grounded with source citations — zero hallucination risk. Accessible where teams already work (Webex). Short-term: internal expert buddy for anyone supporting CII. Long-term: embed in CII dashboard as a premium customer-facing feature for case deflection and ARR growth.

**Next Steps:** Add authentication and rate limiting. Embed the agent in the CII product dashboard for customer self-service. Expand to other Cisco doc sites (XDR, Duo). Add usage analytics to measure case deflection and time saved.

## Architecture notes

- **Ingestion** (`app/ingest/`): sitemap-driven crawl → `markdownify` → heading-aware chunker (~800 tokens, 100 overlap, heading path prefixed) → Voyage `voyage-3` embeddings (batches of 128) → ChromaDB collection `cii_docs`. Incremental: per-URL content hash stored in `data/url_hashes.json`; unchanged pages are skipped on re-run.
- **Retrieval** (`app/rag/`): vector search over Chroma + BM25 rerank (60/40 blend) on the candidate pool.
- **Agent** (`app/agent/`): Claude `claude-opus-4-7` with adaptive thinking, prompt caching on system + tool definitions. Tools exposed: `search_docs`, `fetch_page`, `list_sections`. Server loops on `tool_use` stop reason until the model produces a final answer, streaming text deltas and citation events over SSE.
- **API** (`app/api/`): `POST /api/chat` (SSE), `POST /api/ingest` (background job, with progress + 30 min timeout), `GET /api/status`, `POST /api/webex/webhook` (Webex bot).
- **Scheduler** (`app/scheduler.py`): daily incremental re-index at 01:00 local. Env: `REINDEX_ENABLED`, `REINDEX_HOUR`.
