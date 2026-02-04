from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import sys
import os
from contextlib import asynccontextmanager

# Add parent directory to path to import from embodiment/core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from embodiment.soul import CharacterSoul
from core.graph import KnowledgeGraph
from core.vector import VectorVault
from embodiment.dashboard_utils import SystemMonitor

# ============================================================
# Global State (created at import time)
# ============================================================

kg = KnowledgeGraph()
vault = VectorVault()
active_personas = {}  # persona_id -> CharacterSoul instance

# ============================================================
# Startup / Shutdown (lifespan)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Persona Engine API starting...")
    print("📊 Verifying database connections...")
    try:
        kg.verify_connection()
        print("✅ Neo4j connected")
        print("✅ ChromaDB connected")
        print("🎯 API ready at http://localhost:8000")
        print("📚 Docs available at http://localhost:8000/docs")
    except Exception as e:
        print(f"❌ Startup error: {e}")

    yield

    # Shutdown (optional)
    print("👋 Shutting down...")

# ============================================================
# App
# ============================================================

app = FastAPI(title="Persona Engine API", version="2.0.0", lifespan=lifespan)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://*.vercel.app",
        "https://*.railway.app",
        "*"  # Allow all for now, tighten later
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Data Models
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
# Helper Functions
# ============================================================

def get_available_characters():
    query = "MATCH (c:Character) RETURN c.name AS name, c.description AS description ORDER BY c.name"
    with kg.driver.session() as session:
        result = session.run(query)
        return [
            {
                "name": record["name"],
                "description": record["description"] or "No description available",
            }
            for record in result
        ]

# ============================================================
# Persona Management Endpoints
# ============================================================

@app.get("/api/personas", response_model=List[PersonaInfo])
async def list_personas():
    try:
        characters = get_available_characters()

        personas = []
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
    except Exception as e:
        print(f"Error listing personas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/personas/{persona_id}", response_model=PersonaInfo)
async def get_persona(persona_id: str):
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting persona: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Chat Endpoints
# ============================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_persona(request: ChatRequest):
    import time
    start_time = time.time()

    try:
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
    except Exception as e:
        print(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
# Knowledge Graph Endpoints
# ============================================================

@app.get("/api/graph/expert/{persona_id}")
async def get_expert_graph(persona_id: str, depth: int = 2):
    try:
        query = f"""
        MATCH path = (c:Character {{name: $name}})-[*1..{depth}]-(connected)
        RETURN path
        LIMIT 100
        """

        nodes = []
        edges = []
        seen_nodes = set()
        seen_edges = set()

        with kg.driver.session() as session:
            results = session.run(query, name=persona_id)

            for record in results:
                path = record["path"]

                for node in path.nodes:
                    node_id = node.element_id
                    if node_id not in seen_nodes:
                        nodes.append(
                            {
                                "id": node_id,
                                "label": node.get("name") or node.get("title") or "Unknown",
                                "type": list(node.labels)[0].lower() if node.labels else "unknown",
                                "properties": dict(node),
                            }
                        )
                        seen_nodes.add(node_id)

                for rel in path.relationships:
                    edge_id = f"{rel.start_node.element_id}-{rel.end_node.element_id}"
                    if edge_id not in seen_edges:
                        edges.append(
                            {
                                "id": edge_id,
                                "source": rel.start_node.element_id,
                                "target": rel.end_node.element_id,
                                "label": rel.type,
                            }
                        )
                        seen_edges.add(edge_id)

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        print(f"Error getting graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/graph/domains")
async def get_domain_graph():
    try:
        query = """
        MATCH (c:Character)
        OPTIONAL MATCH (c)-[r]->(related)
        RETURN c.name as character, type(r) as relationship, related.name as related_to
        LIMIT 50
        """

        domains = []
        with kg.driver.session() as session:
            results = session.run(query)
            for record in results:
                domains.append(
                    {
                        "character": record["character"],
                        "relationship": record["relationship"],
                        "related_to": record["related_to"],
                    }
                )

        return domains
    except Exception as e:
        print(f"Error getting domains: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Analytics Endpoints
# ============================================================

@app.get("/api/analytics/system")
async def get_system_analytics():
    try:
        monitor = SystemMonitor()
        health = monitor.get_system_health()

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
    except Exception as e:
        print(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/persona/{persona_id}")
async def get_persona_analytics(persona_id: str):
    try:
        query = """
        MATCH (c:Character {name: $name})
        OPTIONAL MATCH (c)-[:RECALLS]->(m:Memory)
        OPTIONAL MATCH (c)-[:HAS_SUMMARY]->(s:Summary)
        OPTIONAL MATCH (c)-[:APPEARS_IN]->(scene:Scene)
        RETURN
            count(DISTINCT m) as memory_count,
            count(DISTINCT s) as summary_count,
            count(DISTINCT scene) as problems_solved
        """

        with kg.driver.session() as session:
            result = session.run(query, name=persona_id).single()

        return {
            "problems_solved": result["problems_solved"],
            "memory_count": result["memory_count"],
            "summary_count": result["summary_count"],
        }
    except Exception as e:
        print(f"Error getting persona analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Health Check
# ============================================================

@app.get("/health")
async def health_check():
    try:
        kg.verify_connection()
        return {"status": "healthy", "services": {"neo4j": "up", "chroma": "up"}}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
