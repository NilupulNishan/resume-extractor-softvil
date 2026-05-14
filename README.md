# ATS Resume Pipeline — Infrastructure Handoff Report

**Document Type:** Developer Handoff — Infrastructure Setup  
**Phase:** Phase 1 — Build & Validate Pipeline  
**Prepared:** May 2026  
**Status:** ✅ All infrastructure provisioned. Application layer not yet started.

## 0. Story

When a user uploads a resume, the file is first processed using Azure Document Intelligence (prebuilt-read) to extract high-quality raw text from formats like PDF or DOCX. That text is then sent to a single GPT-4o call, which performs two tasks in one pass: it transforms the unstructured content into a normalized, structured JSON schema (with standardized skills, roles, and experience fields) and generates a concise, semantic "embedding text" optimized for meaning-based search rather than raw wording. This embedding text is passed to a modern embedding model (`text-embedding-3-small`) to produce a vector representation capturing the candidate's professional profile. The vector, along with lightweight display fields such as name, key skills, and summary, is stored in Azure AI Search to enable fast, low-latency retrieval for ATS queries. At the same time, the complete structured JSON is stored in Azure Cosmos DB as the system of record, and importantly, this document also includes a secure reference to the original CV file — such as a blob storage URL or document link — so that recruiters can download or view the raw resume when needed. This link is a controlled-access signed URL (SAS token) rather than a public path to ensure security. For embedding strategy, the recommended approach is to begin with a single high-quality semantic summary per resume for efficiency and scalability, and only introduce section-based chunk embeddings (skills, experience, projects) if more granular matching or explainability becomes necessary. This architecture ensures fast search (~100–300 ms), strong semantic matching quality, and a clean separation between search optimization and full data storage while maintaining traceability back to the original uploaded CV.

---

## 1. System Overview

This document describes the Azure infrastructure provisioned for an AI-powered Applicant Tracking System (ATS) resume ingestion and search pipeline. The system processes uploaded resumes (PDF/DOCX), extracts and normalizes candidate data using AI, generates semantic vector embeddings, and stores them for fast recruiter search and retrieval.

### High-Level Architecture

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

## 2. Data Flow (Step by Step)

| Step | Action | Service Used |
|------|--------|--------------|
| 1 | Recruiter uploads CV (PDF/DOCX) | Blob Storage |
| 2 | Raw file stored with controlled access (signed URL) | Blob Storage |
| 3 | File sent to Document Intelligence `prebuilt-read` model | Document Intelligence |
| 4 | High-quality raw text extracted | Document Intelligence |
| 5 | Raw text sent to GPT-4o in a single prompt | Azure OpenAI |
| 6 | GPT-4o outputs: normalized structured JSON + semantic embedding text | Azure OpenAI |
| 7 | Full structured JSON + blobUrl stored as system of record | Cosmos DB |
| 8 | Embedding text sent to `text-embedding-3-small` | Azure OpenAI |
| 9 | 1536-dimension vector produced | Azure OpenAI |
| 10 | Vector + lightweight display fields written to search index | Azure AI Search |
| 11 | Recruiter queries ATS → vector + semantic + filter search | Azure AI Search |
| 12 | Recruiter clicks candidate → full profile fetched via `cosmosDocumentId` | Cosmos DB |
| 13 | Recruiter downloads CV → signed URL resolved | Blob Storage |

---

## 3. Provisioned Azure Services

### Resource Group
All five services are deployed under a **single shared Resource Group**.  
*Resource Group name — Resume-Scoring-Project-RG*

---

### 3.1 Azure Blob Storage

| Property | Value |
|----------|-------|
| **Resource Name** | `resumestorage26` |
| **Region** | East US |
| **Redundancy** | Locally Redundant Storage (LRS) |
| **Purpose** | Stores raw uploaded CVs + structured JSON outputs |
| **Access Pattern** | Controlled access via signed URLs (SAS tokens) — not public |
| **Upgrade Note** | Upgrade to GRS when moving to production for disaster recovery |

**Containers — ✅ Created:**

| Container Name | Access Level | Contents |
|----------------|-------------|----------|
| `raw-cvs` | Private | Original uploaded PDF/DOCX files |
| `structured-json` | Private | GPT-4o normalized JSON output per candidate |

---

### 3.2 Azure Document Intelligence

| Property | Value |
|----------|-------|
| **Resource Name** | `resume-extractor-v1` |
| **Region** | East US |
| **Tier** | Standard S0 |
| **Model Used** | `prebuilt-read` |
| **Purpose** | Extract high-quality raw text from PDF and DOCX resumes |
| **Input** | CV file from Blob Storage |
| **Output** | Clean raw text passed to GPT-4o |

---

### 3.3 Azure OpenAI

| Property | Value |
|----------|-------|
| **Resource Name** | `ai-resume-openai` |
| **Region** | East US |
| **Purpose** | Structured extraction + semantic embedding generation |

**Deployed Models:**

| Model | Deployment Name | Role |
|-------|----------------|------|
| `gpt-4o` | `gpt-4o` | Resume structuring + embedding text generation |
| `text-embedding-3-small` | `text-embedding-3-small` | 1536-dim vector embedding from semantic summary |

**GPT-4o Single-Pass Prompt Strategy:**
- Input: raw text from Document Intelligence
- Output 1: Normalized structured JSON (skills, roles, experience, education, etc.)
- Output 2: Concise semantic "embedding text" optimized for meaning-based search

**Embedding Strategy:**
- Phase 1: Single embedding per resume (full semantic summary) — efficient and scalable
- Phase 2 (future): Section-based chunk embeddings (skills, experience, projects) for granular matching

---

### 3.4 Azure Cosmos DB

| Property | Value |
|----------|-------|
| **Resource Name** | `ats-cosmos-prod` |
| **Region** | East US |
| **API** | NoSQL (Document) |
| **Capacity Mode** | Serverless |
| **Free Tier Discount** | Opted Out |
| **Purpose** | System of record — full normalized candidate JSON + blob reference |
| **Upgrade Path** | Migrate to Provisioned Throughput (now GA, no downtime) when load stabilizes |

**Database & Container — ✅ Created:**

| Setting | Value |
|---------|-------|
| **Database Name** | `ats-db` |
| **Container Name** | `resumes` |
| **Partition Key** | `/candidateId` |
| **Unique Key** | `/email` ✅ Enforced at database level — prevents duplicate candidates |

> **Note:** Cosmos DB is schemaless. The document schema below defines what the application layer will write — no further portal configuration is needed.

**Cosmos DB Document Schema (Fields Stored):**

| Field | Description |
|-------|-------------|
| `candidateId` | Partition key — shared identity across all services |
| `personalInfo` | Full name, email, phone, location, LinkedIn |
| `workExperience[]` | Company, title, dates, responsibilities, achievements |
| `education[]` | Degree, institution, dates |
| `skills` | Raw + normalized skill list |
| `certifications[]` | Name, issuer, date |
| `projects[]` | Title, description, tech stack |
| `languages[]` | Spoken/written languages |
| `rawExtractedText` | Original Document Intelligence output |
| `structuredJson` | Full GPT-4o normalized output |
| `embeddingText` | Semantic summary sent to embedding model (audit trail) |
| `blobUrl` | Signed URL reference to original CV file |
| `blobJsonUrl` | Reference to structured JSON file in Blob Storage |
| `uploadedAt` | Upload timestamp |
| `lastUpdatedAt` | Last modified timestamp |
| `processingStatus` | `pending` / `completed` / `failed` |

---

### 3.5 Azure AI Search

| Property | Value |
|----------|-------|
| **Resource Name** | `ats-search-test` |
| **Region** | East US |
| **Tier** | Free *(Phase 1 only — must upgrade to Standard S1 before production)* |
| **Index Name** | `resumes-index` |
| **Purpose** | Vector search + semantic ranking + faceted filtering for ATS queries |

**⚠️ Free Tier Limitations (Known — Upgrade Required for Production):**

| Limitation | Impact |
|-----------|--------|
| 50MB storage cap | Will be hit before 5,000 resumes with vectors |
| No semantic ranker execution | Semantic config saved but inactive until S1 |
| No SLA | Not acceptable for production |
| No scaling (partitions/replicas) | Fixed shared resources |
| **Upgrade path** | Delete Free service → recreate as S1 → reindex from Cosmos DB |

**Index Schema (`resumes-index`) — ✅ Created:**

> Index was created via JSON definition (REST API through portal) to correctly configure the vector field and HNSW profile in a single operation.

| Field | Type | Retrievable | Searchable | Filterable | Sortable | Facetable | Notes |
|-------|------|-------------|------------|------------|----------|-----------|-------|
| `id` | Edm.String | ✅ | ❌ | ❌ | ❌ | ❌ | Key field |
| `candidateId` | Edm.String | ✅ | ❌ | ✅ | ❌ | ❌ | FK → Cosmos DB |
| `cosmosDocumentId` | Edm.String | ✅ | ❌ | ✅ | ❌ | ❌ | Direct Cosmos DB lookup |
| `name` | Edm.String | ✅ | ✅ | ✅ | ✅ | ❌ | Recruiter card display |
| `email` | Edm.String | ✅ | ❌ | ✅ | ❌ | ❌ | Dedup + filter |
| `summary` | Edm.String | ✅ | ✅ | ❌ | ❌ | ❌ | Semantic search source |
| `skills` | Collection(Edm.String) | ✅ | ✅ | ✅ | ❌ | ✅ | Facet by skill |
| `currentRole` | Edm.String | ✅ | ✅ | ✅ | ✅ | ✅ | Facet by role |
| `totalExperienceYears` | Edm.Double | ✅ | ❌ | ✅ | ✅ | ✅ | Range facet |
| `uploadedAt` | Edm.DateTimeOffset | ✅ | ❌ | ✅ | ✅ | ✅ | Recency sort + facet |
| `blobUrl` | Edm.String | ✅ | ❌ | ❌ | ❌ | ❌ | Signed URL — retrieve only |
| `embedding` | Collection(Edm.Single) | ❌ | ✅ | ❌ | ❌ | ❌ | 1536-dim vector field |

**Vector Search Configuration — ✅ Deployed:**

| Setting | Value |
|---------|-------|
| Algorithm | HNSW |
| Algorithm Name | `ats-hnsw-algorithm` |
| Profile Name | `ats-vector-profile` |
| Dimensions | `1536` (matches `text-embedding-3-small`) |
| Similarity Metric | `cosine` |
| m | `4` |
| efConstruction | `400` |
| efSearch | `500` |

**Semantic Configuration — ✅ Deployed:**

| Setting | Value |
|---------|-------|
| Config Name | `ats-semantic-config` |
| Title Field | `currentRole` |
| Content Fields | `summary`, `skills` |
| Keywords Field | `name` |
| Status | Saved — inactive on Free tier, activates automatically on S1 |

---

## 4. Authentication & Security

| Item | Current Status | Recommended Action |
|------|---------------|-------------------|
| API Keys (all services) | ✅ Collected into `.env` file | Never commit `.env` to Git |
| Managed Identity | ❌ Not set up | Implement for production — replaces API keys |
| Blob SAS Tokens | ❌ Not implemented | Required before any CV URL is exposed to frontend |
| Key Vault | ❌ Not provisioned | Add in Phase 2 to centralize secret management |
| Network restrictions | ❌ Public endpoints | Lock down to selected networks in Phase 2 |

**`.env` File Structure (template — fill with real values):**

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

**Where to find each key in the portal:**

| Service | What to Copy | Location in Portal |
|---------|-------------|-------------------|
| Blob Storage | Connection String | Storage Account → Security + networking → Access Keys |
| Document Intelligence | Endpoint + Key 1 | Resource → Resource Management → Keys and Endpoint |
| Azure OpenAI | Endpoint + Key 1 | Resource → Resource Management → Keys and Endpoint |
| Cosmos DB | URI + Primary Key + Primary Connection String | Resource → Settings → Keys |
| Azure AI Search | Endpoint URL + Primary Admin Key | Resource → Settings → Keys |

---

## 5. What Is NOT Done Yet (Next Developer Picks Up Here)

| Task | Priority |
|------|----------|
| Implement SAS token generation for CV downloads | 🔴 Before frontend |
| Build ingestion pipeline (Blob → Doc Intelligence → GPT-4o → Embedding → Cosmos + Search) | 🔴 Core work |
| Build ATS query/retrieval layer | 🟡 After ingestion |
| Build recruiter frontend (search UI + candidate cards + facets) | 🟡 After query layer |
| Upgrade AI Search from Free → Standard S1 | 🟡 Before >500 resumes |
| Set up Managed Identity across services | 🟠 Phase 2 |
| Provision Azure Key Vault | 🟠 Phase 2 |
| Enable network restrictions / Private Endpoints | 🟠 Phase 2 |
| Upgrade Blob Storage LRS → GRS | 🟠 Phase 2 |
| Add second AI Search replica for SLA | 🟠 Phase 2 |

---

## 6. Phase Upgrade Checklist (Free → Production)

When moving from Phase 1 to production scale (5,000+ resumes):

- [ ] Upgrade Azure AI Search: delete Free service → recreate as **Standard S1** → reindex from Cosmos DB
- [ ] Add **2 replicas** to AI Search for SLA
- [ ] Switch Cosmos DB to **Provisioned Throughput** if query patterns stabilize
- [ ] Upgrade Blob Storage to **GRS** redundancy
- [ ] Replace API key auth with **Managed Identity**
- [ ] Provision **Azure Key Vault** for secret management
- [ ] Lock all services to **selected network / VNet** access
- [ ] Enable **Cosmos DB backup** (continuous policy)
- [ ] Set up **Azure Monitor** alerts on AI Search latency + Cosmos DB RU consumption

---

## 7. Design Decisions & Rationale

| Decision | Choice | Reason |
|----------|--------|--------|
| Cosmos DB API | NoSQL (Document) | Flexible JSON schema, best SDK support, lowest overhead |
| Cosmos DB capacity | Serverless | Resume uploads are event-driven and bursty — pay per use |
| Cosmos DB partition key | `/candidateId` | Even distribution, all queries scoped per candidate |
| Embedding model | `text-embedding-3-small` | Best cost/quality ratio; 1536 dims sufficient for resume matching |
| Embedding strategy | Single summary embedding per resume | Efficient at scale; chunk embeddings deferred to Phase 2 |
| AI Search tier | Free (Phase 1) → S1 (production) | Validate pipeline cheaply; S1 required for semantic ranker + SLA |
| Search + Cosmos DB (both) | Keep both | Search = retrieval layer; Cosmos = source of truth. Industry standard. |
| Blob URL in both stores | ✅ Yes | AI Search for quick card display; Cosmos DB for audit + reprocessing |
| Single GPT-4o pass | ✅ Yes | Structuring + embedding text in one call — cost and latency efficient |
| AI Search index creation | JSON definition via portal | Required to configure vector field + HNSW profile correctly in one pass |

---

*Infrastructure setup completed May 2026. All five services provisioned and configured via Azure Portal. Application layer is the next phase.*