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
npm run dev              # http://localhost:5173, proxies /api → http://localhost:8000
npm run dev -- --host    # bind 0.0.0.0 so other machines on the network can reach it
```

## Architecture notes

- **Ingestion** (`app/ingest/`): sitemap-driven crawl → `markdownify` → heading-aware chunker (~800 tokens, 100 overlap, heading path prefixed) → Voyage `voyage-3` embeddings (batches of 128) → ChromaDB collection `cii_docs`. Incremental: per-URL content hash stored in `data/url_hashes.json`; unchanged pages are skipped on re-run.
- **Retrieval** (`app/rag/`): vector search over Chroma + BM25 rerank (60/40 blend) on the candidate pool.
- **Agent** (`app/agent/`): Claude `claude-opus-4-7` with adaptive thinking, prompt caching on system + tool definitions. Tools exposed: `search_docs`, `fetch_page`, `list_sections`. Server loops on `tool_use` stop reason until the model produces a final answer, streaming text deltas and citation events over SSE.
- **API** (`app/api/`): `POST /api/chat` (SSE), `POST /api/ingest` (background job), `GET /api/status`.

## Deferred

- Auth on the API.
- Production deployment target.
- Retrieval eval harness.
