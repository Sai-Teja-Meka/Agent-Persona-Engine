import logging
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config.settings import settings
from core.graph import KnowledgeGraph

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self):
        self.kg = KnowledgeGraph()
        self.llm = self._init_llm()

    def _init_llm(self):
        """Uses a cheaper/faster model for summarization tasks if available."""
        if getattr(settings, "GOOGLE_API_KEY", None):
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.3,
            )

        if getattr(settings, "DEEPSEEK_API_KEY", None):
            return ChatOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                model=getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat"),
                base_url="https://api.deepseek.com",
            )

        raise RuntimeError("No LLM configured for MemoryManager")


    def prune_character_memory(self, character_name: str, threshold: int = 20, compress_batch: int = 10):
        """
        Checks if memory exceeds threshold. If so, compresses the oldest batch.
        """
        # 1. Check Count
        count = self.kg.get_memory_count(character_name)
        if count < threshold:
            # logger.info(f"🧠 Memory load nominal ({count}/{threshold}). No action.")
            return

        logger.info(f"🧠 Memory overflow ({count}/{threshold}). Initiating compression...")

        # 2. Fetch Oldest Memories
        old_memories = self.kg.get_oldest_memories(character_name, limit=compress_batch)
        if not old_memories:
            return

        # 3. Format for LLM
        transcript = "\n".join([f"User: {m['user']}\n{character_name}: {m['ai']}" for m in old_memories])
        memory_ids = [m['id'] for m in old_memories]

        # 4. Generate Summary
        prompt = ChatPromptTemplate.from_template(
            """
            You are a Memory Compressor for an AI Character.
            Compress the following conversation transcript into a single, dense paragraph.
            Retain key facts, names, and emotional shifts. Discard pleasantries ("Hello", "Goodbye").
            
            TRANSCRIPT:
            {transcript}
            
            SUMMARY:
            """
        )
        try:
            chain = prompt | self.llm | StrOutputParser()
            summary_text = chain.invoke({"transcript": transcript})
            self.kg.compress_memories(character_name, summary_text, memory_ids)
        except Exception as e:
            logger.error(f"Memory compression failed (skipping): {e}")
            return
