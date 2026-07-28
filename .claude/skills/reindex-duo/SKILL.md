---
name: reindex-duo
description: Trigger a Duo docs re-index (duo.com/docs, help.duo.com) against the running backend, poll progress, and surface failures. Use when the Duo index is empty or stale.
---

# Trigger and monitor a Duo ingest run

## When to use

- `GET /api/status?product=duo` shows `pages: 0` (empty index).
- The agent is answering "the docs don't cover this" for clearly-documented Duo topics.
- After a code change to the crawler, chunker, or embedder.
- After a Duo docs content change you want indexed *now* (otherwise wait for the daily 01:00 scheduler).

## Preflight

```bash
# Backend reachable?
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/health
# Is there already a job running?
curl -s "http://localhost:8001/api/status?product=duo" | python3 -c "
import sys, json
print(json.load(sys.stdin)['job']['status'])
"
```

If `status` is `running`, don't kick another one — poll the existing job
instead (`/api/ingest` will return `already_running`).

## Kick it off

Incremental (only re-embeds changed pages — fast, the default):

```bash
curl -s -X POST http://localhost:8001/api/ingest \
  -H 'content-type: application/json' \
  -d '{"force":false,"product":"duo"}' | python3 -m json.tool
```

Full re-embed (use after a chunker/embedder change):

```bash
curl -s -X POST http://localhost:8001/api/ingest \
  -H 'content-type: application/json' \
  -d '{"force":true,"product":"duo"}' | python3 -m json.tool
```

## Watch progress

```bash
while true; do
  curl -s "http://localhost:8001/api/status?product=duo" | python3 -c "
import sys, json
d = json.load(sys.stdin)['job']
p = d.get('progress', {})
print(f\"{d['status']:8} phase={p.get('phase','?'):11} \"
      f\"discovered={p.get('urls_discovered',0):4} \"
      f\"seen={p.get('pages_seen',0):4} \"
      f\"failed={p.get('pages_failed',0):4} \"
      f\"last_err={p.get('last_error','')[:60]}\")
"
  sleep 15
done
```

Expected phase transitions: `discovering → fetching → indexing → done`.

Note: Duo sites do not have a sitemap, so discovery uses link-crawling which
is slower than CII (sitemap-based). Expect 5-10 minutes for full discovery.

## Troubleshooting

- **`pages_failed` climbing with empty `last_error`** — the running code is
  old (uvicorn `--reload` doesn't preempt the in-flight asyncio task).
  Hard-restart uvicorn before retrying.
- **Job stuck `running` for >30 min** — `INGEST_TIMEOUT_SEC` (default 1800)
  should flip it to `error`. If it doesn't, kill and restart uvicorn.
- **All fetches fail immediately with `RemoteProtocolError` / `ConnectError`** —
  check network connectivity. Test directly: `curl -I https://duo.com/docs`.
- **Job finishes with 0 pages but no errors** — `discover_urls` returned
  nothing via link-crawl. The Duo doc site may have changed structure. Check
  that `https://duo.com/docs` returns HTML with navigable links.

## After a successful run

`GET /api/status?product=duo` should show `collection_size` and `pages` jumping. The
QA cache is auto-cleared on success so stale answers don't linger.
