# Deal Copilot

AI-assisted presale and tender decision system.

**Core principle:** AI reads and structures documents; deterministic code calculates labor, cost, margin and BID/NO BID.

## MVP scope implemented in `feat/mvp-0-3`

### MVP-0 — documents
- FastAPI + SQLite + SQLAlchemy.
- Upload PDF/DOCX/XLSX.
- Parsing layer adapted from the proven Ask-Learn mechanics.
- Original vs parsed document review UI.
- Model Gateway with MiMo provider and mock fallback.
- Structured extraction + human confirmation.
- Full pipeline log with inputs/outputs/warnings.

### MVP-1 — labor
- Demo productivity reference.
- Labor-hours, FTE and physical staff calculation.

### MVP-2 — economics
- Revenue, direct/full cost, profit and margin.
- Break-even and target-price calculation.
- Price sensitivity scenarios.

### MVP-3 — decision
- Deterministic BID / BID WITH CONDITIONS / NO BID.
- Conditions are returned separately from the decision.

## Stack

- Frontend: Next.js + React + TypeScript
- Backend: FastAPI + Python
- Database: SQLite + SQLAlchemy
- LLM gateway: provider abstraction; first provider is Xiaomi MiMo
- Default model: `mimo-v2.6-flash`
- MiMo OpenAI-compatible base URL: `https://api.xiaomimimo.com/v1`

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate
pip install -e .[dev]
copy .env.example .env
# Set MIMO_API_KEY and DEMO_MODE=false for real MiMo calls.
uvicorn app.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm ci
copy .env.example .env.local
npm run dev
```

Open http://localhost:3000

Set the API URL in `frontend/.env.local` with `NEXT_PUBLIC_API_URL`.

Calculation defaults, labor assumptions, demo reference values, upload limits,
accepted formats, prompt version, locale and currency are read from backend
settings. `backend/.env.example` lists their environment variable names and
demo defaults. In demo mode, extraction returns no invented fields; enter and
confirm the area manually before running a calculation. Uploaded files are
limited by the configured per-file, total-size and file-count settings.

## Secret handling

Never commit API keys. `.env` is ignored. Only placeholders belong in `.env.example`.

## Architecture boundary

The Model Gateway isolates business code from a specific LLM provider. MiMo is the first provider, not a hard dependency of extraction/business logic.

The document review approach is intentionally based on the Ask-Learn UX: source document on the left, parsed/structured representation on the right, with traceability at every later step.
