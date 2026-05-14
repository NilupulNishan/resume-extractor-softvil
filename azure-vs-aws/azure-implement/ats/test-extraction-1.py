from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from config import settings


def extract_text(file_path: str, endpoint: str, key: str) -> str:
    client = DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    )

    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document(
            model_id="prebuilt-read",
            body=f
        )

    result = poller.result()

    # ✅ Clean full document text
    return result.content


# Example usage
if __name__ == "__main__":
    endpoint = settings.endpoint
    key = settings.key

    text = extract_text("data/pdfs/3- Chamindu Nipun.pdf", endpoint, key)
    print(text[:])  # preview first 1000 chars