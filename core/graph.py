from neo4j import GraphDatabase
import logging
from config.settings import settings
from core.models import Chapter, CharacterState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeGraph:
    def __init__(self):
        uri = settings.NEO4J_URI
        
        # Detect if using Neo4j Aura (cloud)
        if uri.startswith('neo4j+s://') or uri.startswith('neo4j+ssc://'):
            # Neo4j Aura requires SSL configuration
            self.driver = GraphDatabase.driver(
                uri,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=3600,
                encrypted=True,
                trust='TRUST_SYSTEM_CA_SIGNED_CERTIFICATES'
            )
        else:
            # Local/Railway Neo4j (bolt://)
            self.driver = GraphDatabase.driver(
                uri,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=3600,
            )

        self.verify_connection()
        self.create_schema()

    def close(self):
        self.driver.close()

    def verify_connection(self):
        self.driver.verify_connectivity()

    def create_schema(self):
        """
        Idempotent schema creation.
        """
        queries = [
        "CREATE CONSTRAINT novel_id_unique IF NOT EXISTS FOR (n:Novel) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT chapter_id_unique IF NOT EXISTS FOR (c:Chapter) REQUIRE (c.novel_id, c.chapter_number) IS UNIQUE",
        "CREATE INDEX chapter_num_index IF NOT EXISTS FOR (c:Chapter) ON (c.chapter_number)",
        "CREATE INDEX scene_id_index IF NOT EXISTS FOR (s:Scene) ON (s.order_index)",
        "CREATE INDEX char_name_index IF NOT EXISTS FOR (c:Character) ON (c.name)",
        "CREATE INDEX char_state_index IF NOT EXISTS FOR (cs:CharacterState) ON (cs.novel_id, cs.character_name, cs.chapter_number)",
        "CREATE INDEX memory_timestamp IF NOT EXISTS FOR (m:Memory) ON (m.timestamp)",
        "CREATE INDEX summary_timestamp IF NOT EXISTS FOR (s:Summary) ON (s.timestamp)",
    ]
        with self.driver.session() as session:
            for q in queries:
                session.run(q)
        logger.info("[OK] Graph schema updated with Memory + Summary indices.")

    # ------------------------------------------------------------------
    # INGESTION: CHAPTERS / SCENES / CHARACTERS
    # ------------------------------------------------------------------
    def add_chapter(self, chapter: Chapter):
        query = """
        MERGE (n:Novel {id: $novel_id})
        MERGE (c:Chapter {novel_id: $novel_id, chapter_number: $chapter_num})
        SET c.title = $title,
            c.summary = $summary,
            c.raw_text = $raw_text,
            c.word_count = $word_count,
            c.state_vector = $state_vector,
            c.ingested_at = timestamp()
        MERGE (n)-[:CONTAINS]->(c)
        WITH c
        MATCH (prev:Chapter {novel_id: $novel_id, chapter_number: $chapter_num - 1})
        MERGE (prev)-[:NEXT]->(c)
        """
        with self.driver.session() as session:
            session.run(query, parameters={
                "novel_id": chapter.novel_id,
                "chapter_num": chapter.chapter_number,
                "title": chapter.title,
                "summary": chapter.summary,
                "raw_text": chapter.raw_text,
                "word_count": chapter.word_count,
                "state_vector": chapter.state_vector
            })

    def link_scene_to_chapter(self, novel_id: str, chapter_num: int, scene_order: int):
        query = """
        MERGE (s:Scene {
            novel_id: $novel_id,
            chapter_number: $chapter_num,
            order_index: $scene_order
        })
        MERGE (c:Chapter {
            novel_id: $novel_id,
            chapter_number: $chapter_num
        })
        MERGE (s)-[:PART_OF]->(c)
        """
        with self.driver.session() as session:
            session.run(query, parameters={
                "novel_id": novel_id,
                "chapter_num": chapter_num,
                "scene_order": scene_order
            })

    def link_character_to_scene(self, character_name: str, novel_id: str, chapter_num: int, scene_order: int):
        query = """
        MERGE (c:Character {name: $name, novel_id: $novel_id})
        MERGE (s:Scene {
            novel_id: $novel_id,
            chapter_number: $chapter_num,
            order_index: $scene_order
        })
        MERGE (c)-[:APPEARS_IN]->(s)
        """
        with self.driver.session() as session:
            session.run(query, parameters={
                "name": character_name,
                "novel_id": novel_id,
                "chapter_num": chapter_num,
                "scene_order": scene_order
            })

    def add_character_state(self, state: CharacterState):
        query = """
        MATCH (c:Chapter {novel_id: $novel_id, chapter_number: $chapter_num})
        
        MERGE (char:Character {name: $char_name, novel_id: $novel_id})
        ON CREATE SET char.description = "Auto-created from ingestion"
        
        MERGE (cs:CharacterState {
            novel_id: $novel_id,
            character_name: $char_name,
            chapter_number: $chapter_num
        })
        SET cs.power_rank = $power_rank,
            cs.emotion = $emotion,
            cs.personality_snapshot = $snapshot,
            cs.location = $location
            
        MERGE (char)-[:HAS_STATE]->(cs)
        MERGE (cs)-[:AT_CHAPTER]->(c)
        """
        with self.driver.session() as session:
            session.run(query, parameters={
                "novel_id": state.novel_id,
                "chapter_num": state.chapter_number,
                "char_name": state.character_name,
                "power_rank": state.current_power_rank,
                "emotion": state.current_emotional_state,
                "snapshot": state.personality_snapshot,
                "location": state.current_location
            })

    # ------------------------------------------------------------------
    # CHAT MEMORY: RAW TURNS
    # ------------------------------------------------------------------
    def log_interaction(self, character_name: str, user_text: str, ai_text: str):
        """
        Saves a chat turn into the Graph, linked to the Character.
        Uses MERGE so logging doesn't fail if Character doesn't exist yet.
        """
        query = """
        MERGE (c:Character {name: $name})
        CREATE (m:Memory {
            user_text: $user,
            ai_text: $ai,
            timestamp: timestamp()
        })
        CREATE (c)-[:RECALLS]->(m)
        """
        with self.driver.session() as session:
            session.run(query, parameters={
                "name": character_name,
                "user": user_text,
                "ai": ai_text
            })

    def get_recent_chat_history(self, character_name: str, limit: int = 10):
        """
        Fetches the last N interactions from the Graph (chronological order).
        """
        query = """
        MATCH (c:Character {name: $name})-[:RECALLS]->(m:Memory)
        RETURN m.user_text as user, m.ai_text as ai, m.timestamp as time
        ORDER BY m.timestamp DESC
        LIMIT $limit
        """
        history = []
        with self.driver.session() as session:
            result = session.run(query, parameters={"name": character_name, "limit": limit})
            for record in result:
                history.append({
                    "user": record["user"],
                    "ai": record["ai"]
                })
        return history[::-1]  # oldest -> newest

    # ------------------------------------------------------------------
    # MEMORY MANAGEMENT: COUNT / FETCH / COMPRESS
    # ------------------------------------------------------------------
    def get_memory_count(self, character_name: str) -> int:
        """
        Counts raw Memory nodes for a character.
        """
        query = """
        MATCH (c:Character {name: $name})-[:RECALLS]->(m:Memory)
        RETURN count(m) as count
        """
        with self.driver.session() as session:
            return session.run(query, parameters={"name": character_name}).single()["count"]

    def get_oldest_memories(self, character_name: str, limit: int = 10):
        """
        Fetches the N oldest memories for compression.
        Returns elementId(m) so we can delete precisely.
        """
        query = """
        MATCH (c:Character {name: $name})-[:RECALLS]->(m:Memory)
        RETURN elementId(m) as id, m.user_text as user, m.ai_text as ai, m.timestamp as time
        ORDER BY m.timestamp ASC
        LIMIT $limit
        """
        data = []
        with self.driver.session() as session:
            result = session.run(query, parameters={"name": character_name, "limit": limit})
            for record in result:
                data.append({
                    "id": record["id"],
                    "user": record["user"],
                    "ai": record["ai"],
                    "time": record["time"]
                })
        return data

    def compress_memories(self, character_name: str, summary_text: str, memory_ids: list):
        """
        ATOMIC TRANSACTION:
        1) Collect the target memories for THIS character
        2) Create Summary node with timeline metadata
        3) Link Character -> Summary
        4) Delete ONLY those Memory nodes (decay)
        """
        query = """
        MATCH (c:Character {name: $name})-[:RECALLS]->(m:Memory)
        WHERE elementId(m) IN $ids
        WITH c, collect(m) as ms

        // If there are no matched memories, do nothing safely.
        FOREACH (_ IN CASE WHEN size(ms) = 0 THEN [] ELSE [1] END |
            CREATE (s:Summary {
                content: $summary,
                timestamp: timestamp(),
                compressed_count: size(ms),
                start_time: reduce(minT = 9223372036854775807, x IN ms | CASE WHEN x.timestamp < minT THEN x.timestamp ELSE minT END),
                end_time: reduce(maxT = 0, x IN ms | CASE WHEN x.timestamp > maxT THEN x.timestamp ELSE maxT END)
            })
            CREATE (c)-[:HAS_SUMMARY]->(s)
        )

        // Delete the matched memories
        FOREACH (m IN ms | DETACH DELETE m)
        """
        with self.driver.session() as session:
            session.run(query, parameters={
                "name": character_name,
                "summary": summary_text,
                "ids": memory_ids
            })
        logger.info(f"🧹 Compressed {len(memory_ids)} memories into 1 summary for {character_name}.")

    # ------------------------------------------------------------------
    # SUMMARY RECALL: LONG-TERM MEMORY
    # ------------------------------------------------------------------
    def get_recent_summaries(self, character_name: str, limit: int = 3):
        """
        Fetches the last N summaries (newest first).
        Your Soul can inject these as long-term memory.
        """
        query = """
        MATCH (c:Character {name: $name})-[:HAS_SUMMARY]->(s:Summary)
        RETURN s.content as content, s.timestamp as time, s.compressed_count as compressed_count
        ORDER BY s.timestamp DESC
        LIMIT $limit
        """
        summaries = []
        with self.driver.session() as session:
            result = session.run(query, parameters={"name": character_name, "limit": limit})
            for record in result:
                summaries.append({
                    "content": record["content"],
                    "compressed_count": record["compressed_count"],
                    "time": record["time"]
                })
        return summaries
