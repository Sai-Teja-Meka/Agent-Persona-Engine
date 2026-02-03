import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import logging
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from config.settings import settings
from core.models import Chapter

logger = logging.getLogger(__name__)

class VectorVault:
    def __init__(self):
        """Initialize ChromaDB client (with fallback)"""
        try:
            self.client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port
        )
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.chapter_collection = self.client.get_or_create_collection("chapters")
            self.scene_collection = self.client.get_or_create_collection("scenes")
            self.available = True
        except Exception as e:
            print(f"⚠️ ChromaDB unavailable: {e}")
            self.available = False
            self.client = None
            self.embedding_model = None
            self.chapter_collection = None
            self.scene_collection = None


    def add_chapter(self, chapter: Chapter):
        """
        Embeds the Chapter text AND its individual scenes into Vector Storage.
        """
        # 1. Embed the Full Chapter
        self.chapter_collection.upsert(  # ← change col to collection
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
            
            self.scene_collection.upsert(  # ← change col to collection
                ids=scene_ids,
                documents=scene_docs,
                metadatas=scene_metas
            )
            
        logger.info(f"💾 Vectorized Ch {chapter.chapter_number}: Added {len(chapter.scenes)} scenes.")

    def search_chapters(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search chapter collection"""
        if not self.available:
            return []
    
        try:
            ch_res = self.chapter_collection.query(query_texts=[query], n_results=top_k)
            return ch_res['documents'][0] if ch_res['documents'] else []
        except Exception as e:
            logger.error(f"Chapter search failed: {e}")
            return []
        
    
    def search_scenes(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search scene collection"""
        if not self.available:
            return []
    
        try:
            sc_res = self.scene_collection.query(query_texts=[query], n_results=top_k)
            return sc_res['documents'][0] if sc_res['documents'] else []
        except Exception as e:
            logger.error(f"Scene search failed: {e}")
            return []
