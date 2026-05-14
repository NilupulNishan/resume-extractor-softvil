# ATS Resume Pipeline

**Document Type:** Developer Working Document  
**Phase:** Phase 1 — Pipeline Build (In Progress)  
**Last Updated:** May 2026  
**Status:** ✅ Infrastructure provisioned. ✅ Pipeline Stages 0–3 complete. 🔄 Stage 4 in progress.

---

## Team

| Role | Responsibility |
|------|---------------|
| **AI/Azure Engineer** (Nilupul) | Azure services, pipeline package, all AI logic, `resume_pipeline/` |
| **Backend Developer** (Junior) | Django API, endpoints, views — integrates pipeline as a black box |

> **Rule:** The backend developer never touches Azure SDKs directly. He calls pipeline functions only.

---

## 0. System Story

When a user uploads a resume, the file is stored in Azure Blob Storage and a secure signed URL (SAS token) is generated. The file bytes are sent to Azure Document Intelligence (`prebuilt-read`) to extract high-quality ordered text from PDF or DOCX formats. That text goes into a single GPT-4o call which does two things in one pass: it normalizes the unstructured content into a structured JSON schema (skills, roles, experience, education, etc.) and generates a concise semantic `embeddingText` optimized for meaning-based search. The `embeddingText` is passed to `text-embedding-3-small` to produce a 1536-dimension vector. The full structured JSON plus the blob reference is stored in Cosmos DB as the system of record. The vector plus lightweight display fields is written to Azure AI Search for fast recruiter queries. When a recruiter searches, AI Search returns candidate cards; clicking a candidate fetches the full profile from Cosmos DB via `cosmosDocumentId`; downloading the CV resolves the SAS URL from Blob Storage.

---

## 1. High-Level Architecture

```
Recruiter / HR Portal
        │
        ▼
┌─────────────────────┐
│   Resume Upload     │  PDF / DOCX
│   (Blob Storage)    │──────────────────────────────────┐
└─────────────────────┘                                  │
        │                                                │
        ▼                                                │
┌─────────────────────┐                                  │
│ Document            │  Raw extracted text              │
│ Intelligence        │                                  │
│ (prebuilt-read)     │                                  │
└─────────────────────┘                                  │
        │                                                │
        ▼                                                │
┌─────────────────────┐                                  │
│   Azure OpenAI      │  Two outputs in one pass:        │
│   GPT-4o            │  1. Structured JSON (normalized) │
│                     │  2. Embedding text (semantic)    │
└─────────────────────┘                                  │
        │                          │                     │
        ▼                          ▼                     │
┌───────────────┐     ┌─────────────────────┐           │
│ Azure OpenAI  │     │   Azure Cosmos DB   │           │
│ Embedding     │     │   (System of Record)│◄──────────┘
│ text-embedding│     │   Full JSON + blobUrl
│ -3-small      │     └─────────────────────┘
└───────────────┘
        │
        ▼
┌─────────────────────┐
│  Azure AI Search    │  Vector + display fields
│  (Search + Retrieve)│  Lightweight index for ATS queries
└─────────────────────┘
        │
        ▼
  Recruiter Search UI
  (semantic + vector + filter + facet)
```

---

## 2. Data Flow

| Step | Action | Service |
|------|--------|---------|
| 1 | CV uploaded (PDF/DOCX) | Blob Storage |
| 2 | Raw file stored, SAS URL generated | Blob Storage |
| 3 | File bytes sent to `prebuilt-read` | Document Intelligence |
| 4 | Clean ordered raw text returned | Document Intelligence |
| 5 | Raw text sent to GPT-4o (single prompt) | Azure OpenAI |
| 6 | GPT-4o returns: normalized JSON + `embeddingText` | Azure OpenAI |
| 7 | Full JSON + `blobUrl` stored as system of record | Cosmos DB |
| 8 | `embeddingText` sent to `text-embedding-3-small` | Azure OpenAI |
| 9 | 1536-dim vector returned | Azure OpenAI |
| 10 | Vector + display fields written to search index | Azure AI Search |
| 11 | Recruiter queries → vector + semantic + filter search | Azure AI Search |
| 12 | Recruiter opens candidate → full profile via `cosmosDocumentId` | Cosmos DB |
| 13 | Recruiter downloads CV → SAS URL resolved | Blob Storage |

---

## 3. Repository Structure

```
resume-extractor-softvil/
│
├── resume_pipeline/                  # AI/Azure Engineer owns this entire package
│   ├── __init__.py
│   ├── clients.py        ✅          # All 5 Azure SDK clients — initialized once from .env
│   ├── blob_service.py   ✅          # Stage 1: Upload CV + generate SAS URL
│   ├── extractor.py      ✅          # Stage 2: Document Intelligence → raw text
│   ├── structurer.py     ✅          # Stage 3: GPT-4o → structured JSON + embeddingText
│   ├── embedder.py       🔄          # Stage 4: text-embedding-3-small → 1536-dim vector
│   ├── writer.py         ⬜          # Stage 5: Dual-write → Cosmos DB + AI Search
│   ├── search_service.py ⬜          # Stage 8: Vector + semantic + filter query logic
│   └── pipeline.py       ⬜          # Stage 6: Orchestrator — single entry point
│
├── tests/
│   ├── fixtures/
│   │   ├── nilupul-cv-26.pdf         # Sample resume used for all stage tests
│   │   └── last_structured_output.json  # Auto-generated by test_structurer.py
│   ├── test_connections.py  ✅       # Stage 0: Verify all 5 Azure clients connect
│   ├── test_blob.py         ✅       # Stage 1: Upload + SAS URL generation
│   ├── test_extractor.py    ✅       # Stage 2: Document Intelligence extraction
│   ├── test_structurer.py   ✅       # Stage 3: GPT-4o structuring + schema validation
│   ├── test_embedder.py     🔄       # Stage 4: Embedding vector generation
│   ├── test_writer.py       ⬜       # Stage 5: Cosmos DB + AI Search write
│   └── test_pipeline.py     ⬜       # Stage 6: Full end-to-end smoke test
│
├── .env                              # All Azure credentials — NEVER commit to Git
├── .gitignore                        # Must include .env and tests/fixtures/*.pdf
└── requirements.txt                  # All Python dependencies
```

---

## 4. Pipeline Build Progress

| Stage | File | What It Does | Model/Service | Status |
|-------|------|-------------|---------------|--------|
| 0 | `clients.py` | Initialize all 5 Azure SDK clients | All services | ✅ Done |
| 1 | `blob_service.py` | Upload CV → Blob Storage, generate SAS URL | Blob Storage | ✅ Done |
| 2 | `extractor.py` | File bytes → clean ordered raw text | Document Intelligence `prebuilt-read` | ✅ Done |
| 3 | `structurer.py` | Raw text → structured JSON + `embeddingText` | GPT-4o (single pass) | ✅ Done |
| 4 | `embedder.py` | `embeddingText` → 1536-dim vector | `text-embedding-3-small` | 🔄 Next |
| 5 | `writer.py` | Dual-write to Cosmos DB + AI Search | Cosmos DB + AI Search | ⬜ Pending |
| 6 | `pipeline.py` | Orchestrate stages 1–5, manage `processingStatus` | — | ⬜ Pending |
| 7 | Django integration | `POST /api/resumes/upload/` calls `pipeline.py` | Django (Junior) | ⬜ Pending |
| 8 | `search_service.py` | Vector + semantic + filter query against `resumes-index` | AI Search | ⬜ Pending |

### Stage 3 Validation Results (May 2026)

Tested against a real resume (`nilupul-cv-26.pdf`, 169 KB, 3,882 characters extracted):

| Check | Result |
|-------|--------|
| All 10 schema keys present | ✅ |
| `personalInfo` — name, email, phone, LinkedIn | ✅ Nilupul Nishan, correctly extracted |
| `workExperience` — 2 roles | ✅ Latest: Associate AI/ML Engineer at Softvil Technologies |
| `skills` — 16 raw / 10 normalized | ✅ Python, Azure, AWS, LangGraph, LlamaIndex, RAG systems |
| `totalExperienceYears` | ✅ 1.2 years |
| `certifications` | ✅ 4 found |
| `projects` | ✅ 4 found |
| `education` | ✅ BSc ICT — University of Sri Jayewardenepura |
| `embeddingText` | ✅ 174 words, 8 sentences, semantic quality confirmed |
| Invalid file format raises `ValueError` | ✅ |

---

## 5. How to Set Up (New Developer)

### Prerequisites
- Python 3.11+
- Access to the `.env` file (get from AI/Azure Engineer — never stored in Git)
- Git access to this repository

### Install

```bash
git clone <repo-url>
cd resume-extractor-softvil
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Verify connections before anything else

```bash
python tests/test_connections.py
```

All 6 checks must pass. If any fail, check your `.env` values.

### Run all stage tests in order

```bash
python tests/test_connections.py    # Stage 0 — Azure clients
python tests/test_blob.py           # Stage 1 — Blob + SAS
python tests/test_extractor.py      # Stage 2 — Document Intelligence
python tests/test_structurer.py     # Stage 3 — GPT-4o structuring
```

> Stage 2–3 tests require a real resume PDF in `tests/fixtures/`. Any PDF works.

---

## 6. Python Dependencies

```
azure-storage-blob==12.24.1
azure-ai-documentintelligence==1.0.0
openai==1.78.0
azure-cosmos==4.9.0
azure-search-documents==11.6.0
python-dotenv==1.1.0
```

---

## 7. Environment Variables

```env
# Blob Storage
AZURE_STORAGE_CONNECTION_STRING=
AZURE_STORAGE_ACCOUNT_NAME=resumestorage26
AZURE_STORAGE_RAW_CONTAINER=raw-cvs
AZURE_STORAGE_JSON_CONTAINER=structured-json

# Document Intelligence
DOCUMENT_INTELLIGENCE_ENDPOINT=
DOCUMENT_INTELLIGENCE_KEY=

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_KEY=
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Cosmos DB
COSMOS_ENDPOINT=
COSMOS_KEY=
COSMOS_CONNECTION_STRING=
COSMOS_DATABASE=ats-db
COSMOS_CONTAINER=resumes

# Azure AI Search
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_ADMIN_KEY=
AZURE_SEARCH_INDEX=resumes-index
```

**Where to find each key:**

| Service | What to Copy | Location in Azure Portal |
|---------|-------------|--------------------------|
| Blob Storage | Connection String | Storage Account → Security + networking → Access Keys |
| Document Intelligence | Endpoint + Key 1 | Resource → Resource Management → Keys and Endpoint |
| Azure OpenAI | Endpoint + Key 1 | Resource → Resource Management → Keys and Endpoint |
| Cosmos DB | URI + Primary Key | Resource → Settings → Keys |
| Azure AI Search | Endpoint URL + Primary Admin Key | Resource → Settings → Keys |

---

## 8. Provisioned Azure Services

All five services under Resource Group: **Resume-Scoring-Project-RG** (East US)

| Service | Resource Name | Tier | Status |
|---------|--------------|------|--------|
| Blob Storage | `resumestorage26` | LRS | ✅ Live — containers `raw-cvs`, `structured-json` |
| Document Intelligence | `resume-extractor-v1` | Standard S0 | ✅ Live — `prebuilt-read` model |
| Azure OpenAI | `ai-resume-openai` | — | ✅ Live — `gpt-4o` + `text-embedding-3-small` deployed |
| Cosmos DB | `ats-cosmos-prod` | Serverless | ✅ Live — `ats-db` / `resumes` container, `/candidateId` partition |
| Azure AI Search | `ats-search-test` | **Free** ⚠️ | ✅ Live — `resumes-index` with HNSW vector config + semantic config |

> ⚠️ AI Search Free tier must be upgraded to Standard S1 before production. Semantic ranker is inactive on Free tier.

### AI Search Index Configuration

| Field | Type | Purpose |
|-------|------|---------|
| `id` | Edm.String | Key field |
| `candidateId` | Edm.String | FK → Cosmos DB |
| `cosmosDocumentId` | Edm.String | Direct Cosmos lookup |
| `name` | Edm.String | Recruiter card display |
| `email` | Edm.String | Dedup + filter |
| `summary` | Edm.String | Semantic search source |
| `skills` | Collection(Edm.String) | Facet by skill |
| `currentRole` | Edm.String | Facet by role |
| `totalExperienceYears` | Edm.Double | Range facet |
| `uploadedAt` | Edm.DateTimeOffset | Recency sort |
| `blobUrl` | Edm.String | Signed URL — retrieve only |
| `embedding` | Collection(Edm.Single) | 1536-dim HNSW vector |

**Vector config:** HNSW · cosine similarity · 1536 dims · m=4 · efConstruction=400 · efSearch=500  
**Semantic config:** `ats-semantic-config` · title=`currentRole` · content=`summary`,`skills`

---

## 9. Security Status

| Item | Status | Action Required |
|------|--------|----------------|
| API Keys in `.env` | ✅ Configured | Never commit `.env` to Git |
| SAS Tokens (CV downloads) | ✅ Implemented in `blob_service.py` | 1-hour expiry — extend for production |
| Managed Identity | ❌ Not set up | Phase 2 — replaces API keys |
| Azure Key Vault | ❌ Not provisioned | Phase 2 — centralise secret management |
| Network restrictions | ❌ Public endpoints | Phase 2 — lock to VNet |
| Blob Storage redundancy | LRS | Upgrade to GRS in production |

---

## 10. What Remains (Ordered by Priority)

| Task | Owner | Priority |
|------|-------|----------|
| `embedder.py` — Stage 4 | 🔵 AI Engineer | 🔴 Current |
| `writer.py` — Stage 5 | 🔵 AI Engineer | 🔴 Next |
| `pipeline.py` — Stage 6 orchestrator | 🔵 AI Engineer | 🔴 Next |
| End-to-end smoke test (real resume → both stores) | 🔵 AI Engineer | 🔴 Gate before Django |
| Django `POST /api/resumes/upload/` endpoint | 🟢 Junior | 🟡 After pipeline complete |
| Django `GET /api/resumes/{candidateId}/` endpoint | 🟢 Junior | 🟡 After upload |
| `search_service.py` + Django search endpoint | 🔵 + 🟢 | 🟡 After ingestion validated |
| Upgrade AI Search Free → Standard S1 | 🔵 AI Engineer | 🟡 Before >500 resumes |
| Managed Identity + Key Vault | 🔵 AI Engineer | 🟠 Phase 2 |
| VNet / Private Endpoints | 🔵 AI Engineer | 🟠 Phase 2 |
| Azure Monitor alerts | 🔵 AI Engineer | 🟠 Phase 2 |

---

## 11. Production Upgrade Checklist

When moving to production scale (5,000+ resumes):

- [ ] Upgrade Azure AI Search: delete Free → recreate as **Standard S1** → reindex from Cosmos DB
- [ ] Add 2 replicas to AI Search for SLA
- [ ] Switch Cosmos DB to **Provisioned Throughput**
- [ ] Upgrade Blob Storage to **GRS**
- [ ] Replace API key auth with **Managed Identity**
- [ ] Provision **Azure Key Vault**
- [ ] Lock services to **selected network / VNet**
- [ ] Enable **Cosmos DB continuous backup**
- [ ] Set up **Azure Monitor** alerts on Search latency + Cosmos RU consumption
- [ ] Extend SAS token to user-delegation SAS (more secure than account-key SAS)

---

## 12. Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| No Azure Functions (Phase 1) | Direct Python module | Simpler debugging, faster iteration, same code can be wrapped later |
| Pipeline as standalone package | `resume_pipeline/` | Django calls it as a black box — decoupled, testable, portable |
| Single GPT-4o pass | ✅ Yes | Structuring + embedding text in one call — cost and latency efficient |
| `response_format: json_object` | Mandatory | Prevents non-JSON GPT-4o output — pipeline cannot recover from bad JSON |
| `temperature: 0.1` on GPT-4o | Low | Consistent extraction across different resume formats |
| Cosmos DB API | NoSQL (Document) | Flexible JSON schema, best SDK support |
| Cosmos DB capacity | Serverless | Bursty event-driven uploads — pay per use |
| Partition key `/candidateId` | Even distribution | All queries scoped per candidate |
| Embedding model | `text-embedding-3-small` | Best cost/quality ratio — 1536 dims sufficient |
| Single embedding per resume | Phase 1 strategy | Efficient at scale — chunk embeddings deferred to Phase 2 |
| Blob URL in both stores | ✅ Yes | AI Search for card display; Cosmos for audit + reprocessing |
| AI Search tier | Free → S1 | Validate cheaply — S1 required for semantic ranker + SLA |

---

*Infrastructure: May 2026 — Nilupul Nishan (AI/Azure Engineer)*  
*Pipeline build started: May 2026 — Stages 0–3 complete*