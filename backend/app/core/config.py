"""
Application Configuration
Centralized settings management using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
import os 
from dotenv import load_dotenv

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

    # Azure Cosmos DB Configuration (Legacy - keeping for backward compatibility)
    COSMOS_DB_ENDPOINT: Optional[str] = None
    COSMOS_DB_KEY: Optional[str] = None
    COSMOS_DB_DATABASE_NAME: str = "homeguard"
    COSMOS_DB_CONTAINER_NAME: str = "estimates"
    COSMOS_DB_CLUSTER_CONTAINER_NAME: str = "zipcodeClusters"

    # SQL Server Configuration
    SQL_SERVER: Optional[str] = None
    SQL_DATABASE: str = "PlsBody"
    SQL_USERNAME: Optional[str] = None
    SQL_PASSWORD: Optional[str] = None
    SQL_DRIVER: str = "ODBC Driver 17 for SQL Server"
    SQL_CONNECTION_TIMEOUT: int = 120  # Increased for large cluster operations
    SQL_ENCRYPT: bool = True
    SQL_TRUST_SERVER_CERTIFICATE: bool = True

    # Azure AI Foundry Agent Configuration
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_AI_PROJECT_ENDPOINT: Optional[str] = None
    AZURE_CHAT_AGENT_ID: Optional[str] = None
    AZURE_AGENT_ID: Optional[str] = None
    AZURE_AI_MODEL_DEPLOYMENT_NAME: str = "gpt-4o"
   
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
