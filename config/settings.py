import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    """
    Centralized configuration for The Infinite Library.
    Reads from environment variables and .env file.
    """
    
    # --- Project Metadata ---
    PROJECT_NAME: str = "The Infinite Library"
    VERSION: str = "1.0.0-Phoenix"
    
    # --- Database: Neo4j (Graph) ---
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4jneo4jneo4j"
    
    # --- Database: Chroma (Vector) ---
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION: str = "infinite_knowledge"
    
    # --- Cognition: LLM (Gemini) ---
    GOOGLE_API_KEY: str  # Required field (will fail if missing)
    GEMINI_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "models/text-embedding-004"

    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    # --- Cognition: LLM (Groq) ---
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
        # --- Pipeline Settings ---
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    @property
    def chroma_enabled(self) -> bool:
        """Check if ChromaDB is configured and reachable"""
        try:
            import requests
            response = requests.get(
                f"http://{self.CHROMA_HOST}:{self.CHROMA_PORT}/api/v1/heartbeat", 
                timeout=2
            )
            return response.status_code == 200
        except:
            return False
    
    # Load from .env file automatically
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    """Singleton pattern to fetch settings efficiently."""
    return Settings()

# Global instance
settings = get_settings()