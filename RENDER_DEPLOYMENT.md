# Render Deployment & Memory Optimization Guide (512MB RAM)

This guide documents the memory optimizations implemented to prevent **Out-Of-Memory (OOM)** errors on Render's Free and Starter tiers (512MB RAM) and provides exact configuration settings.

---

## 1. Why Render Experiences OOM Crashes

On Render's Free/Starter tiers, services are capped at **512MB RAM**. When the memory threshold is exceeded, the Linux kernel invokes the Out-Of-Memory (OOM) killer to terminate the backend process instantly.

The original codebase had several compounding memory leaks and peaks:
1. **Multi-Worker Uvicorn (`WEB_CONCURRENCY > 1`)**:
   Render automatically calculates `WEB_CONCURRENCY` based on host CPU cores (often 2–4 workers). Each worker is an independent Python process loading PyTorch, `sentence-transformers`, and FastAPI (~250MB per process). 2 workers alone exceeded 500MB immediately upon startup.
2. **PyTorch Multi-Thread BLAS Pools**:
   By default, PyTorch and OpenMP allocate thread pools and tensor scratchpads across all available CPU cores, causing sudden RAM spikes during embedding generation.
3. **Full-Repository Chunk Accumulation**:
   The entire repository was parsed into memory, generating hundreds or thousands of `CodeChunk` objects into a single Python list. All chunks were then converted into `Document` objects and passed all at once to `embed_documents()`, allocating massive tensor buffers in RAM.
4. **Unbounded In-Memory FAISS Index Caching**:
   `build_index` kept the full FAISS index and its in-memory Python `docstore` (containing every chunk's text and metadata) permanently in `_LOADED_CACHE`. Every subsequent query or indexing operation accumulated more indexes in RAM without eviction.
5. **Concurrent Indexing Jobs**:
   Multiple simultaneous indexing requests multiplied clone, parse, and embedding overhead, instantly crashing the container.

---

## 2. Implemented Memory Protections

| Problem | Solution | Implementation |
|---|---|---|
| **Multi-Worker Uvicorn** | Enforce single-worker mode | `WEB_CONCURRENCY=1`, `uvicorn --workers 1` |
| **PyTorch CPU Thread Spikes** | Single-threaded inference | `torch.set_num_threads(1)`, `torch.set_grad_enabled(False)`, `OMP_NUM_THREADS=1`, `TORCH_NUM_THREADS=1` |
| **Full Repo Chunk Accumulation** | Streaming generator + batching | `stream_chunk_batches(repo_path, batch_size=32)` streams chunks without accumulating all files or chunks in memory |
| **Monolithic Embeddings** | Incremental batch indexing | `FAISS.from_documents()` on batch 1, `store.add_documents()` on batches 2..N, with explicit `del` and `gc.collect()` per batch |
| **Unbounded FAISS In-Memory Cache** | Evict upon build + Bounded LRU (size=1) | Indexes are saved to disk and immediately unloaded from RAM; query-time cache keeps at most 1 index in memory |
| **Concurrent Indexing Collisions** | Non-blocking thread lock | `_INDEXING_LOCK = threading.Lock()` limits indexing to 1 job at a time; returns HTTP 429 to concurrent requests |
| **Memory Visibility** | Real-time memory monitoring | `/api/health` reports live RSS memory, peak memory, and cached indexes |

---

## 3. Exact Render Environment Variables

Set these environment variables in your Render Dashboard under **Environment** (or use the provided `render.yaml` blueprint):

| Variable | Recommended Value | Purpose |
|---|---|---|
| `WEB_CONCURRENCY` | `1` | **CRITICAL**: Restricts Uvicorn to 1 process. Prevents duplicating PyTorch in RAM. |
| `PYTHONUNBUFFERED` | `1` | Ensures logs stream in real-time to the Render console. |
| `OMP_NUM_THREADS` | `1` | Limits OpenMP thread buffers in numerical libraries. |
| `MKL_NUM_THREADS` | `1` | Limits Intel MKL CPU threads. |
| `OPENBLAS_NUM_THREADS` | `1` | Limits OpenBLAS thread buffers. |
| `VECLIB_MAXIMUM_THREADS` | `1` | Limits Apple VecLib (if applicable). |
| `NUMEXPR_NUM_THREADS` | `1` | Limits NumExpr thread overhead. |
| `TORCH_NUM_THREADS` | `1` | Restricts PyTorch CPU intra-op threads to 1. |
| `INDEXING_BATCH_SIZE` | `32` | Number of chunks per FAISS embedding batch. |
| `EMBEDDING_BATCH_SIZE` | `16` | Batch size for sentence-transformers encoding. |
| `FAISS_CACHE_MAX_SIZE` | `1` | Maximum number of FAISS indexes retained in memory. |
| `LLM_PROVIDER` | `groq` or `gemini` | Hosted LLM provider (`groq` / `gemini` / `openai`). **Do NOT run Ollama inside a 512MB Render web service.** |
| `GROQ_API_KEY` | *(your key)* | API key if using Groq (`llama-3.1-8b-instant`). |
| `GEMINI_API_KEY` | *(your key)* | API key if using Gemini (`gemini-2.0-flash`). |
| `DATABASE_URL` | *(neon connection string)* | Neon Postgres connection string with `sslmode=require`. |
| `JWT_SECRET` | *(64-char hex string)* | Secret for signing JWT authentication tokens. |
| `CORS_ORIGINS_RAW` | `http://localhost:5173,https://your-frontend.onrender.com` | Allowed CORS origins for your frontend app. |

---

## 4. Render Service Deployment Settings

### Option A: Deploy via Blueprint (`render.yaml`)
1. Push your repository to GitHub.
2. In Render, select **Blueprints** -> **New Blueprint Instance**.
3. Select this repository. Render will automatically read `render.yaml`, configure the Python 3.11 environment, set all memory-safe environment variables, and configure the web service.
4. Fill in your secrets (`DATABASE_URL`, `GROQ_API_KEY` or `GEMINI_API_KEY`).

### Option B: Manual Web Service Setup
- **Environment**: `Python`
- **Root Directory**: `backend`
- **Build Command**: `pip install --no-cache-dir -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
- **Instance Type**: `Free` or `Starter` (512MB RAM)

---

## 5. Memory Monitoring & Verification

You can inspect the live memory footprint of your backend at any time:

### Live Health & Memory Check
```bash
curl https://your-backend.onrender.com/api/health
```
Response:
```json
{
  "status": "ok",
  "llm_provider": "groq",
  "memory": {
    "rss_mb": 182.45,
    "vms_mb": 420.12,
    "indexing_in_progress": false,
    "cached_indexes": []
  }
}
```

### Manual Cache Clearing (Optional Maintenance)
```bash
curl -X POST https://your-backend.onrender.com/api/system/clear-cache \
     -H "Authorization: Bearer <JWT_TOKEN>"
```
This forces all loaded FAISS indexes out of memory and runs garbage collection, dropping memory back to baseline.
