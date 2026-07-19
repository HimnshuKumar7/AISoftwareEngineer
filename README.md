# repo:// AI Software Engineer

An AI assistant that understands an entire GitHub repository: explains flows,
finds where things are implemented, generates docs/tests, finds duplicate
code, and suggests optimizations.

**Pipeline:** GitHub Repo → Clone → Parse (Tree-sitter) → Chunk → Embeddings
→ FAISS → LangGraph (`Planner → Code Search → Reasoner → Final Answer`) → FastAPI → React

```
ai-swe/
├── backend/         FastAPI + LangChain + LangGraph + FAISS + Tree-sitter
└── frontend/         React (Vite) chat UI
```

---

## 1. Which models to use (free options)

Embeddings are **always free and local** — `sentence-transformers/all-MiniLM-L6-v2`
runs on CPU, no API key, no cost, and never leaves your machine.

For the reasoning LLM (Planner / Reasoner / Final Answer), pick one:

| Provider | Cost | Setup | Notes |
|---|---|---|---|
| **Ollama** (recommended to start) | Free, 100% local | Install [ollama.com](https://ollama.com), then `ollama pull qwen2.5-coder:7b` | No API key, fully private, needs ~8GB RAM. Also try `codellama:13b`, `deepseek-coder-v2:16b`, or `llama3.1:8b`. |
| **Groq** | Free tier (generous rate limits) | Get a key at [console.groq.com](https://console.groq.com) | Hosted, very fast, `llama-3.3-70b-versatile` is strong for code reasoning. |
| **Gemini** | Free tier | Get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `gemini-2.0-flash` is fast and free within quota. |
| OpenAI | Paid | api.anthropic keys not applicable here — needs OpenAI billing | Only use if you already have credits. |

Set your choice in `backend/.env` via `LLM_PROVIDER=ollama|groq|gemini|openai`.
You can switch providers any time without re-indexing (indexing only uses the
free local embedding model).

**Recommended for a portfolio demo:** start with `ollama` (zero cost, zero
signup) so anyone can run your project instantly, then optionally show it
also works with Groq/Gemini for speed.

---

## 2. Auth, Dashboard & Neon Postgres

The app now has a **sign in / sign up** page and a **dashboard** (name,
email, previously indexed repos, recent Q&A history). All of this is stored
in **Neon** (serverless Postgres), via SQLAlchemy.

### 2.1 Create a free Neon database
1. Go to https://neon.tech, sign up (free tier is plenty for this project).
2. Create a project, then open **Connection Details** and copy the connection
   string. It looks like:
   ```
   postgresql://neondb_owner:PASSWORD@ep-xxxx-pooler.region.aws.neon.tech/neondb?sslmode=require
   ```
3. Paste it into `backend/.env` as `DATABASE_URL`.

### 2.2 Set a JWT secret
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```
Paste the output into `backend/.env` as `JWT_SECRET`.

### 2.3 Tables are created automatically
On first backend startup, `init_db()` runs `Base.metadata.create_all(...)`,
which creates the `users`, `repos`, and `query_history` tables in your Neon
database if they don't already exist. No manual migration step needed for
this project's scope (for a production app, swap this for Alembic migrations).

### How auth works
- `POST /api/auth/signup` — name, email, password → bcrypt-hashed password
  stored, returns a JWT.
- `POST /api/auth/login` — email, password → JWT.
- Every other API route (`/api/repos/index`, `/api/ask`, quick actions,
  `/api/auth/dashboard`) requires `Authorization: Bearer <token>` and is
  scoped to the signed-in user.
- The frontend stores the JWT in `localStorage` and attaches it to every
  request via `frontend/src/api.js`.
- Every indexed repo is saved to the `repos` table (owned by the user who
  indexed it) and every question/answer is saved to `query_history` — that's
  what populates the dashboard.

---

## 3. Running on Windows with a virtual environment

### Prerequisites
- Python 3.11 (from [python.org](https://python.org) — check "Add to PATH" during install)
- Node.js 20 LTS (from [nodejs.org](https://nodejs.org))
- Git for Windows
- (If using Ollama) install from [ollama.com/download/windows](https://ollama.com/download/windows)

### Step 1 — Backend setup (PowerShell)

```powershell
cd ai-swe\backend

# create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1

# if PowerShell blocks the activation script, run once as admin:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2 — Configure your `.env`

```powershell
copy .env.example .env
notepad .env
```

For the free local option, just leave `LLM_PROVIDER=ollama` and set:
```
OLLAMA_MODEL=qwen2.5-coder:7b
```
Also fill in `DATABASE_URL` (your Neon connection string) and `JWT_SECRET`
as described in section 2 above — the backend won't start without a valid
`DATABASE_URL`.
Then in a separate terminal:
```powershell
ollama pull qwen2.5-coder:7b
ollama serve
```
(Ollama usually auto-starts a background service after install, so `ollama serve`
may already be running — check the system tray.)

If you'd rather use a hosted free tier, set `LLM_PROVIDER=groq` and paste your
key into `GROQ_API_KEY` (no local model download needed).

### Step 3 — Run the backend

```powershell
# still inside ai-swe\backend, with venv active
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/api/health` — you should see `{"status":"ok",...}`.

### Step 4 — Run the frontend (new terminal)

```powershell
cd ai-swe\frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### Step 5 — Use it
1. Paste a GitHub repo URL (e.g. `https://github.com/psf/requests`) → **Index repo**.
   First index can take a minute or two (cloning + embedding).
2. Ask questions like *"Where is authentication handled?"* or *"Explain the retry logic."*
3. Enter a file path (e.g. `requests/auth.py`) and use the quick action buttons
   to generate docs, tests, find duplicates, or get optimization suggestions.

---

## 4. Running with Docker (optional, alternative to venv)

```powershell
cd ai-swe
copy backend\.env.example backend\.env
# edit backend\.env as above
docker compose up --build
```

Backend → `http://localhost:8000`, frontend → `http://localhost:5173`.

If you're using **Ollama** and running Docker, Ollama should stay running on
your Windows host, and the backend container needs to reach it via
`host.docker.internal` — uncomment `extra_hosts` in `docker-compose.yml` and
set `OLLAMA_BASE_URL=http://host.docker.internal:11434` in `.env`.

---

## 5. How each requested capability maps to the code

| Feature | Implementation |
|---|---|
| Explain authentication flow / Where is JWT implemented / Which files handle login / Explain this API | `/api/ask` → full LangGraph pipeline (Planner plans sub-queries, Code Search retrieves via FAISS, Reasoner + Final Answer synthesize a cited answer) |
| Generate documentation | `/api/repos/docs` (pre-filled prompt, reuses the same graph) |
| Find duplicate code | `/api/repos/duplicates` |
| Suggest optimizations | `/api/repos/optimize` |
| Generate unit tests | `/api/repos/tests` |

Code understanding comes from **Tree-sitter** (`app/ingestion/parser.py`),
which parses each source file into an AST and extracts function/class/method
level chunks (with a line-window fallback for unsupported languages) —
this is what lets retrieval return whole, meaningful units of code instead of
arbitrary text slices.

---

## 6. Extending this project (ideas for your portfolio writeup)

- Add a `Critic` node to the graph that checks the Final Answer against the
  retrieved sources and asks the Reasoner to redo the search if unsupported.
- Stream tokens over Server-Sent Events / WebSockets instead of returning the
  full answer at once.
- Add incremental indexing (only re-embed changed files) via git diff.
- Swap FAISS for a hosted vector DB (Qdrant, pgvector) for multi-user scale.
- Add authentication + per-user repo indexes for a real SaaS version.
