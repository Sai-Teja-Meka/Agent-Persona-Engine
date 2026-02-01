from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, computed_field
from datetime import datetime
import uuid

# --- Enums for Standardization ---

class EntityType(str, Enum):
    CHARACTER = "CHARACTER"
    LOCATION = "LOCATION"
    OBJECT = "OBJECT"
    FACTION = "FACTION"
    TECHNIQUE = "TECHNIQUE"  # New: To track martial arts/skills

class EmotionalState(str, Enum):
    JOY = "JOY"
    SADNESS = "SADNESS"
    ANGER = "ANGER"
    FEAR = "FEAR"
    NEUTRAL = "NEUTRAL"
    DETERMINATION = "DETERMINATION"
    CONFUSION = "CONFUSION"
    MURDEROUS_INTENT = "MURDEROUS_INTENT" # Genre-specific addition

# --- Feature 6: Power & Cultivation Hierarchy ---

class CultivationRank(BaseModel):
    """
    A single step in the power ladder (scraped from Wiki).
    Example: {name: 'Divine Sea', order_index: 50, sub_realm: 'Late Stage'}
    """
    name: str = Field(..., description="Name of the rank (e.g., 'Mortal Blood')")
    order_index: int = Field(..., description="Numeric power value for sorting/logic (e.g., 1, 2, 10)")
    description: Optional[str] = None
    major_realm: str = Field(..., description="The broad realm this belongs to")
    sub_realm: Optional[str] = Field(None, description="Specific stage (Early, Mid, Late, Peak)")

class PowerHierarchy(BaseModel):
    """
    The 'Physics' of the novel. Defined BEFORE ingestion via Wiki.
    """
    novel_id: str
    system_name: str = Field(..., description="e.g., 'Essence Gathering System'")
    ranks: List[CultivationRank] = Field(default_factory=list)

# --- Feature 1: Identity & Namespacing ---

class NovelNamespace(BaseModel):
    """
    The Container for World Truths. 
    Isolates this novel's logic from others in the same DB.
    """
    novel_id: str
    title: str
    wiki_url: Optional[str] = None
    power_hierarchy: Optional[PowerHierarchy] = None
    known_factions: List[str] = Field(default_factory=list)
    known_locations: List[str] = Field(default_factory=list)

# --- Feature 4: Temporal Character States ---

class CharacterState(BaseModel):
    """
    A snapshot of a character at a specific Chapter.
    Tracks 'Drift', 'Power Growth', and 'Emotion' over time.
    """
    character_name: str
    novel_id: str
    chapter_number: int
    
    # Mutable State
    current_power_rank: Optional[str] = Field(None, description="Linked to CultivationRank")
    current_emotional_state: EmotionalState = EmotionalState.NEUTRAL
    current_location: Optional[str] = None
    active_allies: List[str] = Field(default_factory=list)
    active_enemies: List[str] = Field(default_factory=list)
    
    # Personality Tracking
    personality_snapshot: str = Field(..., description="Short summary of demeanor in this chapter")
    
    @computed_field
    def unique_id(self) -> str:
        return f"{self.novel_id}_{self.character_name}_ch{self.chapter_number}"

class Character(BaseModel):
    """
    The Invariant Soul. 
    This node exists outside of time and links to all Temporal States.
    """
    name: str = Field(..., description="Canonical name")
    novel_id: str
    description: str
    aliases: List[str] = Field(default_factory=list)
    role: str = Field("Minor", description="Protagonist, Antagonist, Support")
    
    # Wiki Data (The Golden Standard)
    wiki_profile_link: Optional[str] = None
    base_personality: str = Field(..., description="The 'Golden Standard' personality from Wiki/Chapter 1")

# --- Narrative Structures (Updated) ---

class Interaction(BaseModel):
    source: str
    target: str
    type: str
    context: str

class Scene(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_index: int
    summary: str
    characters_present: List[str]
    location: Optional[str] = None
    interactions: List[Interaction] = Field(default_factory=list)
    significance: str

class Chapter(BaseModel):
    novel_id: str
    chapter_number: int
    title: Optional[str] = None
    raw_text: str
    summary: str
    scenes: List[Scene] = Field(default_factory=list)
    state_vector: str
    
    # Links to the character states updated in this chapter
    character_states: List[CharacterState] = Field(default_factory=list)

    @computed_field
    def word_count(self) -> int:
        return len(self.raw_text.split())

    @computed_field
    def unique_id(self) -> str:
        return f"{self.novel_id}_ch_{self.chapter_number:04d}"

class Novel(BaseModel):
    id: str
    title: str
    namespace: NovelNamespace  # Embeds the World Rules
    total_chapters_ingested: int = 0
    last_updated: datetime = Field(default_factory=datetime.now)