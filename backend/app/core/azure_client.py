from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, CredentialUnavailableError
from app.core.config import settings
from app.core.exceptions import ServiceError
import threading
import time

_client_lock = threading.Lock()
_shared_client = None
_shared_credential = None

def get_azure_ai_client():
    """
    Get a cached AIProjectClient, refresh if token expired or authentication fails.
    """
    global _shared_client, _shared_credential
    max_retries = 3
    delay = 1  # seconds

    for attempt in range(1, max_retries + 1):
        with _client_lock:
            try:
                # Create credential if missing or reset
                if _shared_credential is None:
                    _shared_credential = DefaultAzureCredential()

                # Create client if missing
                if _shared_client is None:
                    _shared_client = AIProjectClient(
                        credential=_shared_credential,
                        endpoint=settings.AZURE_AI_PROJECT_ENDPOINT
                    )
                
                # Test token by forcing a small request
                # (Optional: ping an endpoint to verify auth)
                return _shared_client

            except CredentialUnavailableError as e:
                # Credential expired or unavailable → reset and retry
                _shared_credential = None
                _shared_client = None
                if attempt < max_retries:
                    time.sleep(delay)
                    continue
                raise ServiceError(
                    message="Unable to authenticate with Azure. Token may have expired.",
                    error_code="AZURE_CREDENTIAL_ERROR",
                    details={"original_error": str(e)}
                )
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(delay)
                    continue
                raise ServiceError(
                    message="Unable to authenticate with Azure.",
                    error_code="AZURE_CREDENTIAL_ERROR",
                    details={"original_error": str(e)}
                )
