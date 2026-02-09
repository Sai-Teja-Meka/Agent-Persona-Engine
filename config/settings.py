# config/settings.py

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized configuration for The Infinite Library.
    Reads from environment variables and .env file.

    Notes:
    - Neo4j Aura commonly uses neo4j+s://<id>.databases.neo4j.io (TLS + routing). [web:34]
    - Local Neo4j is usually neo4j://localhost:7687 or bolt://localhost:7687. [web:37]
    """

    # --- Project Metadata ---
    PROJECT_NAME: str = "The Infinite Library"
    VERSION: str = "1.0.0-Phoenix"

    # --- Database: Neo4j (Graph) ---
    # For local dev:
    #   neo4j://localhost:7687  (routing; safe default) [web:37]
    # For Aura:
    #   neo4j+s://xxxxx.databases.neo4j.io  (TLS + routing) [web:34]
    NEO4J_URI: str = "neo4j://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4jneo4jneo4j"
    NEO4J_DATABASE: Optional[str] = None

    # If True, your KnowledgeGraph bootstrap can be configured to fail hard instead of degraded mode.
    NEO4J_STRICT: bool = False

    # --- Database: Chroma (Vector) ---
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION: str = "infinite_knowledge"

    # If True, VectorVault can fail hard when it can't reach Chroma.
    CHROMA_STRICT: bool = True

    # --- Cognition: LLM (Gemini) ---
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "models/text-embedding-004"

    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # --- Cognition: LLM (Groq) ---
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # --- Pipeline Settings ---
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Load from .env file automatically
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def effective_public_config(self) -> dict:
        """
        For startup logs / /health: returns non-secret config.
        """
        return {
            "NEO4J_URI": self.NEO4J_URI,
            "NEO4J_USER": self.NEO4J_USER,
            "NEO4J_DATABASE": self.NEO4J_DATABASE,
            "NEO4J_STRICT": self.NEO4J_STRICT,
            "CHROMA_HOST": self.CHROMA_HOST,
            "CHROMA_PORT": self.CHROMA_PORT,
            "CHROMA_COLLECTION": self.CHROMA_COLLECTION,
            "CHROMA_STRICT": self.CHROMA_STRICT,
        }


@lru_cache
def get_settings() -> Settings:
    """Singleton pattern to fetch settings efficiently."""
    return Settings()


settings = get_settings()
