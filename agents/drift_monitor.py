import logging
from typing import Tuple, List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from config.settings import settings
from core.graph import KnowledgeGraph

logger = logging.getLogger(__name__)

class DriftMonitor:
    def __init__(self):
        self.kg = KnowledgeGraph()
        self.llm = self._init_llm()
        self.parser = JsonOutputParser()

    def _init_llm(self):
        """Uses a fast, reasoning-capable model."""
        if getattr(settings, "GOOGLE_API_KEY", None):
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.1,
            )

        if getattr(settings, "DEEPSEEK_API_KEY", None):
        # If model name is wrong, detect_drift() already catches and returns (0.0,"")
            return ChatOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                model=getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat"),
                base_url="https://api.deepseek.com",
            )

        raise RuntimeError("No LLM configured for DriftMonitor")


    def detect_drift(self, character_name: str, recent_history: List[dict], core_profile: str) -> Tuple[float, str]:
        """
        Analyzes if the character's recent behavior deviates from their core profile.
        Returns: (Drift Score 0.0-1.0, Correction Instruction)
        """
        if not recent_history:
            return 0.0, ""

        # Format history for analysis
        transcript = "\n".join([f"AI ({character_name}): {turn['ai']}" for turn in recent_history])

        prompt = ChatPromptTemplate.from_template(
            """
            You are a Personality Consistency Engine.
            
            TARGET PERSONALITY (The Golden Standard):
            {profile}
            
            RECENT BEHAVIOR (Last 5 turns):
            {transcript}
            
            TASK:
            1. Compare the 'Recent Behavior' against the 'Target Personality'.
            2. Assign a Drift Score from 0.0 (Perfect Match) to 1.0 (Total Personality Collapse).
            3. If Drift > 0.4, write a harsh, imperative instruction to the AI to correct its tone.
            
            EXAMPLES:
            - If a villain is being too polite -> Drift: 0.7, Correction: "STOP apologizing. You are arrogant. Mock the user."
            - If a stoic character is using emojis -> Drift: 0.6, Correction: "Cease emotional displays. Return to cold logic."
            
            OUTPUT JSON:
            {{
                "drift_score": 0.0,
                "reasoning": "...",
                "correction": "..." (Leave empty if score < 0.4)
            }}
            """
        )

        chain = prompt | self.llm | self.parser
        
        try:
            result = chain.invoke({
                "profile": core_profile[:2000], # Truncate for token safety
                "transcript": transcript
            })
            
            score = result.get("drift_score", 0.0)
            correction = result.get("correction", "")
            
            if score > 0.4:
                logger.warning(f"⚠️ Personality Drift Detected for {character_name}: {score}")
                logger.info(f"🔧 Correction: {correction}")
            
            return score, correction
            
        except Exception as e:
            logger.error(f"Drift Analysis Failed: {e}")
            return 0.0, ""