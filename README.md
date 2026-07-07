<div align="center">

# Agent Persona Engine
### *The Infinite Library*

**Chat with characters from a novel — grounded in the actual text, with persistent hybrid memory.**

</div>

---

## What it does

Feed it a long-form novel. It builds a queryable world model and lets you converse with any character in it — where every reply is grounded in scenes the character actually lived through, not the LLM's vibes about them.

1. **Ingestion** — an Archivist agent processes the novel chapter by chapter, extracting scenes, characters, relationships, and the world's power hierarchy (e.g. cultivation ranks) into structured form.
2. **Hybrid memory** — scenes are embedded into **ChromaDB** (semantic recall); characters, relationships, and world facts go into **Neo4j** (relational recall).
3. **Character Soul** — a persona layer that answers as a specific character. Each turn performs *deep recall*: vector search over lived scenes + graph queries over relationships + rolling conversation summaries, all injected into the prompt.
4. **Drift monitoring** — a DriftMonitor agent watches for the persona sliding out of character across turns; a MemoryManager compresses conversation history into summaries so long sessions stay coherent.

## Architecture

```
novel.txt
   │
   ▼
IngestionEngine (main.py, resumable per chapter)
   ├── ArchivistAgent ──► scene/character/relationship extraction (LLM)
   ├── NovelNamespace ──► power-hierarchy grounding (data/<id>_namespace.json)
   ├── VectorVault ─────► ChromaDB  (scene embeddings, all-MiniLM-L6-v2)
   └── KnowledgeGraph ──► Neo4j     (characters, relations, world facts)

CharacterSoul (embodiment/soul.py)
   deep_recall(query) ──► scenes + facts + history + summaries ──► speak()
   ├── MemoryManager  ──► rolling summarization
   └── DriftMonitor   ──► persona-consistency checks

Interfaces
   ├── FastAPI backend (backend/main.py) — REST + WebSocket chat
   ├── React + TypeScript frontend      — persona gallery, chat, graph view
   └── Streamlit dashboard (app.py)     — memory inspector, system monitor
```

**Stack:** Python · FastAPI · Neo4j · ChromaDB · LangChain · DeepSeek / Gemini / Groq · React 19 + TypeScript + Vite · WebSockets · Streamlit · Docker Compose

## Quick start

Prerequisites: Python 3.11+, Docker, and LLM keys — ingestion uses Groq (`GROQ_API_KEY`), while chat uses DeepSeek (`DEEPSEEK_API_KEY`) or Gemini (`GOOGLE_API_KEY`), so you need `GROQ_API_KEY` plus one of the other two for the full pipeline.

```bash
git clone https://github.com/Sai-Teja-Meka/Agent-Persona-Engine.git
cd Agent-Persona-Engine
cp .env.example .env        # add your LLM API key(s)

# 1. Start the memory layer (Neo4j + ChromaDB)
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Ingest a novel (plain-text file; ingestion is resumable)
python main.py ingest --file path/to/novel.txt --id my_novel

# 4a. Chat via API + React frontend
uvicorn backend.main:app --port 8001
cd frontend && npm install && npm run dev   # http://localhost:5173

# 4b. …or via the Streamlit dashboard
streamlit run app.py
```

## Design notes

- **Grounded ≠ retrieved-once.** Every turn re-queries both stores. The character's knowledge is bounded by what's actually in the ingested text — the persona can't "know" events the source never gave it.
- **Two memories, two failure modes.** Vector store alone loses relationships ("who betrayed whom"); graph alone loses texture ("what the rain felt like in that scene"). The hybrid recall exists because each covers the other's blind spot.
- **Resumable ingestion.** Long novels take many LLM calls; the engine checkpoints per chapter and resumes from the last processed state.
- **Provenance-first.** Chat responses expose the memories and facts they used (`context_used` in the API response), so you can audit *why* the character said what it said.

## Status & roadmap

Working today: end-to-end ingestion → hybrid storage → character chat with recall context, via API, React UI, and Streamlit. Measured chat latency is returned per-response (`latency_ms`).

Honest gaps: no automated eval harness yet (persona-fidelity scoring is the next milestone), single-novel-at-a-time workflow, and drift correction is monitor-and-flag rather than auto-repair.

Cold-start verification with live keys: see docs/VERIFICATION.md.

## License

MIT
