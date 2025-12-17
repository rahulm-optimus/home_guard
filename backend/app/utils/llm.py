"""
LLM Utilities
Helper functions for Azure OpenAI interactions
"""
from langchain_openai import AzureChatOpenAI
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Singleton instance
_llm_instance = None


def get_llm() -> AzureChatOpenAI:
    """
    Get or create Azure OpenAI LLM instance (singleton)
    
    Returns:
        AzureChatOpenAI: Configured LLM instance
    """
    global _llm_instance
    
    if _llm_instance is None:
        try:
            _llm_instance = AzureChatOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                deployment_name=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                temperature=settings.AZURE_OPENAI_TEMPERATURE
            )
            logger.info("Azure OpenAI LLM initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI LLM: {str(e)}")
            raise
    
    return _llm_instance


def reset_llm():
    """Reset the LLM instance (useful for testing)"""
    global _llm_instance
    _llm_instance = None
