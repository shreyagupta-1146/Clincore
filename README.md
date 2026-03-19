# CLINICORE Backend

> **Secure. Explainable. Always learning.**  
> A privacy-first, multi-modal medical AI agent for clinical decision support.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLINICORE BACKEND                         │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI (Python 3.10)  ←→  React Frontend (separate repo)      │
├──────────┬──────────────┬────────────┬────────────┬─────────────┤
│PostgreSQL│    Redis     │   Qdrant   │   MinIO    │  Celery     │
│(encrypted│(sessions +   │(vector DB  │(private    │(nightly     │
│ messages)│ zero-retain) │ PubMed RAG)│ image store│ PubMed sync)│
└──────────┴──────────────┴────────────┴────────────┴─────────────┘
                              ↕ AI Layer
                    ┌─────────────────────────┐
                    │  Claude API (primary)    │
                    │  Gemini API (fallback)   │
                    │  PubMed E-utilities      │
                    │  Microsoft Presidio PII  │
                    │  BioLORD-2023 embeddings │
                    └─────────────────────────┘
```

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Python 3.10
- Auth0 account (free tier works)
- Anthropic API key (Claude)

### 1. Clone and configure

```bash
git clone https://github.com/yourname/clinicore-backend
cd clinicore-backend
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start infrastructure services

```bash
docker compose up -d postgres redis qdrant minio
# Wait for services to be healthy
docker compose ps
```

### 3. Set up Python environment

```bash
python3.10 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Download spaCy model for PII detection
python -m spacy download en_core_web_lg
```

### 4. Run the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Visit:
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health/detailed

### 5. Start background workers (for knowledge updates)

```bash
# In a separate terminal:
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat --loglevel=info

# Celery monitoring UI:
http://localhost:5555
```

---

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register after Auth0 login |
| GET | `/api/v1/auth/me` | Get current user profile |
| POST | `/api/v1/folders/` | Create a folder |
| GET | `/api/v1/folders/{id}/stepup` | Open a STEP_UP folder (after MFA) |
| POST | `/api/v1/chats/` | Create a chat in a folder |
| POST | `/api/v1/chats/{id}/continue` | Create mini-folder continuation |
| **POST** | **`/api/v1/chats/{id}/messages`** | **Send message → AI response** |
| POST | `/api/v1/chats/{id}/messages/stream` | Streaming response |
| GET | `/api/v1/chats/{id}/messages` | Get all messages |
| POST | `/api/v1/shares/` | Share a folder with recipient |
| POST | `/api/v1/shares/accept` | Recipient accepts share |
| GET | `/api/v1/research/search` | Search PubMed + get TL;DRs |
| GET | `/api/v1/audit/my-activity` | User's own audit trail |

---

## Security Architecture

### Layers of Protection

```
Layer 1: TLS (HTTPS)
  └─ All traffic encrypted in transit

Layer 2: Auth0 JWT Validation
  └─ Every request validates the Bearer token against Auth0 JWKS

Layer 3: Role-Based Access Control (RBAC)
  └─ Doctor, Nurse, Specialist, Researcher roles with different permissions

Layer 4: Folder-Level Step-Up Authentication
  └─ Sensitive folders require MFA re-verification before access

Layer 5: AES-256-GCM Message Encryption
  └─ Message content encrypted at the application layer before DB storage

Layer 6: PII Redaction (Presidio)
  └─ Patient identifiers stripped before ANY text is sent to external LLMs

Layer 7: Audit Logs (Immutable)
  └─ Every access, share, and AI query is permanently logged

Layer 8: Zero-Retention Mode
  └─ Ultra-sensitive cases: messages exist only in Redis, never written to disk
```

---

## AI Pipeline (What happens when you send a message)

```
User sends message + optional image
            ↓
[1] Auth check (JWT validation + folder permission)
            ↓
[2] PII Redaction (Presidio)
    "John Smith, DOB 01/01/1980" → "[PERSON], DOB [DATE_TIME]"
            ↓
[3] Image Upload → MinIO (if image provided)
            ↓
[4] PARALLEL:
    ├─ LLM Call (Claude API):
    │   System prompt + conversation history + redacted text + image
    │   → Structured JSON response with:
    │     - reasoning_steps
    │     - differential_diagnoses
    │     - missing_information
    │     - red_flags
    │     - bias_alerts
    │     - counterfactual_insights
    │     - uncertainty_factors
    └─ RAG Pipeline:
        SciSpacy entity extraction → Qdrant semantic search
        → PubMed fallback → TL;DR generation
            ↓
[5] Responses merged (research_suggestions added to AI response)
            ↓
[6] Encryption + Storage (PostgreSQL)
    User message: encrypt(original_content)
    AI message: encrypt(ai_response_text) + ai_metadata JSON
            ↓
[7] Audit Log written
            ↓
[8] Response returned to frontend
```

---

## Database Schema

```
users
  ├── folders
  │   ├── chats (small, MAX_MESSAGES_PER_CHAT limit)
  │   │   └── messages (encrypted content_encrypted column)
  │   └── shares (recipient-verified sharing)
  │       └── share_audits (every access logged)
  └── audit_logs (immutable, 7-year retention)
```

---

## Configuration Reference

See `.env.example` for all configuration options.

Key decisions:
- `MAX_MESSAGES_PER_CHAT=20`: Keeps chats small; encourages continuation
- `AUDIT_LOG_RETENTION_DAYS=2555`: 7 years (HIPAA minimum)
- `ZERO_RETENTION_TTL_SECONDS=3600`: 1 hour for in-memory-only mode
- `MAX_CONTINUATION_DEPTH=5`: Prevents unbounded mini-folder nesting

---

## Adding Medical Knowledge Topics

To index new medical topics immediately:

```python
from app.tasks.celery_app import index_topic_now
index_topic_now.delay("rare autoimmune disease diagnosis criteria 2024")
```

---

## Tech Stack Summary

| Component | Technology | Why |
|-----------|-----------|-----|
| API Framework | FastAPI | Async, typed, auto-docs |
| Database | PostgreSQL + pgcrypto | AES-256 column encryption |
| Cache/Session | Redis | Fast, TTL support for zero-retention |
| Vector DB | Qdrant | Local, private, fast semantic search |
| File Storage | MinIO | S3-compatible, self-hosted |
| Primary LLM | Claude (Anthropic) | Best medical reasoning + multimodal |
| Fallback LLM | Gemini 1.5 Pro | Multimodal fallback |
| Embeddings | BioLORD-2023 | Medical domain sentence embeddings |
| PII Redaction | Microsoft Presidio | Production-grade NER-based redaction |
| Auth | Auth0 | OAuth2 + MFA + RBAC + Step-Up Auth |
| Background Tasks | Celery + Redis | Nightly PubMed knowledge updates |
| Research DB | PubMed E-utilities | Free, comprehensive, official |
| Monitoring | Prometheus + Flower | Metrics + Celery task monitoring |

---

## Competition Demo Script

```
1. Login as "Dr. Lee" → folder list appears
2. Click "Complex Dermatology Cases" (STEP_UP folder)
   → Triggers MFA re-auth prompt
   → Complete MFA → folder opens
3. Open a chat, type:
   "35F presenting with erythematous rash on arms, 2 weeks duration,
   associated with joint pain and low-grade fever. No recent travel."
4. Upload: [attach dermato photo]
5. Hit Send → watch streaming response appear
6. Observe the structured response:
   ✅ Reasoning steps
   ✅ Differentials (SLE, psoriatic arthritis, reactive arthritis)
   ✅ Missing info (ANA, anti-dsDNA, RF, ESR/CRP)
   ✅ Research papers with TL;DRs
   ✅ Bias alerts (if any anchoring detected)
7. Click "Share with Rheumatologist" → enter Dr. Patel's details
8. Show audit log: every step is recorded
9. Demo "Continue Chat" → creates mini-folder
```
