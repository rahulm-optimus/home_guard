"""
Application Configuration
Centralized settings management using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


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
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4"
    AZURE_OPENAI_TEMPERATURE: float = 0.3
    
    # Timeouts
    LLM_TIMEOUT: int = 30
    
    # Azure Cosmos DB Configuration
    COSMOS_DB_ENDPOINT: Optional[str] = None
    COSMOS_DB_KEY: Optional[str] = None
    COSMOS_DB_DATABASE_NAME: str = "homeguard"
    COSMOS_DB_CONTAINER_NAME: str = "items"
    
    # Azure AI Foundry Agent Configuration
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_AI_PROJECT_ENDPOINT: str = "https://aif-home-inspection-ai-dev-wu-01.services.ai.azure.com/api/projects/proj-home-inspection-ai-dev-wu-01"
    AZURE_AI_AGENT_ID: str = "asst_DIzNuZfJv2qblsqPnySbyzde"
    AZURE_CHAT_AGENT_ID: str = "asst_BFZt4Wu3VmOom3rzXuufpg8I"
    AZURE_AI_MODEL_DEPLOYMENT_NAME: str = "gpt-4o"
    BING_PROJECT_CONNECTION_ID: str = "/subscriptions/e10b341a-ea6d-42ef-80a4-5d430deb0782/resourceGroups/OptimusRG/providers/Microsoft.CognitiveServices/accounts/aif-home-inspection-ai-dev-wu-01/projects/proj-home-inspection-ai-dev-wu-01/connections/gbscostestimatordev01"
    
    # Agent Feature Flags
    AZURE_AGENT_USE_BING: bool = True
    AZURE_AGENT_CHECK_DB_FIRST: bool = True
    
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
