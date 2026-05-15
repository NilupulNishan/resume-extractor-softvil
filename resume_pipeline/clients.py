"""
clients.py
----------
Initializes all 5 Azure SDK clients once, from environment variables.
Every other module imports from here — never re-initialize clients elsewhere.
"""

import os
from dotenv import load_dotenv

from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from azure.cosmos import CosmosClient
from azure.search.documents import SearchClient

load_dotenv()


# ── 1. Blob Storage ────────────────────────────────────────────────────────────
blob_service_client = BlobServiceClient.from_connection_string(
    os.environ["AZURE_STORAGE_CONNECTION_STRING"]
)

RAW_CVS_CONTAINER     = os.environ["AZURE_STORAGE_RAW_CONTAINER"]      # raw-cvs
STRUCTURED_CONTAINER  = os.environ["AZURE_STORAGE_JSON_CONTAINER"]     # structured-json


# ── 2. Document Intelligence ───────────────────────────────────────────────────
document_intelligence_client = DocumentIntelligenceClient(
    endpoint=os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["DOCUMENT_INTELLIGENCE_KEY"]),
)


# ── 3. Azure OpenAI (GPT-4o + Embeddings share the same client) ───────────────
openai_client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_version="2024-08-01-preview",
)

GPT4O_DEPLOYMENT       = os.environ["AZURE_OPENAI_GPT4O_DEPLOYMENT"]        # gpt-4o
EMBEDDING_DEPLOYMENT   = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]    # text-embedding-3-small
EMBEDDING_DIMENSIONS   = int(os.environ["AZURE_OPENAI_EMBEDDING_DIMENSIONS"])  # Must match the `dimensions` in the AI Search HNSW vector config (resumes-index)


# ── 4. Cosmos DB ───────────────────────────────────────────────────────────────
cosmos_client    = CosmosClient(
    url=os.environ["COSMOS_ENDPOINT"],
    credential=os.environ["COSMOS_KEY"],
)
cosmos_database  = cosmos_client.get_database_client(os.environ["COSMOS_DATABASE"])
cosmos_container = cosmos_database.get_container_client(os.environ["COSMOS_CONTAINER"])


# ── 5. Azure AI Search ─────────────────────────────────────────────────────────
search_client = SearchClient(
    endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
    index_name=os.environ["AZURE_SEARCH_INDEX"],
    credential=AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"]),
)