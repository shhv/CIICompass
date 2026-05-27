---
name: run-cii-dev
description: Launch the full CII Assistant dev stack locally — backend (FastAPI on :8000), frontend (Vite on :5173), and Cloudflare tunnel for the Webex bot. Use this when the user asks to start, run, or boot the CII assistant for development.
---

# Launch the CII Assistant dev stack

## Preconditions to check first

```bash
# Is the backend already up?
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health
# Is the frontend already up?
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/
# .env present?
test -f backend/.env && echo ".env OK" || echo "MISSING backend/.env"
```

If any are missing, follow the steps below for the missing layer only.

## 1. Backend

```bash
cd backend
python3 -m venv .venv 2>/dev/null   # no-op if exists
source .venv/bin/activate
pip install -e . >/dev/null         # no-op if up to date
uvicorn app.main:app --reload --port 8000
```

Run uvicorn in the background (e.g. tmux / a background bash task) so the
session can keep going. Verify with:

```bash
curl -s http://localhost:8000/health
```

**Gotcha:** `get_settings()` is `lru_cache`'d. If you edit `backend/.env`,
touch any Python file or restart uvicorn — `--reload` watches `.py`, not `.env`.

## 2. Frontend

```bash
cd frontend
npm install     # no-op if up to date
npm run dev     # http://localhost:5173, proxies /api → :8000
```

## 3. Cloudflare tunnel (Webex bot only)

Skip this if not testing the Webex bot.

```bash
cloudflared tunnel --url http://localhost:8000 --protocol http2
```

**Always pass `--protocol http2`** — default QUIC (UDP/7844) is blocked on
Cisco corp networks and you'll get "failed to dial a quic connection"
errors.

Copy the printed `https://<random>.trycloudflare.com` URL.

## 4. Re-register the Webex webhook (only if tunnel URL changed)

The trycloudflare URL is randomized every restart. Any time it changes,
delete old webhooks and register a new one:

```bash
cd backend
WEBEX_BOT_TOKEN=$(grep '^WEBEX_BOT_TOKEN=' .env | cut -d= -f2-)
WEBEX_WEBHOOK_SECRET=$(grep '^WEBEX_WEBHOOK_SECRET=' .env | cut -d= -f2-)
TUNNEL_URL="https://<new-tunnel>.trycloudflare.com"

# List existing
curl -s -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
  https://webexapis.com/v1/webhooks | python3 -m json.tool

# Delete stale ones by id
curl -X DELETE -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
  https://webexapis.com/v1/webhooks/<id>

# Register the new one
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

**Don't use `set -a; source .env`** — the `.env` has comment lines that
aren't `KEY=value` and zsh chokes. Use the `grep | cut` extraction above.

## Verify everything is wired

```bash
curl -s -o /dev/null -w "backend: %{http_code}\n"  http://localhost:8000/health
curl -s -o /dev/null -w "frontend: %{http_code}\n" http://localhost:5173/
curl -s -o /dev/null -w "tunnel:   %{http_code}\n" "$TUNNEL_URL/health"
curl -s http://localhost:8000/api/status | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'index: {d[\"pages\"]} pages, {d[\"collection_size\"]} chunks')
print(f'job:   {d[\"job\"][\"status\"]}')
"
```

All three should return 200. If `pages: 0`, see the `reindex` skill.

Then DM `CIICompass@webex.bot` in Webex with a test question.
