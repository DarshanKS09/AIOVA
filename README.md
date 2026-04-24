# AIOVA

A small full-stack app for turning plain-language interaction notes into structured CRM-style fields.

## Stack

- Backend: FastAPI
- Frontend: React + Vite
- Optional AI parsing: OpenAI API via `OPENAI_API_KEY`

## Local setup

### Backend

1. Create and activate a virtual environment inside `backend/`.
2. Install dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Copy `backend/.env.example` to `backend/.env` and set your values.
4. Start the API:

```bash
uvicorn backend.main:app --reload
```

### Frontend

1. Install dependencies:

```bash
npm --prefix frontend install
```

2. Copy `frontend/.env.example` to `frontend/.env`.
3. Start the app:

```bash
npm --prefix frontend run dev
```

## Environment variables

### Backend

- `OPENAI_API_KEY`: optional. If omitted, the backend falls back to regex/date parsing.
- `OPENAI_MODEL`: optional. Defaults to `gpt-4o-mini`.
- `FRONTEND_ORIGIN`: optional. Defaults to `http://localhost:5173`.

### Frontend

- `VITE_API_BASE_URL`: optional. Defaults to `http://localhost:8000`.

## Before pushing to GitHub

- Keep `backend/.env` and `frontend/.env` local only.
- Do not commit `backend/venv/`, `frontend/node_modules/`, build output, or cache files.
- If you already initialized a Git repo somewhere above this folder, make sure you are pushing the intended repository root.
