---
name: start-webex-webhook
description: Start the Cloudflare tunnel for the Webex bot, capture the trycloudflare URL, delete all stale Webex webhooks, and register a fresh one pointing at the new tunnel. Use when the user asks to start, restart, refresh, or re-register the Webex webhook / tunnel, or when the bot stops receiving messages after a tunnel restart.
---

# Restart the Webex webhook + Cloudflare tunnel

This skill rotates the trycloudflare URL and re-registers the Webex webhook
so the bot keeps working after a tunnel/laptop restart.

## Preconditions

```bash
# Backend must be up on :8000 — webhook target is useless without it
curl -s -o /dev/null -w "backend: %{http_code}\n" http://localhost:8000/health
# .env must have token + secret
test -f backend/.env && grep -E '^(WEBEX_BOT_TOKEN|WEBEX_WEBHOOK_SECRET)=' backend/.env
```

If backend is down, run `/run-cii-dev` first.

## 1. Kill any existing cloudflared

```bash
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 1
pgrep -f "cloudflared tunnel" && echo "STILL RUNNING — kill -9 manually" || echo "cleared"
```

## 2. Start a new tunnel in the background and capture the URL

`cloudflared` prints the trycloudflare URL to stderr. Run it as a background
bash task, then poll the log file for the URL.

```bash
LOG=/tmp/cloudflared-cii.log
: > "$LOG"
# Start in background — run via Bash run_in_background=true
cloudflared tunnel --url http://localhost:8000 --protocol http2 > "$LOG" 2>&1
```

Then in a foreground call, poll until the URL appears (give it ~15s):

```bash
for i in $(seq 1 30); do
  TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared-cii.log | head -1)
  [ -n "$TUNNEL_URL" ] && break
  sleep 1
done
echo "TUNNEL_URL=$TUNNEL_URL"
[ -z "$TUNNEL_URL" ] && { echo "FAILED to capture tunnel URL — check $LOG"; tail -40 "$LOG"; }
```

**Always use `--protocol http2`** — QUIC (UDP/7844) is blocked on Cisco corp
networks and the tunnel will silently fail to connect.

Verify the tunnel actually proxies:

```bash
curl -s -o /dev/null -w "tunnel: %{http_code}\n" "$TUNNEL_URL/health"
```

Must be `200`. If not, the tunnel didn't finish connecting yet — wait a few
more seconds and retry, or check `/tmp/cloudflared-cii.log`.

## 3. Load Webex credentials from .env

Do **not** `source .env` — it has comment lines that zsh chokes on.

```bash
cd backend
WEBEX_BOT_TOKEN=$(grep '^WEBEX_BOT_TOKEN=' .env | cut -d= -f2-)
WEBEX_WEBHOOK_SECRET=$(grep '^WEBEX_WEBHOOK_SECRET=' .env | cut -d= -f2-)
[ -z "$WEBEX_BOT_TOKEN" ] && { echo "WEBEX_BOT_TOKEN missing in backend/.env"; exit 1; }
cd ..
```

## 4. Delete ALL existing webhooks

Stale `trycloudflare.com` webhooks pile up fast and Webex will deliver to
dead URLs. Wipe them all and start clean.

```bash
curl -s -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
  https://webexapis.com/v1/webhooks \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for w in data.get('items', []):
    print(w['id'])
" > /tmp/webex-webhook-ids.txt

echo "Deleting $(wc -l < /tmp/webex-webhook-ids.txt) stale webhooks..."
while read -r id; do
  [ -z "$id" ] && continue
  curl -s -o /dev/null -w "deleted $id: %{http_code}\n" \
    -X DELETE -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
    "https://webexapis.com/v1/webhooks/$id"
done < /tmp/webex-webhook-ids.txt
```

## 5. Register the new webhook

```bash
curl -s -X POST https://webexapis.com/v1/webhooks \
  -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"CIICompass\",
    \"targetUrl\": \"$TUNNEL_URL/api/webex/webhook\",
    \"resource\": \"messages\",
    \"event\": \"created\",
    \"secret\": \"$WEBEX_WEBHOOK_SECRET\"
  }" | python3 -m json.tool
```

Look for `"status": "active"` in the response.

## 6. Verify end-to-end

```bash
# Confirm exactly one webhook is registered, pointing at the new tunnel
curl -s -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
  https://webexapis.com/v1/webhooks \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for w in d.get('items', []):
    print(f\"{w['status']:8s} {w['targetUrl']}\")
"
```

Expected: one line, `active`, URL matches `$TUNNEL_URL`.

Then DM `CIICompass@webex.bot` "ping" in Webex — you should see the ack
message followed by an answer. If nothing arrives, tail
`/tmp/cloudflared-cii.log` and the uvicorn logs.

## Cleanup notes

- The cloudflared process keeps running in the background. To stop it later:
  `pkill -f "cloudflared tunnel"`.
- The tunnel URL is **only valid while cloudflared is running**. Closing the
  laptop / sleeping the process invalidates it and this skill must be run
  again.
- For a stable URL across restarts, set up a [named Cloudflare tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-local-tunnel/)
  instead of trycloudflare — then this skill is no longer needed.
