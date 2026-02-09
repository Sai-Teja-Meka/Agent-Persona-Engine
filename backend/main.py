# backend/main.py

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config.settings import settings

# Add parent directory to path to import from embodiment/core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from embodiment.soul import CharacterSoul
from embodiment.dashboard_utils import SystemMonitor
from core.graph import KnowledgeGraph, Neo4jNotReadyError
from core.vector import VectorVault

# ============================================================
# Global state (personas only)
# ============================================================
active_personas: Dict[str, CharacterSoul] = {}  # persona_id -> CharacterSoul instance


# ============================================================
# Service checks
# ============================================================
def check_neo4j(kg: KnowledgeGraph) -> Dict:
    # Do not force a hard verify here; just report readiness + last error.
    return kg.health()


def check_chroma(vault: VectorVault) -> Dict:
    """
    Best-effort Chroma check.
    Prefer explicit vault.health()/vault.ping() if implemented.
    """
    # 1) VectorVault has explicit health/ping method
    for method_name in ("health", "ping"):
        if hasattr(vault, method_name) and callable(getattr(vault, method_name)):
            try:
                result = getattr(vault, method_name)()
                # If it's a health dict, pass it through; otherwise coerce.
                if isinstance(result, dict):
                    return result
                return {"chroma_ready": True, "chroma_last_error": None, "method": method_name}
            except Exception as e:
                return {"chroma_ready": False, "chroma_last_error": str(e), "method": method_name}

    # 2) Try common underlying client attribute names
    for attr in ("client", "_client", "chroma", "_chroma"):
        if hasattr(vault, attr):
            client = getattr(vault, attr)
            try:
                if hasattr(client, "heartbeat") and callable(getattr(client, "heartbeat")):
                    client.heartbeat()
                    return {"chroma_ready": True, "chroma_last_error": None, "method": f"{attr}.heartbeat"}
                if hasattr(client, "list_collections") and callable(getattr(client, "list_collections")):
                    client.list_collections()
                    return {
                        "chroma_ready": True,
                        "chroma_last_error": None,
                        "method": f"{attr}.list_collections",
                    }
            except Exception as e:
                return {"chroma_ready": False, "chroma_last_error": str(e), "method": attr}

    return {
        "chroma_ready": None,
        "chroma_last_error": "No known health method on VectorVault; implement vault.ping() or expose client.",
        "method": None,
    }


# ============================================================
# Lifespan
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("CHROMA_HOST", settings.CHROMA_HOST)
    print("CHROMA_PORT", settings.CHROMA_PORT)
    print("🚀 Persona Engine API starting...")

    # Create services and store on app.state (not globals)
    # IMPORTANT: never let these raise and kill lifespan unless you want strict mode.
    try:
        app.state.kg = KnowledgeGraph()  # should start degraded if Neo4j down
    except Exception as e:
        # Absolute last-resort: keep app alive even if KnowledgeGraph init changed.
        print(f"⚠️ KnowledgeGraph init failed (continuing without Neo4j): {e}")
        app.state.kg = None

    try:
        app.state.vault = VectorVault()  # should start degraded if Chroma down (depending on strict)
    except Exception as e:
        print(f"⚠️ VectorVault init failed (continuing without Chroma): {e}")
        app.state.vault = None

    # Report status (do NOT print “connected” unless verified)
    if app.state.kg is not None:
        neo4j_status = check_neo4j(app.state.kg)
        if neo4j_status.get("neo4j_ready"):
            print("✅ Neo4j ready")
        else:
            print(f"⚠️ Neo4j NOT ready (degraded mode): {neo4j_status.get('neo4j_last_error')}")
    else:
        print("⚠️ Neo4j disabled (KnowledgeGraph not initialized).")

    if app.state.vault is not None:
        chroma_status = check_chroma(app.state.vault)
        if chroma_status.get("chroma_ready") is True:
            print("✅ ChromaDB ready")
        else:
            print(f"⚠️ ChromaDB status uncertain/down: {chroma_status.get('chroma_last_error')}")
    else:
        print("⚠️ Chroma disabled (VectorVault not initialized).")

    print("🎯 API running (some endpoints may return 503 until dependencies recover).")

    yield

    # Shutdown
    try:
        kg = getattr(app.state, "kg", None)
        if kg is not None:
            kg.close()
    finally:
        print("👋 Shutting down...")


# ============================================================
# App
# ============================================================
app = FastAPI(title="Persona Engine API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://*.vercel.app",
        "https://*.railway.app",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Exception handling: return 503 for Neo4j not ready
# ============================================================
@app.exception_handler(Neo4jNotReadyError)
async def neo4j_not_ready_handler(request, exc: Neo4jNotReadyError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# ============================================================
# Data models
# ============================================================
class ChatRequest(BaseModel):
    persona_id: str
    message: str
    include_context: bool = True


class ChatResponse(BaseModel):
    response: str
    context_used: Dict
    latency_ms: int


class PersonaInfo(BaseModel):
    persona_id: str
    name: str
    domain: str
    expertise_areas: List[str]
    credibility_score: float
    description: str


# ============================================================
# App-state getters + guards
# ============================================================
def get_kg() -> KnowledgeGraph:
    kg = getattr(app.state, "kg", None)
    if kg is None:
        raise Neo4jNotReadyError("Neo4j unavailable: KnowledgeGraph not initialized")
    return kg


def get_vault() -> VectorVault:
    vault = getattr(app.state, "vault", None)
    if vault is None:
        raise HTTPException(status_code=503, detail="Chroma unavailable: VectorVault not initialized")
    return vault


def require_neo4j() -> KnowledgeGraph:
    kg = get_kg()
    kg.ensure_ready()
    return kg


# ============================================================
# Helper functions (Neo4j-safe)
# ============================================================
def get_available_characters() -> List[Dict]:
    kg = require_neo4j()

    # Prefer kg._fetch() to ensure errors mark readiness, but keeping your direct session style is OK
    query = "MATCH (c:Character) RETURN c.name AS name, c.description AS description ORDER BY c.name"
    with kg.driver.session() as session:
        result = session.run(query)
        return [
            {"name": record["name"], "description": record["description"] or "No description available"}
            for record in result
        ]


# ============================================================
# Persona endpoints
# ============================================================
@app.get("/api/personas", response_model=List[PersonaInfo])
async def list_personas():
    characters = get_available_characters()

    personas: List[PersonaInfo] = []
    for char in characters:
        personas.append(
            PersonaInfo(
                persona_id=char["name"],
                name=char["name"],
                domain="General",
                expertise_areas=["Problem Solving", "Analysis"],
                credibility_score=0.85,
                description=char["description"],
            )
        )
    return personas


@app.get("/api/personas/{persona_id}", response_model=PersonaInfo)
async def get_persona(persona_id: str):
    kg = require_neo4j()

    query = """
    MATCH (c:Character {name: $name})
    RETURN c.name as name, c.description as description
    """
    with kg.driver.session() as session:
        result = session.run(query, name=persona_id).single()

    if not result:
        raise HTTPException(status_code=404, detail="Persona not found")

    return PersonaInfo(
        persona_id=result["name"],
        name=result["name"],
        domain="General",
        expertise_areas=["Problem Solving", "Analysis"],
        credibility_score=0.85,
        description=result["description"] or "No description available",
    )


# ============================================================
# Chat endpoints
# ============================================================
@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_persona(request: ChatRequest):
    import time

    start_time = time.time()

    if request.persona_id not in active_personas:
        active_personas[request.persona_id] = CharacterSoul(request.persona_id)

    persona = active_personas[request.persona_id]

    if request.include_context:
        memories, facts, history, summaries = persona.deep_recall(request.message)
        response = persona.speak(
            request.message,
            memories=memories,
            facts=facts,
            chat_history=history,
            summaries=summaries,
        )
        context = {
            "memories": memories[:3],
            "facts": facts[:3],
            "summaries": [s["content"][:100] for s in summaries[:2]],
        }
    else:
        response = persona.speak(request.message)
        context = {}

    latency = int((time.time() - start_time) * 1000)
    return ChatResponse(response=response, context_used=context, latency_ms=latency)


@app.websocket("/ws/chat/{persona_id}")
async def websocket_chat(websocket: WebSocket, persona_id: str):
    await websocket.accept()

    try:
        if persona_id not in active_personas:
            active_personas[persona_id] = CharacterSoul(persona_id)

        persona = active_personas[persona_id]

        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")

            await websocket.send_json({"type": "typing", "status": "started"})

            memories, facts, history, summaries = persona.deep_recall(message)
            response = persona.speak(
                message,
                memories=memories,
                facts=facts,
                chat_history=history,
                summaries=summaries,
            )

            await websocket.send_json(
                {
                    "type": "message",
                    "content": response,
                    "context": {
                        "memories_count": len(memories),
                        "facts_count": len(facts),
                        "summaries_count": len(summaries),
                    },
                }
            )

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for {persona_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()


# ============================================================
# Analytics endpoints (Neo4j-safe)
# ============================================================
@app.get("/api/analytics/system")
async def get_system_analytics():
    monitor = SystemMonitor()
    health = monitor.get_system_health()

    kg = require_neo4j()

    with kg.driver.session() as session:
        character_count = session.run("MATCH (c:Character) RETURN count(c) as count").single()["count"]
        chapter_count = session.run("MATCH (ch:Chapter) RETURN count(ch) as count").single()["count"]
        memory_count = session.run("MATCH (m:Memory) RETURN count(m) as count").single()["count"]

    return {
        **health,
        "expert_count": character_count,
        "domain_count": 1,
        "problem_count": chapter_count,
        "memory_raw": memory_count,
    }


# ============================================================
# Health endpoints
# ============================================================
@app.get("/health")
async def health():
    kg = getattr(app.state, "kg", None)
    vault = getattr(app.state, "vault", None)

    return {
        "status": "ok",
        "services": {
            "neo4j": check_neo4j(kg) if kg is not None else {"neo4j_ready": False, "neo4j_last_error": "kg is None"},
            "chroma": check_chroma(vault) if vault is not None else {"chroma_ready": False, "chroma_last_error": "vault is None"},
        },
    }


@app.get("/health/neo4j")
async def health_neo4j():
    kg = getattr(app.state, "kg", None)
    return check_neo4j(kg) if kg is not None else {"neo4j_ready": False, "neo4j_last_error": "kg is None"}


@app.get("/health/chroma")
async def health_chroma():
    vault = getattr(app.state, "vault", None)
    return check_chroma(vault) if vault is not None else {"chroma_ready": False, "chroma_last_error": "vault is None"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
