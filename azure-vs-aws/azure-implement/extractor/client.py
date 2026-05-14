from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
 
from config import settings
 
 
def get_client() -> DocumentIntelligenceClient:
    """Return a ready-to-use DocumentIntelligenceClient."""
    return DocumentIntelligenceClient(
        endpoint=settings.endpoint,
        credential=AzureKeyCredential(settings.key),
    )
 