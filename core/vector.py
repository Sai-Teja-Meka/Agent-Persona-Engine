# core/vector.py

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from config.settings import settings
from core.models import Chapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChromaConfig:
    host: str
    port: int
    collection_prefix: str
    allow_reset: bool = True
    anonymized_telemetry: bool = False

    # If True, VectorVault.__init__ will raise if Chroma can't be reached.
    # If False, it will log and run in a "not ready" state until ping() succeeds.
    strict: bool = True

    # Connection retry (helpful for container orchestration cold-start)
    connect_retries: int = 6
    connect_base_delay_s: float = 0.4
    connect_max_delay_s: float = 5.0

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"


class VectorVault:
    """
    Chroma-backed vector store for:
      - Full chapters (macro context)
      - Atomic scenes (micro context)

    Key behaviors:
      - Uses HttpClient
      - Performs an explicit heartbeat() to confirm Chroma connectivity
      - Optional retry/backoff on connect
    """

    def __init__(self, cfg: Optional[ChromaConfig] = None):
        self.cfg = cfg or ChromaConfig(
            host=settings.CHROMA_HOST,
            port=int(settings.CHROMA_PORT),
            collection_prefix=settings.CHROMA_COLLECTION,
        )

        self.client: Optional[chromadb.HttpClient] = None
        self.embed_fn = None
        self.chapter_col = None
        self.scene_col = None

        self._ready: bool = False
        self._last_error: Optional[str] = None

        self._connect_and_init()

    # ----------------------------
    # Public API
    # ----------------------------
    def health(self) -> Dict[str, Any]:
        return {
            "ready": self._ready,
            "last_error": self._last_error,
            "host": self.cfg.host,
            "port": self.cfg.port,
            "collection_prefix": self.cfg.collection_prefix,
        }

    def ping(self) -> None:
        """
        Hard check: raises if Chroma cannot be reached.
        """
        if not self.client:
            raise RuntimeError("Chroma client not initialized")
        # heartbeat() forces an HTTP round-trip
        self.client.heartbeat()

    def ensure_ready(self) -> None:
        """
        Raises a clear error if VectorVault isn't usable (e.g., Chroma down).
        """
        if not self._ready:
            raise RuntimeError(f"Chroma not ready: {self._last_error or 'unknown error'}")

    def add_chapter(self, chapter: Chapter) -> None:
        """
        Embeds the Chapter text AND its individual scenes into Vector Storage.
        """
        self.ensure_ready()

        assert self.chapter_col is not None
        assert self.scene_col is not None

        # 1) Embed the full chapter
        self.chapter_col.upsert(
            ids=[chapter.unique_id],
            documents=[chapter.raw_text],
            metadatas=[
                {
                    "novel_id": chapter.novel_id,
                    "chapter_num": chapter.chapter_number,
                    "title": chapter.title or "",
                    "summary": chapter.summary,
                }
            ],
        )

        # 2) Embed scenes
        scenes = chapter.scenes or []
        if scenes:
            scene_ids: List[str] = []
            scene_docs: List[str] = []
            scene_metas: List[Dict[str, Any]] = []

            for scene in scenes:
                s_id = f"{chapter.unique_id}_sc{scene.order_index:02d}"

                doc_text = (
                    f"Scene Summary: {scene.summary}\n"
                    f"Significance: {scene.significance}\n"
                    f"Characters: {', '.join(scene.characters_present)}\n"
                    f"Location: {scene.location}"
                )

                meta = {
                    "novel_id": chapter.novel_id,
                    "chapter_num": chapter.chapter_number,
                    "scene_index": scene.order_index,
                    "location": scene.location or "Unknown",
                }

                scene_ids.append(s_id)
                scene_docs.append(doc_text)
                scene_metas.append(meta)

            self.scene_col.upsert(ids=scene_ids, documents=scene_docs, metadatas=scene_metas)

        logger.info(
            "💾 Vectorized Ch %s: chapter upserted; scenes added=%s",
            chapter.chapter_number,
            len(scenes),
        )

    def search(self, query: str, n_results: int = 3) -> Dict[str, List[str]]:
        """
        Hybrid search: returns matching full chapters AND specific scenes.
        """
        self.ensure_ready()

        assert self.chapter_col is not None
        assert self.scene_col is not None

        results: Dict[str, List[str]] = {"chapters": [], "scenes": []}

        # Macro search (1 chapter)
        ch_res = self.chapter_col.query(query_texts=[query], n_results=1)
        if ch_res and ch_res.get("documents") and ch_res["documents"][0]:
            results["chapters"] = ch_res["documents"][0]

        # Micro search (N scenes)
        sc_res = self.scene_col.query(query_texts=[query], n_results=n_results)
        if sc_res and sc_res.get("documents") and sc_res["documents"][0]:
            results["scenes"] = sc_res["documents"][0]

        return results

    # ----------------------------
    # Internals
    # ----------------------------
    def _connect_and_init(self) -> None:
        """
        Establishes a Chroma HttpClient, verifies reachability, sets up embedding function,
        and creates/loads collections.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.cfg.connect_retries + 1):
            try:
                self.client = chromadb.HttpClient(
                    host=self.cfg.host,
                    port=self.cfg.port,
                    settings=Settings(
                        allow_reset=self.cfg.allow_reset,
                        anonymized_telemetry=self.cfg.anonymized_telemetry,
                    ),
                )

                # Verify the server is reachable before doing anything else
                self.client.heartbeat()

                # Embedding function (local SentenceTransformer)
                self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self.cfg.embedding_model
                )

                # Collections
                self.chapter_col = self.client.get_or_create_collection(
                    name=f"{self.cfg.collection_prefix}_chapters",
                    embedding_function=self.embed_fn,
                    metadata={"description": "Full chapter texts"},
                )
                self.scene_col = self.client.get_or_create_collection(
                    name=f"{self.cfg.collection_prefix}_scenes",
                    embedding_function=self.embed_fn,
                    metadata={"description": "Atomic scene summaries"},
                )

                self._ready = True
                self._last_error = None
                logger.info("✅ Connected to ChromaDB at %s:%s", self.cfg.host, self.cfg.port)
                return

            except Exception as e:
                last_exc = e
                self._ready = False
                self._last_error = str(e)

                delay = min(
                    self.cfg.connect_base_delay_s * (2 ** (attempt - 1)),
                    self.cfg.connect_max_delay_s,
                )
                logger.warning(
                    "Chroma not ready (attempt %s/%s): %s; retrying in %.2fs",
                    attempt,
                    self.cfg.connect_retries,
                    e,
                    delay,
                )
                time.sleep(delay)

        # Exhausted retries
        msg = f"❌ Failed to connect to ChromaDB at {self.cfg.host}:{self.cfg.port}: {self._last_error}"
        if self.cfg.strict:
            logger.error(msg)
            raise RuntimeError(msg) from last_exc
        else:
            logger.error("%s (continuing in degraded mode)", msg)
