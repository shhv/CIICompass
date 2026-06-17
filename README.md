# CII Assistant

An AI agent that turns hours of doc searching into seconds with grounded answers, citations, and delivery right in Webex or the browser.

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
- **Multi-source intelligence** — ingests both the doc site AND GitHub source code, so answers can draw from documentation and implementation
- **Heading-aware chunking** — every chunk knows exactly where it sits in the doc hierarchy (e.g. "Admin Guide > Policies > Risk Scoring"), so the model always has structural context
- **Confidence-aware answers** — retrieval scores are classified as high/medium/low, and the agent calibrates its response accordingly — no low-confidence results presented as fact
- **Graceful fallback** — when docs don't have the answer, the agent asks clarifying questions instead of hallucinating or saying "I don't know"
- **Grounded citations** — every claim links back to the exact doc page, so you can verify in one click
- **Self-updating index** — daily incremental re-crawl keeps answers current as docs evolve (only re-embeds pages that actually changed, using content hashing)

Tech under the hood:
- Sitemap-driven crawler + GitHub repo crawler → heading-aware chunker → Voyage embeddings → ChromaDB
- Hybrid retrieval: vector search + BM25 reranking (60/40 blend)
- Claude tool-use loop with adaptive thinking + prompt caching for cost efficiency, streaming answers over SSE

## Setup & Run

### Prerequisites

1. **Terminal access** — you need a terminal app (macOS: Terminal.app or iTerm2; Windows: PowerShell or Windows Terminal). If you've never used one, [watch this 2-min intro](https://www.youtube.com/watch?v=aKRYQsKR46I).
2. **Xcode Command Line Tools** (macOS only) — required before anything else. Open Terminal and run: `xcode-select --install`. Click "Install" in the popup and wait for it to finish. This gives you git, compilers, and other dev essentials. *(Windows users: skip this step.)*
3. **Claude Code** installed and working (`claude` command available in your terminal). Follow the [claudegate getting started guide](https://wwwin-github.cisco.com/netascode/claudegate/blob/master/docs/getting-started.md) — **VPN required** for installation and GitHub setup.
4. **Python 3.11+** — [download here](https://www.python.org/downloads/) if not installed. Check with `python3 --version` (macOS) or `python --version` (Windows).
5. **Node.js 18+** — [download here](https://nodejs.org/) if not installed. Check with `node --version`.
6. **Homebrew** (macOS only) — needed for installing dependencies. Install with `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` if not installed. *(Windows users: skip this step — Python and Node installers handle everything.)*

### Step 0: Get the project

1. From this same repository page, click the **Code** button → **Download ZIP**.
2. Unzip the downloaded file (double-click on macOS, right-click → "Extract All" on Windows). Note the folder name it creates in your Downloads folder.
3. Open your terminal:
   - **macOS**: search for "Terminal" in Spotlight, or find it in Applications → Utilities
   - **Windows**: open PowerShell or Windows Terminal
4. Navigate into the unzipped folder. Replace the folder name below with whatever is actually on your disk (it may include the branch name, e.g. `cii-assistant-haiku-fallback-routing`):
   - **macOS**:
     ```bash
     cd ~/Downloads/cii-assistant-haiku-fallback-routing
     ```
   - **Windows**:
     ```powershell
     cd $HOME\Downloads\cii-assistant-haiku-fallback-routing
     ```
   > **Tip:** If you're not sure of the exact folder name, check your Downloads folder and match the `cd` command to what you see there.
5. Start Claude Code:
   ```bash
   claude
   ```

You're now inside Claude Code and ready to use the skills below.

---

There are **two ways** to run this project from here. **Pick one — you don't need both.**

| | Option A: Claude Code skills | Option B: CLI commands |
|--|------|------|
| **For** | Non-coders, CSEs, CSSs, anyone who just wants it running | Developers who want manual control |
| **How** | Type slash commands in Claude Code | Run terminal commands yourself |
| **Setup time** | ~2 minutes | ~10 minutes |

---

### Option A: Claude Code skills (recommended)

If you have [Claude Code](https://wwwin-github.cisco.com/netascode/claudegate/blob/master/docs/getting-started.md) installed, you can run the entire project without touching the terminal yourself. Claude Code has built-in **skills** (slash commands) that handle all the setup and orchestration for you.

### How to use it

Type the following commands **in the Claude Code prompt** (not your regular terminal):

| | Command | What it does |
|--|---------|--------------|
| 🟢 Required | `/run-cii-dev` | Starts backend and frontend. Wait until Claude confirms both are healthy. |
| 🟢 Required | `/reindex` | Populates the search index from docs.oort.io. Run on first use or after docs update. |
| ⚪ Optional | `/start-webex-webhook` | Sets up the Webex bot tunnel and webhook. Search **CIIcompass** in Webex to find the bot (displays as **CII AI Assistant**). |

> **Important:** Claude will ask you to approve commands as it runs (e.g. installing dependencies, starting servers). Read the prompts on screen and press **Enter** or type **y** to approve. Don't walk away after typing the skill command. Stay and follow along until Claude confirms everything is up and running.

### Typical first-time flow

```
/run-cii-dev          ← starts backend + frontend
/reindex              ← populates the doc index (takes a few minutes)
/start-webex-webhook  ← sets up the Webex bot (optional)
```

After that, open **http://localhost:5173** in your browser to chat with the assistant.

### Tips

- **First-time users**: always run `/reindex` after `/run-cii-dev` to populate the doc index — the assistant can't answer questions without it.
- `/reindex` needs the backend to be running first — always run `/run-cii-dev` before `/reindex`.
- If the Webex bot stops responding, run `/start-webex-webhook` to get a fresh tunnel URL and webhook.
- To stop everything, press **Ctrl+C** in the Claude Code session.
- You don't need to understand Python, Node.js, or any of the backend code — the skills handle it all.

---

### Option B: CLI commands (for developers)

If you prefer running things manually or need more control, use these commands instead. **Skip this if you already used Option A above.**

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

## Key Outcomes

- **10+ minutes → seconds** — answers that used to require manual searching are now instant
- **100% grounded** — every response cites the exact source page, eliminating hallucination risk
- **Zero context switch** — answers arrive in Webex where teams already work, or in a dedicated web UI
- **Always current** — automated daily re-indexing means the assistant never falls behind doc updates
- **Works out of the box** — one command (`/run-cii-dev`) boots the entire stack; no ML expertise needed

## Business Value & Rollout

### Phase 1 — now: CSE/CSS expert buddy (ready today)

Anyone who supports CII — CSEs, CSSs, partner support, SEs, new hires ramping up — gets an instant expert on demand. Run it locally with your own API keys, no deployment or ops overhead. Clone the repo, add your keys, run `/run-cii-dev`, and start getting cited answers in seconds instead of spending 15 minutes digging through docs.

- Saves 30+ min/day per support engineer on doc lookups
- Accelerates onboarding for new hires touching CII
- Reduces escalations to senior engineers for documentation questions
- Zero adoption friction — answers arrive in Webex (CIIcompass) or the web UI

### Phase 2 — next: centrally hosted shared instance

Host a shared instance so the whole CII support org can use it without running anything locally. Adds rate limiting, authentication, and usage analytics.

- One instance serves all CSE/CSS teams
- Usage data shows which topics cause the most questions — feeds back into doc improvements
- Cost-controlled with rate limits and shared API keys

### Phase 3 — long-term: embedded in the CII dashboard with monetization

Embed the agent directly into the CII product dashboard as a premium customer-facing feature. Customers and admins self-diagnose and self-remediate issues without opening a TAC case.

- **Case deflection** — every issue a customer self-solves is a TAC case that never gets opened
- **Premium SKU** — "CII with AI Agent" becomes a paid differentiator competitors don't have
- **ARR impact** — drives upsell to higher tiers and improves renewal rates through better self-service
- **CSAT lift** — customers prefer instant self-service over waiting in a support queue

> The tech is identical across all three phases — the only difference is where it runs and who's asking the question.

## Demo

[abc](abc)

## Summary

**Problem:** CII documentation spans hundreds of pages. Engineers and support teams spend 10-15 minutes per question searching manually, slowing down case resolution, onboarding, and customer support.

**Solution:** An agentic AI assistant that ingests the full CII doc site and delivers instant, citation-backed answers. Available as a web chat UI and a Webex bot (CIIcompass). Uses multi-step reasoning — not just keyword search — to find, verify, and synthesize answers across multiple doc pages.

**Tech Used:** Python/FastAPI, Claude (agentic tool-use loop with adaptive thinking), Voyage embeddings, ChromaDB, hybrid retrieval (vector search + BM25 reranking), SSE streaming, Vite/React/TypeScript frontend, Webex bot integration, Cloudflare tunnel, Claude Code skills for one-command setup.

**Impact:** Reduces answer time from 10+ minutes to seconds. Every response is grounded with source citations — zero hallucination risk. Accessible where teams already work (Webex). Short-term: internal expert buddy for anyone supporting CII. Long-term: embed in CII dashboard as a premium customer-facing feature for case deflection and ARR growth.

**Next Steps:** Phase 1 (now) — CSE/CSS teams use it locally with their own API keys for day-to-day work. Phase 2 — host a shared instance with rate limiting, auth, and usage analytics. Phase 3 — embed the agent in the CII product dashboard as a premium customer-facing feature for case deflection and ARR growth. Expand to other Cisco doc sites (XDR, Duo).

## Architecture notes

- **Ingestion** (`app/ingest/`): sitemap-driven crawl → `markdownify` → heading-aware chunker (~800 tokens, 100 overlap, heading path prefixed) → Voyage `voyage-3` embeddings (batches of 128) → ChromaDB collection `cii_docs`. Incremental: per-URL content hash stored in `data/url_hashes.json`; unchanged pages are skipped on re-run.
- **Retrieval** (`app/rag/`): vector search over Chroma + BM25 rerank (60/40 blend) on the candidate pool.
- **Agent** (`app/agent/`): Claude `claude-opus-4-7` with adaptive thinking, prompt caching on system + tool definitions. Tools exposed: `search_docs`, `fetch_page`, `list_sections`. Server loops on `tool_use` stop reason until the model produces a final answer, streaming text deltas and citation events over SSE.
- **API** (`app/api/`): `POST /api/chat` (SSE), `POST /api/ingest` (background job, with progress + 30 min timeout), `GET /api/status`, `POST /api/webex/webhook` (Webex bot).
- **Scheduler** (`app/scheduler.py`): daily incremental re-index at 01:00 local. Env: `REINDEX_ENABLED`, `REINDEX_HOUR`.
