# Verification Report

**Date:** July 2026
**Scope:** Full README quickstart, cold-start, on Windows (cp1252 console), with live LLM keys.
**Method:** Fresh virtualenv, fresh containers, empty databases. Every step below was executed as a new user would run it, in order. Test corpus: chapters 1–3 of *Alice's Adventures in Wonderland* (public domain, abridged).

## Results

| Step | Result | Notes |
|---|---|---|
| `cp .env.example .env` | ✅ | |
| `docker-compose up -d` (Neo4j + Chroma) | ✅ | Both health checks green |
| Fresh venv + `pip install -r requirements.txt` | ✅ | |
| `python main.py ingest --file test_novel.txt --id test_novel` | ✅ | 3 chapters processed; no-namespace path degrades gracefully (power scaling disabled, as documented) |
| `uvicorn backend.main:app --port 8001` | ✅ | Starts on a default cp1252 Windows console (no `PYTHONUTF8` required); unencodable glyphs degrade to `?` |
| `GET /health` | ✅ | `neo4j_ready: true`, `chroma_ready: true` |
| `GET /api/personas` | ✅ | Extracted from the text: Alice, Alice's sister, Dodo, Duck, Eagle, Mouse, White Rabbit |
| `POST /api/chat` | ✅ | 9.6s end-to-end latency; grounded response (below) |
| Frontend (`npm install` + `npm run dev`) | ✅ | Loads at :5173, persona gallery renders from live API; `tsc -b` clean |

## Grounding spot-check

Question to the Alice persona (answerable only from chapter 3):

> *"Why did all the birds and creatures suddenly leave you alone by the pool? What did you say wrong?"*

The persona correctly answered that mentioning her cat Dinah frightened the party away and that the Mouse took offence, both facts present in the ingested text. The API's `context_used` field showed the correct retrieved scene, so the answer is auditable, not coincidental.

## Observed limitation (kept deliberately)

The response also included one embellishment not present in the source: the Dodo "muttering about creatures of different feathers." Retrieval correctly bounds what the persona *knows*; generation still decorates around the retrieved facts. This is the precise gap the roadmap's persona-fidelity eval harness is intended to measure.

Additionally, in this exchange the graph store contributed no facts (`facts: []`), scene memories carried the full recall. With a 3-chapter corpus this is expected: relational recall earns its keep on relationship-dense questions against fully-ingested novels, not short excerpts.

## Reproducing

Follow the README quickstart exactly. Any plain-text novel works; ingestion is resumable per chapter. The grounding spot-check pattern: ask a question answerable only from a specific chapter, then inspect `context_used` in the chat response to audit which memories produced the answer.
