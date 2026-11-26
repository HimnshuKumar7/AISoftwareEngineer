# AI Software Engineer

Ask questions about any public GitHub repository and get answers grounded in its real code, with file-path and
line-number citations. Built on a RAG pipeline: **Tree-sitter → MiniLM embeddings → per-repository FAISS indexes →
4-stage LangGraph agent → pluggable LLM**.

| Layer | Technology | Hosted on |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript | **Vercel** |
| Backend | Python FastAPI, JWT auth | **Render** (Docker) |
| Database | PostgreSQL (users, repositories, query history, **persisted FAISS indexes**) | **Neon** |

## How it works

```
GitHub URL ─► git clone (shallow) ─► Tree-sitter AST chunks ─► MiniLM (all-MiniLM-L6-v2) ─► FAISS index (one per repo)
                                     function / method / class       384-d, L2-normalised            └─► serialized into Neon
```

**Ingestion.** 16 languages via per-language Tree-sitter wheels (no runtime downloads): Python, JavaScript, TypeScript,
TSX, Java, Go, Rust, C, C++, C#, Ruby, PHP, Kotlin, Swift, Scala, Bash, Lua. Each function, method and class becomes a
chunk with an exact 1-based line range; top-level code becomes `module` chunks and README/docs become `doc` chunks.
Long functions are split into overlapping windows, long classes keep their header (members are separate chunks).
**Jupyter notebooks (`.ipynb`)** are flattened to a text view (one `# %% [code] cell N` header per cell; outputs are never indexed). Code cells are parsed with Tree-sitter in the notebook's kernel language (IPython `%`/`!` magics are neutralised), markdown cells become `doc` chunks, and chunk line numbers refer to that view, so the UI's GitHub link omits the line anchor for notebooks.
Embeddings are generated **only** by Sentence-Transformers `all-MiniLM-L6-v2`, independent of the LLM provider.

**RAG (LangGraph, 4 stages).** `decompose` (LLM → 2–4 sub-queries, heuristic fallback) → `retrieve` (FAISS search per
sub-query) → `dedupe` (same chunk, contained chunks, identical code) → `generate` (answer from line-numbered excerpts).
Every `[path:start-end]` in the answer is **verified against the retrieved chunks**; unknown files/lines are removed and
valid ranges are clamped to what was actually retrieved, so citations cannot point at invented lines.

**Capabilities** (the `mode` of a query): `qa` repository Q&A · `explain` documentation/explanation · `optimize`
optimisation suggestions · `duplicates` duplicate-code analysis. Duplicates combine exact content hashes with FAISS
nearest neighbours confirmed by token-shingle overlap; `GET /api/repos/{id}/duplicates` runs a whole-repo scan with no LLM.

**Isolation.** One FAISS index per repository id, stored in `repo_indexes` keyed by that id. Nothing searches across
repositories, and every repository route checks ownership (other users get `404`).

**Persistence on an ephemeral disk.** Render's filesystem is wiped on restart/redeploy, so the serialized index
(`faiss.serialize_index`) and gzip-compressed chunk metadata live in Neon and are lazily loaded into a small in-RAM LRU.
Indexes survive restarts and redeploys; nothing important is written to local disk.

## Repository layout

```
backend/   FastAPI app (app/api, core, db, ingestion, rag, llm, services), schema.sql, Dockerfile, tests/
frontend/  React app, vercel.json
render.yaml        Render Blueprint (backend)
scripts/smoke_test.py   end-to-end check of a running deployment
```

## Environment variables

### Backend (Render)

| Variable | Required | Description |
|---|---|---|
| `ENVIRONMENT` | yes | `production` enables strict startup checks (refuses weak `JWT_SECRET` / SQLite) |
| `DATABASE_URL` | yes | Neon connection string, `postgresql://…?sslmode=require` (pooled or direct) |
| `JWT_SECRET` | yes | ≥ 32 random chars (`python -c "import secrets; print(secrets.token_urlsafe(48))"`); `render.yaml` generates one |
| `CORS_ORIGINS` | yes | Comma-separated exact frontend origins, no trailing slash, e.g. `https://my-app.vercel.app` |
| `CORS_ORIGIN_REGEX` | no | e.g. `https://my-app-.*\.vercel\.app` to allow Vercel preview deployments |
| `LLM_PROVIDER` | yes | `ollama` \| `groq` \| `gemini` \| `openai` |
| `LLM_MODEL` | no | Model id for the selected provider; blank uses the default in `app/llm/providers.py` |
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` | per provider | Key for the provider(s) you enable |
| `OLLAMA_BASE_URL` | for Ollama | Must be reachable from Render (a public/tunnelled host; `localhost` will not work) |
| `MAX_REPOS_PER_USER`, `MAX_REPO_SIZE_MB`, `MAX_FILES_PER_REPO`, `MAX_FILE_SIZE_KB`, `MAX_CHUNKS_PER_REPO`, `EMBEDDING_BATCH_SIZE` | no | Resource limits, defaults tuned for 512 MB |
| `AUTO_CREATE_TABLES` | no | `true` (default) creates tables on boot; set `false` if you apply `backend/schema.sql` yourself |

Every configured provider appears in the chat UI's provider dropdown; `LLM_PROVIDER`/`LLM_MODEL` set the default.
Default model ids (`llama-3.3-70b-versatile`, `gemini-2.5-flash`, `gpt-4o-mini`, `llama3.1:8b`) are only defaults:
providers retire models, so confirm they still exist and override with `LLM_MODEL` if not.

### Frontend (Vercel)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | yes | Backend origin, e.g. `https://ai-software-engineer-api.onrender.com` (no trailing slash, no `/api`) |

`VITE_*` values are baked in at build time: after changing it, **redeploy**.

## Deployment (do the steps in this order)

### 1. Neon PostgreSQL
1. Create a project at neon.tech and copy the connection string (**Connection Details**, keep `sslmode=require`).
2. Tables are created automatically on first boot. To manage the schema yourself, run `backend/schema.sql` in the
   Neon SQL editor and set `AUTO_CREATE_TABLES=false`.

### 2. Backend on Render
1. Push this repository to GitHub.
2. Render dashboard → **New → Blueprint** → select the repository (reads `render.yaml`). Or create a **Web Service**
   manually with runtime **Docker**, Dockerfile path `./backend/Dockerfile`, Docker context `./backend`, health check
   path `/api/health`.
3. Fill the prompted variables: `DATABASE_URL`, your LLM provider key, and for now `CORS_ORIGINS=http://localhost:5173`.
4. Deploy. The Docker build installs CPU-only PyTorch, the pinned requirements, and **downloads the MiniLM weights into
   the image**, so the running service never needs Hugging Face. Build commands/start command are in `backend/Dockerfile`
   (start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`).
5. Open `https://<service>.onrender.com/api/health` → `{"status":"ok"}`, and `/api/health/ready` → `{"status":"ready"}`
   (confirms Neon connectivity).

### 3. Frontend on Vercel
1. Vercel → **Add New → Project** → import the repository, set **Root Directory** to `frontend`.
   `frontend/vercel.json` already sets the build (`npm run build`), output (`dist`) and the SPA rewrite so `/app/...`
   deep links and refreshes work.
2. Add the environment variable `VITE_API_URL` = your Render URL (Production and Preview) and deploy.

### 4. Connect them
Set Render's `CORS_ORIGINS` to the exact Vercel production URL (e.g. `https://my-app.vercel.app`) and let Render redeploy.
Tokens travel in the `Authorization` header, so credentialed cookies/CORS are intentionally disabled.

### 5. Verify end to end
```bash
python scripts/smoke_test.py --api https://<service>.onrender.com --origin https://<app>.vercel.app
```
It checks health, database, CORS from your Vercel origin, register/login, GitHub clone → index → `ready`, a real
question with file/line citations that all lie inside retrieved sources, conversation history, and cleanup. Then
sign in on the Vercel site and index a repository from the UI. **Treat the deployment as done only when this passes.**

## Free-tier notes (read before relying on it)

* **Cold starts:** Render free web services sleep after ~15 min idle; the first request can take about a minute (the
  UI shows a "waking up" notice). While a repository is indexing the UI polls every 2.5 s, which keeps the service awake.
* **Memory (512 MB):** PyTorch + MiniLM + FAISS is tight. The app loads the model lazily, runs **one** indexing job at a
  time, encodes in small batches, caps files/chunks per repository, and uses one worker. If Render reports out-of-memory
  during indexing, lower `MAX_CHUNKS_PER_REPO`/`EMBEDDING_BATCH_SIZE` or move to the Starter plan (2 GB). Peak memory
  has **not** been measured on Render, so check the service's metrics after your first index.
* **Interrupted jobs:** a restart mid-index marks the repository `failed` ("interrupted"); use **Re-index**.
* **Neon storage:** each index is ~1.5 KB per chunk plus code text (a 3,000-chunk repo ≈ 5–10 MB); the free tier is 0.5 GB.
* **LLM limits:** free provider tiers have per-minute token caps; context size is bounded by `MAX_CONTEXT_CHARS`.

## Local development

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
cp .env.example .env            # set DATABASE_URL (Neon, or leave the SQLite default), JWT_SECRET, an LLM key
python -m app.scripts.download_model
uvicorn app.main:app --reload --port 8000    # API docs: http://localhost:8000/docs

# frontend (new terminal)
cd frontend
cp .env.example .env.local      # VITE_API_URL=http://localhost:8000
npm install && npm run dev      # http://localhost:5173
```

## Tests

```bash
cd backend && pytest                 # 78 tests; `pytest -m "not network"` skips the real GitHub clone tests
cd frontend && npm run build         # type-checks and builds
```
Covered: all 16 languages with exact line-range verification, long-function splitting, the 4-node LangGraph and
2–4 sub-query guarantee, de-duplication, citation grounding, duplicate detection, FAISS persistence/restart/isolation,
every LLM provider's request/response handling, JWT auth, CORS, cross-user authorization, input validation, and a full
workflow against a real GitHub repository (clone → index → query → citations compared with the upstream files).

The automated tests use a **hashing stand-in for the embedder and a scripted LLM** (see `backend/tests/conftest.py`)
because the real MiniLM weights and LLM APIs need network access. The production code path uses only
Sentence-Transformers MiniLM; `python -m app.scripts.download_model` (run in the Docker build) fails the build if the
model cannot be loaded or does not produce 384-d vectors.

## Security notes
Passwords are bcrypt-hashed; JWTs are HS256 with expiry; repository URLs are strictly validated and cloned with
argument lists (no shell), hooks/submodules/credential prompts disabled and size/time limits; symlinks are never followed;
validation errors never echo submitted values; the JWT is kept in `localStorage` (simple, but exposed to XSS, so
the app renders model output through `react-markdown` without raw HTML). There is no login rate limiting; add one
(or Cloudflare) before exposing it publicly.

## API overview
`POST /api/auth/register|login` · `GET /api/auth/me` · `GET|POST /api/repos` · `GET|DELETE /api/repos/{id}` ·
`POST /api/repos/{id}/reindex` · `GET /api/repos/{id}/duplicates` · `POST /api/repos/{id}/query` ·
`GET /api/repos/{id}/history|conversations` · `GET /api/llm/providers` · `GET /api/health[/ready]`.
Interactive docs at `/docs`.
