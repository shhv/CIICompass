---
name: run-dev
description: Launch the dev stack locally — backend (FastAPI on :8000) and frontend (Vite on :5173). Use this when the user asks to start, run, or boot the assistant for development. Does NOT handle the Webex bot tunnel — use /start-webex-webhook for that.
---

# Launch the CII Assistant dev stack

## Preconditions to check first

Run ALL of these checks before starting anything:

```bash
# Is the backend already up?
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health
# Is the frontend already up?
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/
# .env present?
test -f backend/.env && echo ".env OK" || echo "MISSING backend/.env"
# Check dependencies
command -v python3 >/dev/null && echo "python3 OK" || echo "MISSING python3"
command -v node >/dev/null && echo "node OK" || echo "MISSING node"
command -v brew >/dev/null && echo "brew OK" || echo "MISSING brew"
```

If services are already up, skip their steps. For any MISSING dependency, install it
using the steps below before proceeding.

## 0a. Install missing dependencies (first time only)

Check each dependency and install whatever is missing. Skip any that are already installed.

**Homebrew** (needed for python/node installs):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**Python 3.11+**:
```bash
brew install python@3.11
```
Verify: `python3 --version` — must be 3.11 or higher.

**Node.js 18+**:
```bash
brew install node
```
Verify: `node --version` — must be 18 or higher.

Tell the user which dependencies were missing and what you installed. If
Homebrew itself is missing, install it first since the others depend on it.

## 0b. Set up .env (first time only)

**Only if `backend/.env` does NOT exist.** Never overwrite an existing `.env` file — it may have user-specific keys (Webex token, etc.) that would be lost.

```bash
test -f backend/.env && echo ".env exists — skipping" || cp backend/.env.example backend/.env
```

The example file has all defaults pre-filled including the Anthropic API key
(`sk-ant-dummy-key` for the claudegate proxy). No user input needed.

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

## Verify

```bash
curl -s -o /dev/null -w "backend: %{http_code}\n"  http://localhost:8000/health
curl -s -o /dev/null -w "frontend: %{http_code}\n" http://localhost:5173/
curl -s http://localhost:8000/api/status | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'index: {d[\"pages\"]} pages, {d[\"collection_size\"]} chunks')
print(f'job:   {d[\"job\"][\"status\"]}')
"
```

Both should return 200. If `pages: 0`, run the `/reindex` skill.

To set up the Webex bot, run `/start-webex-webhook` separately.
