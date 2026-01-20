"""
Application Configuration
Centralized settings management using Pydantic Settings
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Application
    APP_NAME: str = "Home Guard API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "AI-powered home repair assistant"
    DEBUG: bool = False

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"

    # CORS
    CORS_ORIGINS: str = "*"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "*"
    CORS_ALLOW_HEADERS: str = "*"

    # Azure Cosmos DB Configuration
    COSMOS_DB_ENDPOINT: Optional[str] = None
    COSMOS_DB_KEY: Optional[str] = None
    COSMOS_DB_DATABASE_NAME: str = "homeguard"
    COSMOS_DB_CONTAINER_NAME: str = "items"
    COSMOS_DB_CLUSTER_CONTAINER_NAME: str = "zipcodeClusters"

    # Azure AI Foundry Agent Configuration
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_AI_PROJECT_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_AGENT_ID: str = os.getenv("AZURE_AGENT_ID")
    AZURE_AI_MODEL_DEPLOYMENT_NAME: str = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")

    # Server Configuration
    PORT: int = 5000

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Use @lru_cache to create a singleton
    """
    return Settings()


# Export settings instance
settings = get_settings()
