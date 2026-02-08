from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase
from neo4j._sync.driver import Driver  # type: ignore
from neo4j.exceptions import (
    AuthError,
    ConfigurationError,
    Neo4jError,
    ServiceUnavailable,
)

from config.settings import settings
from core.models import Chapter, CharacterState

logger = logging.getLogger(__name__)


class Neo4jNotReadyError(RuntimeError):
    """Raised when Neo4j is not reachable/ready at the moment."""


class KnowledgeGraph:
    """
    Neo4j access layer that is resilient to transient network/DNS failures.

    Key behavior changes vs your original version:
    - Does NOT crash the whole app on startup if Neo4j DNS/network blips.
    - Maintains an internal readiness flag and last_error.
    - Auto-retries bootstrap (verify + schema) with backoff.
    - Any DB method calls ensure Neo4j readiness (and can attempt a quick reconnect).
    """

    def __init__(
        self,
        *,
        bootstrap_attempts: int = 6,
        bootstrap_initial_delay_s: float = 0.5,
        bootstrap_max_delay_s: float = 15.0,
        connection_timeout_s: float = 10.0,
        max_tx_retry_time_s: float = 15.0,
    ) -> None:
        uri: str = settings.NEO4J_URI

        self._ready: bool = False
        self._last_error: Optional[BaseException] = None

        # Optional: if you have NEO4J_DATABASE in settings, it will be used.
        self._database: Optional[str] = getattr(settings, "NEO4J_DATABASE", None) or None

        self.driver: Driver = GraphDatabase.driver(
            uri,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
            connection_timeout=connection_timeout_s,
            max_transaction_retry_time=max_tx_retry_time_s,
        )

        # Try to bootstrap now, but do NOT hard-fail the process on transient errors.
        self._bootstrap(
            attempts=bootstrap_attempts,
            initial_delay_s=bootstrap_initial_delay_s,
            max_delay_s=bootstrap_max_delay_s,
            fatal=False,
        )

    # -----------------------------
    # Public helpers / lifecycle
    # -----------------------------
    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def last_error(self) -> Optional[str]:
        return str(self._last_error) if self._last_error else None

    def close(self) -> None:
        self.driver.close()

    def health(self) -> Dict[str, Any]:
        return {"neo4j_ready": self._ready, "neo4j_last_error": self.last_error}

    # -----------------------------
    # Bootstrap / readiness
    # -----------------------------
    def ensure_ready(self, *, quick_reconnect: bool = True) -> None:
        """
        Ensures Neo4j is ready. If not ready, optionally tries a short reconnect.
        Raise Neo4jNotReadyError if still unavailable.
        """
        if self._ready:
            return

        if quick_reconnect:
            self._bootstrap(attempts=3, initial_delay_s=0.25, max_delay_s=2.0, fatal=False)

        if not self._ready:
            raise Neo4jNotReadyError(f"Neo4j unavailable: {self._last_error}")

    def _bootstrap(
        self,
        *,
        attempts: int,
        initial_delay_s: float,
        max_delay_s: float,
        fatal: bool,
    ) -> None:
        """
        Try to verify connectivity and create schema.
        - fatal=True: raise if cannot become ready (useful in local dev).
        - fatal=False: mark not-ready and keep process alive.
        """
        delay = max(0.0, initial_delay_s)

        for attempt in range(1, attempts + 1):
            try:
                self.driver.verify_connectivity()
                self.create_schema()
                self._ready = True
                self._last_error = None
                logger.info("✅ Neo4j connected and schema ensured.")
                return

            except (AuthError, ConfigurationError) as e:
                # These are not transient; fail fast.
                self._ready = False
                self._last_error = e
                logger.exception("Neo4j configuration/auth error (not retrying).")
                if fatal:
                    raise
                return

            except Exception as e:
                # Transient: DNS failure, network hiccup, Aura briefly unavailable, etc.
                self._ready = False
                self._last_error = e

                if attempt >= attempts:
                    logger.error(
                        "Neo4j bootstrap failed after %s attempts; continuing in degraded mode: %s",
                        attempts,
                        e,
                    )
                    if fatal:
                        raise
                    return

                # Exponential-ish backoff + jitter
                sleep_for = min(max_delay_s, max(0.1, delay)) * (1.0 + random.random() * 0.25)
                logger.warning(
                    "Neo4j not ready (attempt %s/%s): %s; retrying in %.2fs",
                    attempt,
                    attempts,
                    e,
                    sleep_for,
                )
                time.sleep(sleep_for)
                delay = min(max_delay_s, delay * 2 if delay > 0 else 0.5)

    # -----------------------------
    # Core query runners
    # -----------------------------
    def _session_kwargs(self) -> Dict[str, Any]:
        # Neo4j Python driver accepts database kwarg in v4+.
        return {"database": self._database} if self._database else {}

    def _run(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        """
        Run a query and consume it (so network errors surface here).
        Marks driver as not-ready on network-ish failures.
        """
        self.ensure_ready()

        try:
            with self.driver.session(**self._session_kwargs()) as session:
                result = session.run(query, parameters=parameters or {})
                result.consume()
        except (ServiceUnavailable, OSError, Neo4jError, ValueError) as e:
            self._ready = False
            self._last_error = e
            raise

    def _fetch(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Run a read query and return list[dict].
        Marks driver as not-ready on network-ish failures.
        """
        self.ensure_ready()

        try:
            with self.driver.session(**self._session_kwargs()) as session:
                result = session.run(query, parameters=parameters or {})
                return [record.data() for record in result]
        except (ServiceUnavailable, OSError, Neo4jError, ValueError) as e:
            self._ready = False
            self._last_error = e
            raise

    # -----------------------------
    # Schema
    # -----------------------------
    def create_schema(self) -> None:
        """
        Idempotent schema creation.
        Called only after verify_connectivity succeeds.
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

        with self.driver.session(**self._session_kwargs()) as session:
            for q in queries:
                session.run(q).consume()

        logger.info("[OK] Graph schema updated with Memory + Summary indices.")

    # ------------------------------------------------------------------
    # INGESTION: CHAPTERS / SCENES / CHARACTERS
    # ------------------------------------------------------------------
    def add_chapter(self, chapter: Chapter) -> None:
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
        self._run(
            query,
            parameters={
                "novel_id": chapter.novel_id,
                "chapter_num": chapter.chapter_number,
                "title": chapter.title,
                "summary": chapter.summary,
                "raw_text": chapter.raw_text,
                "word_count": chapter.word_count,
                "state_vector": chapter.state_vector,
            },
        )

    def link_scene_to_chapter(self, novel_id: str, chapter_num: int, scene_order: int) -> None:
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
        self._run(
            query,
            parameters={"novel_id": novel_id, "chapter_num": chapter_num, "scene_order": scene_order},
        )

    def link_character_to_scene(
        self, character_name: str, novel_id: str, chapter_num: int, scene_order: int
    ) -> None:
        query = """
        MERGE (c:Character {name: $name, novel_id: $novel_id})
        MERGE (s:Scene {
            novel_id: $novel_id,
            chapter_number: $chapter_num,
            order_index: $scene_order
        })
        MERGE (c)-[:APPEARS_IN]->(s)
        """
        self._run(
            query,
            parameters={
                "name": character_name,
                "novel_id": novel_id,
                "chapter_num": chapter_num,
                "scene_order": scene_order,
            },
        )

    def add_character_state(self, state: CharacterState) -> None:
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
        self._run(
            query,
            parameters={
                "novel_id": state.novel_id,
                "chapter_num": state.chapter_number,
                "char_name": state.character_name,
                "power_rank": state.current_power_rank,
                "emotion": state.current_emotional_state,
                "snapshot": state.personality_snapshot,
                "location": state.current_location,
            },
        )

    # ------------------------------------------------------------------
    # CHAT MEMORY: RAW TURNS
    # ------------------------------------------------------------------
    def log_interaction(self, character_name: str, user_text: str, ai_text: str) -> None:
        query = """
        MERGE (c:Character {name: $name})
        CREATE (m:Memory {
            user_text: $user,
            ai_text: $ai,
            timestamp: timestamp()
        })
        CREATE (c)-[:RECALLS]->(m)
        """
        self._run(query, parameters={"name": character_name, "user": user_text, "ai": ai_text})

    def get_recent_chat_history(self, character_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        query = """
        MATCH (c:Character {name: $name})-[:RECALLS]->(m:Memory)
        RETURN m.user_text as user, m.ai_text as ai, m.timestamp as time
        ORDER BY m.timestamp DESC
        LIMIT $limit
        """
        rows = self._fetch(query, parameters={"name": character_name, "limit": limit})
        # rows come newest->oldest; reverse to oldest->newest
        return [{"user": r["user"], "ai": r["ai"]} for r in rows][::-1]

    # ------------------------------------------------------------------
    # MEMORY MANAGEMENT: COUNT / FETCH / COMPRESS
    # ------------------------------------------------------------------
    def get_memory_count(self, character_name: str) -> int:
        query = """
        MATCH (c:Character {name: $name})-[:RECALLS]->(m:Memory)
        RETURN count(m) as count
        """
        rows = self._fetch(query, parameters={"name": character_name})
        return int(rows[0]["count"]) if rows else 0

    def get_oldest_memories(self, character_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        query = """
        MATCH (c:Character {name: $name})-[:RECALLS]->(m:Memory)
        RETURN elementId(m) as id, m.user_text as user, m.ai_text as ai, m.timestamp as time
        ORDER BY m.timestamp ASC
        LIMIT $limit
        """
        rows = self._fetch(query, parameters={"name": character_name, "limit": limit})
        return [{"id": r["id"], "user": r["user"], "ai": r["ai"], "time": r["time"]} for r in rows]

    def compress_memories(self, character_name: str, summary_text: str, memory_ids: List[str]) -> None:
        query = """
        MATCH (c:Character {name: $name})-[:RECALLS]->(m:Memory)
        WHERE elementId(m) IN $ids
        WITH c, collect(m) as ms

        FOREACH (_ IN CASE WHEN size(ms) = 0 THEN [] ELSE [1] END |
            CREATE (s:Summary {
                content: $summary,
                timestamp: timestamp(),
                compressed_count: size(ms),
                start_time: reduce(minT = 9223372036854775807, x IN ms |
                    CASE WHEN x.timestamp < minT THEN x.timestamp ELSE minT END),
                end_time: reduce(maxT = 0, x IN ms |
                    CASE WHEN x.timestamp > maxT THEN x.timestamp ELSE maxT END)
            })
            CREATE (c)-[:HAS_SUMMARY]->(s)
        )

        FOREACH (m IN ms | DETACH DELETE m)
        """
        self._run(query, parameters={"name": character_name, "summary": summary_text, "ids": memory_ids})
        logger.info("🧹 Compressed %s memories into 1 summary for %s.", len(memory_ids), character_name)

    # ------------------------------------------------------------------
    # SUMMARY RECALL: LONG-TERM MEMORY
    # ------------------------------------------------------------------
    def get_recent_summaries(self, character_name: str, limit: int = 3) -> List[Dict[str, Any]]:
        query = """
        MATCH (c:Character {name: $name})-[:HAS_SUMMARY]->(s:Summary)
        RETURN s.content as content, s.timestamp as time, s.compressed_count as compressed_count
        ORDER BY s.timestamp DESC
        LIMIT $limit
        """
        rows = self._fetch(query, parameters={"name": character_name, "limit": limit})
        return [
            {"content": r["content"], "compressed_count": r["compressed_count"], "time": r["time"]}
            for r in rows
        ]
