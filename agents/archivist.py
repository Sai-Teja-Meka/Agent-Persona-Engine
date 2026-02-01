import logging
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from google.api_core.exceptions import ResourceExhausted
from config.settings import settings
from core.models import Chapter, Scene, CharacterState, EmotionalState
import re
import json

logger = logging.getLogger(__name__)

def extract_json(text: str) -> dict:
    """
    Extracts the first JSON object found in text.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM output.")
    return json.loads(match.group())

def normalize_emotion(value: str) -> EmotionalState:
    mapping = {
        "CONFIDENCE": EmotionalState.DETERMINATION,
        "CALM": EmotionalState.NEUTRAL,
        "PRIDE": EmotionalState.JOY,
        "RAGE": EmotionalState.ANGER,
        "KILLING_INTENT": EmotionalState.MURDEROUS_INTENT,
    }
    return mapping.get(value, EmotionalState.NEUTRAL)

class ArchivistAgent:
    def __init__(self):
        self.llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        temperature=0.0,
        max_tokens=8192
    )

        self.parser = JsonOutputParser()

    @retry(
        retry=retry_if_exception_type(ResourceExhausted),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(10)
    )
    def analyze_chapter(self, novel_id: str, chapter_num: int, text: str, previous_state: str, power_ranks: List[str]) -> Chapter:
        
        # Convert list of ranks to a string for the prompt
        ranks_str = ", ".join(power_ranks) if power_ranks else "Unknown System"

        prompt = ChatPromptTemplate.from_template(
    """
You are The Archivist, a Realm-Aware Literary Engine.

WORLD PHYSICS (Cultivation System):
The valid power ranks in this world are (from lowest to highest):
[{ranks}]

PREVIOUS CONTEXT:
{previous_state}

CURRENT TEXT (Chapter {chapter_num}):
{text}

TASK:
1. Summarize the plot (3-5 sentences).
2. Extract Scenes (atomic events).
3. For every major character present, generate a CharacterState.

STRICT OUTPUT RULES (CRITICAL):
- Output MUST be valid JSON
- Output MUST contain ONLY JSON
- Do NOT use Markdown
- Do NOT add explanations, notes, or commentary
- All string values MUST be wrapped in double quotes
- If information is missing, use "Unknown" or "None"

OUTPUT JSON SCHEMA:
{{
  "summary": "string",
  "state_vector": "string",
  "scenes": [
    {{
      "order_index": 1,
      "summary": "string",
      "characters_present": ["string"],
      "location": "string",
      "significance": "string"
    }}
  ],
  "character_states": [
    {{
      "character_name": "string",
      "current_power_rank": "string",
      "current_emotional_state": "NEUTRAL",
      "current_location": "string",
      "personality_snapshot": "string"
    }}
  ]
}}

REMEMBER:
Return ONLY the JSON object. No text before or after.
"""
)

        chain = prompt | self.llm | self.parser
        
        try:
            result = chain.invoke({
                "ranks": ranks_str,
                "previous_state": previous_state,
                "chapter_num": chapter_num,
                "text": text[:50000]
            })
            
            # Reconstruct Pydantic Models
            scenes = [
                Scene(
                    order_index=s['order_index'],
                    summary=s['summary'],
                    characters_present=s['characters_present'],
                    location=s.get('location'),
                    significance=s['significance']
                ) for s in result.get('scenes', [])
            ]
            
            char_states = [
                CharacterState(
                    character_name=cs['character_name'],
                    novel_id=novel_id,
                    chapter_number=chapter_num,
                    current_power_rank=cs.get('current_power_rank'),
                    current_emotional_state=normalize_emotion(cs.get("current_emotional_state", "NEUTRAL")),
                    current_location=cs.get('current_location'),
                    personality_snapshot=cs.get('personality_snapshot', "No change.")
                ) for cs in result.get('character_states', [])
            ]
            
            return Chapter(
                novel_id=novel_id,
                chapter_number=chapter_num,
                title=f"Chapter {chapter_num}",
                raw_text=text,
                summary=result['summary'],
                state_vector=result['state_vector'],
                scenes=scenes,
                character_states=char_states # Link the states to the chapter object
            )
            
        except Exception as e:
            logger.error(f"❌ Analysis failed for Ch {chapter_num}: {e}")
            raise e