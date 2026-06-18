# CII Assistant

An AI agent that turns hours of doc searching into seconds with grounded answers, citations, and delivery right in Webex or the browser.

[![▶ See it in action](https://img.shields.io/badge/▶_See_it_in_action-Vidcast-00bceb?style=for-the-badge)](https://app.vidcast.io/share/2923351e-e82f-44ea-8726-05ebfeef5a63)

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

Download the ZIP from this repo, unzip, and use [Claude Code](SETUP.md#prerequisites) to run the skills:

```
/run-cii-dev          ← boots backend + frontend (required)
/reindex              ← populates the doc index (required, first time only)
/start-webex-webhook  ← enables the Webex bot (optional)
```

Then open **http://localhost:5173** to start chatting.

> First-time setup (Claude Code install, prerequisites, manual CLI commands): **[SETUP.md](SETUP.md)**

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

## Summary

**Problem:** CII documentation spans hundreds of pages. Engineers and support teams spend 10-15 minutes per question searching manually, slowing down case resolution, onboarding, and customer support.

**Solution:** An agentic AI assistant that ingests the full CII doc site and delivers instant, citation-backed answers. Available as a web chat UI and a Webex bot (CIIcompass). Uses multi-step reasoning — not just keyword search — to find, verify, and synthesize answers across multiple doc pages.

**Tech Used:** Python/FastAPI, Claude (agentic tool-use loop with adaptive thinking), Voyage embeddings, ChromaDB, hybrid retrieval (vector search + BM25 reranking), SSE streaming, Vite/React/TypeScript frontend, Webex bot integration, Cloudflare tunnel, Claude Code skills for one-command setup.

**Impact:** Reduces answer time from 10+ minutes to seconds. Every response is grounded with source citations — zero hallucination risk. Accessible where teams already work (Webex). Short-term: internal expert buddy for anyone supporting CII. Long-term: embed in CII dashboard as a premium customer-facing feature for case deflection and ARR growth.

**Next Steps:** Phase 1 (now) — CSE/CSS teams use it locally with their own API keys for day-to-day work. Phase 2 — host a shared instance with rate limiting, auth, and usage analytics. Phase 3 — embed the agent in the CII product dashboard as a premium customer-facing feature for case deflection and ARR growth. Expand to other Cisco doc sites (XDR, Duo).
