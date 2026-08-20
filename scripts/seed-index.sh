#!/usr/bin/env bash
# Seed the Chroma vector index for both CII and Duo products.
# Run this once after cloning the repo to populate backend/data/.
#
# Prerequisites:
#   - backend/.env exists with required API keys
#   - Python deps installed (pip install -r backend/requirements.txt)
#
# Usage: ./scripts/seed-index.sh

set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8001}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# --- Start backend if not already running ---
if ! curl -s -o /dev/null -w "" "$BACKEND_URL/health" 2>/dev/null; then
  echo "Starting backend..."
  cd "$ROOT_DIR/backend"
  uvicorn app.main:app --host 0.0.0.0 --port 8001 &
  BACKEND_PID=$!
  trap 'kill $BACKEND_PID 2>/dev/null' EXIT

  echo "Waiting for backend to be ready..."
  for i in $(seq 1 30); do
    if curl -s -o /dev/null "$BACKEND_URL/health" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  cd "$ROOT_DIR"
fi

poll_until_done() {
  local product="$1"
  echo "Indexing $product..."
  curl -s -X POST "$BACKEND_URL/api/ingest" \
    -H 'content-type: application/json' \
    -d "{\"force\":false,\"product\":\"$product\"}" > /dev/null

  while true; do
    status=$(curl -s "$BACKEND_URL/api/status?product=$product" | python3 -c "
import sys, json
d = json.load(sys.stdin)['job']
p = d.get('progress', {})
print(d['status'])
" 2>/dev/null || echo "error")

    case "$status" in
      done)
        echo "  $product: done"
        break
        ;;
      error)
        echo "  $product: ERROR — check backend logs" >&2
        return 1
        ;;
      *)
        sleep 15
        ;;
    esac
  done
}

echo "=== Seeding vector index ==="
poll_until_done "cii"
poll_until_done "duo"
echo "=== Done. backend/data/ is now populated. ==="
