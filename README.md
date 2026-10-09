# Hotel AI Concierge

A production-style MVP for an AI-powered hotel guest assistance system. Built with **React + TypeScript** frontend, **FastAPI + LangGraph** backend, **RAG** via Chroma + HuggingFace embeddings, and a clean Docker Compose setup.

---

## ✨ Features

- **AI Chat Interface** — Hotel-themed chat UI with typing indicators, suggested prompts, and RAG source citations
- **RAG Knowledge Base** — 50+ hotel FAQ entries indexed in Chroma with HuggingFace embeddings (runs fully offline)
- **LangGraph Orchestration** — One StateGraph with 7 specialized nodes routing to appropriate workflows
- **17 Intent Categories** — HOUSEKEEPING, MAINTENANCE, DINING, FACILITIES, TRANSPORTATION, COMPLAINT, HUMAN_ESCALATION, EMERGENCY, and more
- **Mock Hotel Tools** — 12 hotel service operations with real request IDs (HK1024, MT1024, etc.)
- **Guest Context** — Room number and name extracted from messages and persisted across the conversation
- **Staff Dashboard** — Real-time view of all open service requests, maintenance tickets, complaints, and escalations
- **Multi-LLM Support** — Mock (default), Google Gemini, Amazon Bedrock via `.env` configuration
- **PostgreSQL / SQLite** — PostgreSQL in Docker; auto-falls back to SQLite for local dev

---

## 🏗️ Architecture

```
User Message
  → FastAPI /api/chat
  → Session Service (guest context)
  → LangGraph StateGraph
      → classify_intent node
      → conditional routing
      → [rag | housekeeping | maintenance | complaint | escalation | emergency | general]
  → Response (with request ID if action taken)
  → Conversation saved to DB
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.10+ and Node.js 18+
- No API keys required (uses mock LLM by default)

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env — LLM_PROVIDER=mock works out of the box
```

### 2. Start the backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Ingest FAQ knowledge base
python scripts/ingest_faq.py

# Start the API server
uvicorn app.main:app --reload --port 8000
```

The backend will:
- Auto-create SQLite database and seed demo data
- Start at `http://localhost:8000`
- API docs available at `http://localhost:8000/docs`

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend opens at `http://localhost:5173`

---

## 🤖 LLM Configuration

Set in `.env`:

| Provider | Setting | Required Keys |
|----------|---------|---------------|
| Mock (default) | `LLM_PROVIDER=mock` | None |
| Google Gemini | `LLM_PROVIDER=gemini` | `GEMINI_API_KEY` |
| Amazon Bedrock | `LLM_PROVIDER=bedrock` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |

---

## 🐳 Docker Compose (Production)

```bash
# Start full stack (PostgreSQL + Redis + Backend + Frontend)
docker compose up -d

# Ingest FAQs into the containerized backend
docker compose --profile ingest run ingest

# View logs
docker compose logs -f backend
```

---

## 🧪 Running Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
```

---

## 🔄 Adding Your Own FAQ Data

Format each entry as JSON:

```json
{
  "category": "Housekeeping",
  "question": "Can I request extra towels?",
  "answer": "Yes, contact housekeeping at extension 3.",
  "intent": "HOUSEKEEPING",
  "entities": ["room_number", "quantity"],
  "source": "hotel_faq"
}
```

Then ingest:

```bash
python scripts/ingest_faq.py --file data/your_faqs.json
python scripts/ingest_faq.py --file data/your_faqs.json --reset  # Full re-index
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Main chat endpoint |
| `GET` | `/api/conversations/{id}` | Get conversation history |
| `GET` | `/api/service-requests` | List service requests |
| `POST` | `/api/service-requests` | Create service request |
| `PATCH` | `/api/service-requests/{id}` | Update request status |
| `GET` | `/api/maintenance` | List maintenance tickets |
| `POST` | `/api/maintenance` | Create maintenance ticket |
| `GET` | `/api/complaints` | List complaints |
| `POST` | `/api/complaints` | Create complaint |
| `GET` | `/api/escalations` | List escalations |
| `POST` | `/api/escalations` | Create escalation |
| `GET` | `/api/guest/{id}` | Get guest details |
| `GET` | `/api/dashboard/stats` | Staff dashboard stats |
| `GET` | `/api/health` | Health check |

Interactive API docs: `http://localhost:8000/docs`

---

## 🗂️ Project Structure

```
IHG/
├── frontend/                  # React + TypeScript + Tailwind
│   └── src/
│       ├── components/       # Chat UI, Dashboard, Messages
│       ├── hooks/            # useChat, useServiceRequests
│       ├── api/              # Typed API client
│       └── types/            # Shared TypeScript types
├── backend/
│   ├── app/
│   │   ├── core/             # Config, LLM factory, logging
│   │   ├── database/         # SQLAlchemy models, session, init
│   │   ├── rag/              # Embeddings, Chroma, pipeline
│   │   ├── agents/           # LangGraph graph, intent, state
│   │   ├── tools/            # Mock hotel service tools
│   │   ├── services/         # Session & conversation services
│   │   ├── api/              # FastAPI routers
│   │   └── main.py           # Application entry point
│   ├── scripts/
│   │   └── ingest_faq.py    # FAQ ingestion script
│   ├── data/
│   │   └── sample_faqs.json # 50 hotel FAQ entries
│   └── tests/
│       └── test_all.py      # Full test suite
├── docker/                    # Dockerfiles
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🔮 Next Steps (Phase 4)

- Connect to real PMS (Oracle OPERA, Amadeus)
- Connect to CRM (Salesforce)
- Add WebSocket for real-time staff notifications
- Add authentication for staff dashboard
- Extend to 1,148 FAQ entries
- Add LangSmith tracing for production monitoring

---

## 🏨 Demo Guest Data

| Guest | Room | Reservation |
|-------|------|-------------|
| John Smith | 405 | RES001 |
| Priya Sharma | 402 | RES002 |

Try: *"Send two towels to room 405"* → Creates HK request with ID

Try: *"My AC in room 405 is broken"* → Creates MT ticket with ID

Try: *"What time is breakfast?"* → RAG answer with knowledge base source
