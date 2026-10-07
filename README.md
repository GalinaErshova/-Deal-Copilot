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

# Локальная MiMo для теста

Для локальной проверки можно использовать community-конверсию Xiaomi MiMo-7B-RL
в GGUF Q4_K_M. Оригинальный API-ключ MiMo в `backend/.env` менять не нужно:
локальный режим обращается к `127.0.0.1` и использует отдельный локальный
провайдер.

1. Скачайте CPU-сборку `llama.cpp` из [официальных релизов](https://github.com/ggml-org/llama.cpp/releases)
   и поместите `llama-server.exe` и DLL в `./.local-model/runtime/`.
2. Скачайте [MiMo-7B-RL-Q4_K_M.gguf](https://huggingface.co/jedisct1/MiMo-7B-RL-GGUF)
   в `./.local-model/` (файл около 4,68 ГБ).
3. Запустите сервер: `./scripts/start-local-mimo.ps1`.
4. В отдельном окне PowerShell задайте параметры только для текущего процесса и
   запустите backend:

   ```powershell
   $env:LLM_PROVIDER = "local"
   $env:DEMO_MODE = "false"
   $env:MIMO_BASE_URL = "http://127.0.0.1:8080/v1"
   $env:LLM_DEFAULT_MODEL = "mimo-7b-rl-q4_k_m"
   $env:LLM_COMPLEX_MODEL = "mimo-7b-rl-q4_k_m"
   cd backend
   uvicorn app.main:app --reload
   ```

Файлы модели и рантайма хранятся в `.local-model/`, исключённой из Git.
Q4 — экспериментальная 4-битная конверсия; перед использованием извлечённые
значения и цитаты необходимо сверять с исходными документами.

В локальном режиме длинный запрос автоматически делится на части размером
`LLM_INPUT_CHUNK_CHARS` (по умолчанию 12 000 символов), чтобы не превышать окно
контекста модели. Результаты объединяются, а разные значения одного поля
помечаются как противоречие. Для ошибки модели интерфейс показывает текст
причины, а не сырой JSON ответа API.
