import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import logging
from typing import List, Dict, Any

from config.settings import settings
from core.models import Chapter

logger = logging.getLogger(__name__)

class VectorVault:
    def __init__(self):
        """
        Initializes connection to the ChromaDB container.
        """
        try:
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                settings=Settings(allow_reset=True, anonymized_telemetry=False)
            )
            
            # Use a high-quality, free, local embedding model
            # 'all-MiniLM-L6-v2' is fast and effective for semantic search
            self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            
            # Collection 1: Full Chapters (Macro Context)
            self.chapter_col = self.client.get_or_create_collection(
                name=f"{settings.CHROMA_COLLECTION}_chapters",
                embedding_function=self.embed_fn,
                metadata={"description": "Full chapter texts"}
            )
            
            # Collection 2: Atomic Scenes (Micro Context)
            self.scene_col = self.client.get_or_create_collection(
                name=f"{settings.CHROMA_COLLECTION}_scenes",
                embedding_function=self.embed_fn,
                metadata={"description": "Atomic scene summaries"}
            )
            
            logger.info(f"✅ Connected to ChromaDB at {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to ChromaDB: {e}")
            raise

    def add_chapter(self, chapter: Chapter):
        """
        Embeds the Chapter text AND its individual scenes into Vector Storage.
        """
        # 1. Embed the Full Chapter
        self.chapter_col.upsert(
            ids=[chapter.unique_id],
            documents=[chapter.raw_text],
            metadatas=[{
                "novel_id": chapter.novel_id,
                "chapter_num": chapter.chapter_number,
                "title": chapter.title or "",
                "summary": chapter.summary
            }]
        )
        
        # 2. Embed Each Scene Individually
        if chapter.scenes:
            scene_ids = []
            scene_docs = []
            scene_metas = []
            
            for scene in chapter.scenes:
                # Unique ID: novel_ch01_sc01
                s_id = f"{chapter.unique_id}_sc{scene.order_index:02d}"
                
                # Document: The searchable text
                # We combine summary + significance + characters for rich search
                doc_text = f"Scene Summary: {scene.summary}\n" \
                           f"Significance: {scene.significance}\n" \
                           f"Characters: {', '.join(scene.characters_present)}\n" \
                           f"Location: {scene.location}"
                
                meta = {
                    "novel_id": chapter.novel_id,
                    "chapter_num": chapter.chapter_number,
                    "scene_index": scene.order_index,
                    "location": scene.location or "Unknown"
                }
                
                scene_ids.append(s_id)
                scene_docs.append(doc_text)
                scene_metas.append(meta)
            
            self.scene_col.upsert(
                ids=scene_ids,
                documents=scene_docs,
                metadatas=scene_metas
            )
            
        logger.info(f"💾 Vectorized Ch {chapter.chapter_number}: Added {len(chapter.scenes)} scenes.")

    def search(self, query: str, n_results: int = 3) -> Dict[str, List[str]]:
        """
        Hybrid search: returns matching full chapters AND specific scenes.
        """
        results = {}
        
        # Macro Search
        ch_res = self.chapter_col.query(query_texts=[query], n_results=1)
        results['chapters'] = ch_res['documents'][0] if ch_res['documents'] else []
        
        # Micro Search
        sc_res = self.scene_col.query(query_texts=[query], n_results=n_results)
        results['scenes'] = sc_res['documents'][0] if sc_res['documents'] else []
        
        return results