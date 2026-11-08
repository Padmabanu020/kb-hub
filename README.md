# Knowledge Base Hub

Upload a CSV/XLSX of URLs → harvest the pages → store raw content in **MSSQL** → embed chunks into a **FAISS** vector index → ask natural-language questions about people (executives, roles, bios) and get structured answers from a **local LLM** (Ollama) or any free OpenAI-compatible API.

**Stack:** Django 4/5 + Django REST Framework · React (Vite) · SQL Server (`mssql-django`) · FAISS · sentence-transformers (`all-MiniLM-L6-v2`) · Ollama / Groq / OpenRouter.

## Architecture

```
React UI ──► POST /api/upload/ ─► parse CSV/XLSX ─► HarvestedURL rows (MSSQL)
                                          │
                       background thread: ThreadPool scraper (requests + BeautifulSoup)
                                          │  raw HTML, clean text, metadata, JSON-LD persons, HTTP status
                                          ▼
                              MSSQL (UploadBatch, HarvestedURL, Chunk)
                                          │  heading-aware chunking (title | section + text)
                                          ▼
                       sentence-transformers embeddings ─► FAISS IndexIDMap2 (id = Chunk.pk)
                                          ▲
React UI ──► POST /api/search/ ─► embed query ─► top-k chunks (+ role-keyword boost for person queries)
                                          └─► LLM (JSON: answer + people[name, role, bio, source]) ─► UI cards
GET /api/urls/  ─► URL, HTTP status, raw HTML, metadata (DRF, paginated)
```

Retrieval is **chunk-based**: every chunk carries its page title and section heading, and JSON-LD `Person` records become dedicated chunks. If no LLM is reachable the API falls back to a regex extractor, so search never hard-fails.

## Prerequisites
- Python 3.10+, Node 18+
- SQL Server (local, Docker, or remote) + **Microsoft ODBC Driver 18 for SQL Server**
  (Windows: download from Microsoft · Ubuntu: `msodbcsql18` · macOS: `brew install msodbcsql18`)
- Optional LLM: [Ollama](https://ollama.com) → `ollama pull llama3.2`

## Setup

### 1. Database
```bash
docker compose up -d            # or use your own SQL Server instance
```

### 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # edit MSSQL_* values
python manage.py createdb_mssql                       # creates the database if missing
python manage.py migrate
python manage.py runserver                            # http://localhost:8000
```
No SQL Server handy? Set `DB_ENGINE=sqlite` in `.env` for a quick try-out.

### 3. Frontend
```bash
cd frontend
npm install
npm run dev                                           # http://localhost:5173 (proxies /api → :8000)
```

### 4. LLM (optional, recommended)
```bash
ollama serve & ollama pull llama3.2
```
Free hosted alternative (Groq, OpenRouter, …): set `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` in `.env`.

## Usage
1. **Upload CSV** tab → drop `sample_urls.csv` (or your own; a `url`/`link`/`website` column is auto-detected, otherwise every cell is scanned; `.xlsx` hyperlinks are supported).
2. Watch progress: scraping → indexing → done.
3. **Search** tab → e.g. *"Who is the CEO?"*, *"List the leadership team and roles"*.
4. **Harvested URLs** tab → inspect status, metadata and raw HTML, or open `GET /api/urls/`.

## REST API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/urls/` | Harvested URLs: `url`, `http_status`, `raw_content`, `metadata`, `title`, `error`, … Filters: `?batch=`, `?http_status=`, `?indexed=true`, `?q=`, `?light=1` (omit raw HTML), `?page=` |
| `GET` | `/api/urls/<id>/` | Single record |
| `POST` | `/api/upload/` | multipart `file` (.csv/.xlsx) → starts harvesting, returns batch |
| `GET` | `/api/batches/`, `/api/batches/<id>/` | Upload progress |
| `POST` | `/api/search/` | `{"query": "...", "top_k": 8, "use_llm": true}` → `answer`, `people[]`, `passages[]` |
| `POST` | `/api/reindex/` | Rebuild FAISS from the SQL data |
| `GET` | `/api/stats/` | Counts + model info |

Example:
```bash
curl "http://localhost:8000/api/urls/?light=1&http_status=200"
curl -X POST localhost:8000/api/search/ -H "Content-Type: application/json" -d '{"query":"Who is the CEO?"}'
```

## Tests
```bash
cd backend && DB_ENGINE=sqlite python manage.py test hub
```

## Notes & limits
- Pages rendered purely by JavaScript (SPAs) return little HTML with `requests`; for those swap `fetch_url` in `hub/scraper.py` for Playwright.
- Some sites block bots (403). These are stored with their status code and error, not indexed.
- Scraping runs in a background thread (fine for an assignment); use Celery/RQ for production.
- The FAISS index is persisted in `backend/vector_store/`. Use *Reindex* (`POST /api/reindex/`) after changing the embedding model.
- To use Milvus instead, implement the same 4 methods (`add/remove/search/reset`) in `hub/vectorstore.py`.
