from typing import List, Tuple, Dict, Optional
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from core.graph import KnowledgeGraph
from core.vector import VectorVault
from agents.memory_manager import MemoryManager
from agents.drift_monitor import DriftMonitor
from config.settings import settings

logger = logging.getLogger(__name__)


class CharacterSoul:
    def __init__(self, character_name: str):
        self.name = character_name
        self.kg = KnowledgeGraph()
        self.vault = VectorVault()
        self.memory_manager = MemoryManager()
        self.drift_monitor = DriftMonitor()
        self.turn_counter = 0

        self.profile = self._load_character_profile()
        self.llm = self._init_chat_llm()

    # --------------------------------------------------
    # Initialization Helpers
    # --------------------------------------------------
    def _init_chat_llm(self):

        # (Same as before...)

        if getattr(settings, "DEEPSEEK_API_KEY", None):

            return ChatOpenAI(

                api_key=settings.DEEPSEEK_API_KEY,

                model=settings.DEEPSEEK_MODEL,

                temperature=0.7,

                max_tokens=2048,

                base_url="https://api.deepseek.com"

            )

        if getattr(settings, "GOOGLE_API_KEY", None):

            return ChatGoogleGenerativeAI(

                model=settings.GEMINI_MODEL,

                google_api_key=settings.GOOGLE_API_KEY,

                temperature=0.7,

                max_output_tokens=2048

            )

        raise RuntimeError("❌ No CHAT LLM configured")

    def _load_character_profile(self) -> str:
        query = """
        MATCH (c:Character {name: $name})
        RETURN c.description AS desc
        """
        with self.kg.driver.session() as session:
            res = session.run(query, {"name": self.name}).single()
            if res and res["desc"]:
                return res["desc"]
        return "A mysterious figure whose past is shrouded in legend."

    # --------------------------------------------------
    # Memory Recall
    # --------------------------------------------------
    def deep_recall(
        self, user_input: str
    ) -> Tuple[List[str], List[str], List[dict], List[dict]]:
        # 1. Vector (Sensory)
        vector_results = self.vault.search(f"{self.name} {user_input}", n_results=3)
        memories = vector_results.get("scenes", [])

        # 2. Graph (Logic / Relationships)
        graph_query = """
        MATCH (me:Character {name: $name})-[r]-(other)
        WHERE toLower($user_input) CONTAINS toLower(other.name)
        RETURN type(r) AS relation, other.name AS entity, other.description AS desc
        LIMIT 5
        """
        logic_facts = []
        with self.kg.driver.session() as session:
            records = session.run(
                graph_query,
                parameters={"name": self.name, "user_input": user_input}
            )
            for record in records:
                logic_facts.append(
                    f"I have a relationship '{record['relation']}' "
                    f"with {record['entity']} ({record['desc']})."
                )

        # 3. Long-Term Memory (Summaries)
        summaries = self.kg.get_recent_summaries(self.name, limit=3)

        # 4. Recent History (Short-Term)
        chat_history = self.kg.get_recent_chat_history(self.name, limit=10)

        return memories, logic_facts, chat_history, summaries

    # --------------------------------------------------
    # Dialogue
    # --------------------------------------------------
    def speak(    self,
    user_input: str,
    memories: Optional[List[str]] = None,
    facts: Optional[List[str]] = None,
    chat_history: Optional[List[dict]] = None,
    summaries: Optional[List[dict]] = None) -> str:
        # Retrieve Context (UPDATED)
        # Inside soul.speak()
        if any(x is None for x in [memories, facts, chat_history, summaries]):
    # Only fetch if we are missing any piece of the puzzle
         memories, facts, chat_history, summaries = self.deep_recall(user_input)

        # Drift Detection
        drift_correction = ""
        if len(chat_history) >= 3:
            recent_history = chat_history[-5:]
            try:
                score, instruction = self.drift_monitor.detect_drift(
                    self.name, recent_history, self.profile
                )
                if score > 0.9 and instruction:
                    drift_correction = f"\n[⚠️ SYSTEM WARNING: {instruction}]"
            except Exception as e:
                logger.error(f"Drift check failed (continuing): {e}")


        # Long-Term Memory Block
        summary_block = "\n".join(
            [f"- {s['content']}" for s in summaries]
        ) if summaries else "No long-term archives yet."

        # Conversation History Block
        history_block = ""
        for turn in chat_history:
            history_block += f"USER: {turn['user']}\n"
            history_block += f"{self.name.upper()}: {turn['ai']}\n"

        system_prompt = f"""
You are {self.name}.

[CORE IDENTITY]
{self.profile}

[LONG-TERM MEMORY]
{summary_block}

[LOGICAL CONTEXT]
{chr(10).join(f'- {f}' for f in facts)}

[SENSORY MEMORIES]
{chr(10).join(f'- {m}' for m in memories)}

[PREVIOUS CONVERSATION]
{history_block if history_block else "No recent memories."}

[DIRECTIVE]
- Respond to the user in character.
- Maintain continuity.
- Stay consistent with your personality.{drift_correction}
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_input)
        ])

        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke({})

        # Persist Interaction
        self.kg.log_interaction(self.name, user_input, response)

        self.turn_counter += 1
        if self.turn_counter % 5 == 0:
            try:
                self.memory_manager.prune_character_memory(self.name)
            except Exception as e:
                logger.error(f"Prune failed (continuing): {e}")
       
        return response        