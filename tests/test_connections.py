"""
test_connections.py
-------------------
Run this BEFORE writing any pipeline code.
Every service must pass before you move to Stage 1.

Usage:
    python tests/test_connections.py
"""

import sys
import os

# Allow imports from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.ai.documentintelligence import DocumentIntelligenceAdministrationClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
load_dotenv()

from resume_pipeline.clients import (
    blob_service_client,
    RAW_CVS_CONTAINER,
    document_intelligence_client,
    openai_client,
    GPT4O_DEPLOYMENT,
    EMBEDDING_DEPLOYMENT,
    cosmos_container,
    search_client,
)

PASS = "  ✅ PASS"
FAIL = "  ❌ FAIL"


# ── 1. Blob Storage ────────────────────────────────────────────────────────────
def test_blob_storage():
    print("\n[1] Blob Storage")
    try:
        container = blob_service_client.get_container_client(RAW_CVS_CONTAINER)
        props = container.get_container_properties()
        print(f"{PASS} — Container '{props.name}' is accessible")
    except Exception as e:
        print(f"{FAIL} — {e}")


# ── 2. Document Intelligence ───────────────────────────────────────────────────
def test_document_intelligence():
    print("\n[2] Document Intelligence")
    try:
        # get_resource_details() is on the admin client, not the regular client
        # The regular DocumentIntelligenceClient in clients.py is still correct for processing
        admin_client = DocumentIntelligenceAdministrationClient(
            endpoint=os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["DOCUMENT_INTELLIGENCE_KEY"]),
        )
        info = admin_client.get_resource_details()
        print(f"{PASS} — Connected. Custom model limit: {info.custom_document_models.limit}")
    except Exception as e:
        print(f"{FAIL} — {e}")


# ── 3. Azure OpenAI — GPT-4o ──────────────────────────────────────────────────
def test_openai_gpt4o():
    print("\n[3] Azure OpenAI — GPT-4o")
    try:
        response = openai_client.chat.completions.create(
            model=GPT4O_DEPLOYMENT,
            messages=[{"role": "user", "content": "Reply with the single word: connected"}],
            max_tokens=5,
        )
        reply = response.choices[0].message.content.strip()
        print(f"{PASS} — Model replied: '{reply}'")
    except Exception as e:
        print(f"{FAIL} — {e}")


# ── 4. Azure OpenAI — Embeddings ──────────────────────────────────────────────
def test_openai_embeddings():
    print("\n[4] Azure OpenAI — text-embedding-3-small")
    try:
        response = openai_client.embeddings.create(
            model=EMBEDDING_DEPLOYMENT,
            input="test connection",
        )
        dims = len(response.data[0].embedding)
        print(f"{PASS} — Vector generated. Dimensions: {dims} (expected 1536)")
        if dims != 1536:
            print(f"  ⚠️  WARNING: Dimensions are {dims}, not 1536 — check deployment")
    except Exception as e:
        print(f"{FAIL} — {e}")


# ── 5. Cosmos DB ───────────────────────────────────────────────────────────────
def test_cosmos_db():
    print("\n[5] Cosmos DB")
    try:
        props = cosmos_container.read()
        print(f"{PASS} — Container '{props['id']}' accessible. Partition key: {props['partitionKey']['paths']}")
    except Exception as e:
        print(f"{FAIL} — {e}")


# ── 6. Azure AI Search ─────────────────────────────────────────────────────────
def test_ai_search():
    print("\n[6] Azure AI Search")
    try:
        # A search with empty results is still a successful connection
        results = search_client.search(search_text="*", top=1)
        count = 0
        for _ in results:
            count += 1
        print(f"{PASS} — Index accessible. Documents found: {count}")
    except Exception as e:
        print(f"{FAIL} — {e}")


# ── Run all ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  ATS Pipeline — Connection Tests")
    print("  Stage 0 Gate: All 6 must PASS")
    print("=" * 50)

    test_blob_storage()
    test_document_intelligence()
    test_openai_gpt4o()
    test_openai_embeddings()
    test_cosmos_db()
    test_ai_search()

    print("\n" + "=" * 50)
    print("  Done. Fix any FAIL before moving to Stage 1.")
    print("=" * 50)