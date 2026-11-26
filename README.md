# AI Software Engineer

An AI-powered code intelligence platform that lets users ask questions about public GitHub repositories and receive answers grounded in actual source code, with verified file-path and line-number citations.

## Features

- **Repository Q&A:** Understand codebases through natural-language queries.
- **AST-Aware Chunking:** Extract functions, classes, and methods using Tree-sitter.
- **Semantic Search:** Retrieve relevant code using MiniLM embeddings and FAISS.
- **Multi-Agent RAG:** Four-stage LangGraph pipeline for query decomposition, retrieval, deduplication, and generation.
- **Citation Verification:** Validate generated file paths and line ranges against retrieved code.
- **Code Optimization:** Identify potential improvements.
- **Duplicate Detection:** Detect identical and semantically similar code.
- **Multi-LLM Support:** Groq, Gemini, OpenAI, and Ollama.
- **Persistent Storage:** Store FAISS indexes and metadata in PostgreSQL.
- **Repository Isolation:** Independent indexes and user-level access control.

## Tech Stack

| Layer | Technologies | Hosting |
|---|---|---|
| Frontend | React, Vite, TypeScript | Vercel |
| Backend | Python, FastAPI | Railway |
| Code Parsing | Tree-sitter | Backend |
| Embeddings | Sentence Transformers (MiniLM) | Backend |
| Vector Database | FAISS | Backend |
| AI Orchestration | LangGraph | Backend |
| Database | PostgreSQL | Neon |
| Authentication | JWT, bcrypt | Backend |
| Containerization | Docker | Railway |

## Architecture

```text
GitHub Repository
       |
       v
  Shallow Clone
       |
       v
 Tree-sitter AST
       |
       v
  Code Chunking
       |
       v
 MiniLM Embeddings
       |
       v
  FAISS Index
       |
       v
 PostgreSQL Storage

     User Query
         |
         v
   LangGraph Agent
         |
   +-----+------+
   |     |      |
Decompose Retrieve Dedupe
   |     |      |
   +-----+------+
         |
         v
    LLM Generation
         |
         v
 Citation Verification
         |
         v
 Grounded Response
```

## Supported Languages

Python, JavaScript, TypeScript, TSX, Java, Go, Rust, C, C++, C#, Ruby, PHP, Kotlin, Swift, Scala, Bash, and Lua.

Jupyter notebooks are also supported.

## Deployment

| Component | Platform |
|---|---|
| Frontend | Vercel |
| Backend API | Railway |
| PostgreSQL | Neon |

**Frontend environment variable:**

```env
VITE_API_URL=https://your-railway-backend-url
```

**Backend environment variables:**

```env
ENVIRONMENT=production
DATABASE_URL=your_neon_postgresql_url
JWT_SECRET=your_secure_secret
CORS_ORIGINS=your_vercel_frontend_url
LLM_PROVIDER=groq
```

Configure the appropriate API key for your selected LLM provider.

## Local Development

**Backend**

```bash
cd backend
python -m venv .venv
pip install -r requirements-dev.txt
cp .env.example .env
python -m app.scripts.download_model
uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

Backend API Docs: `http://localhost:8000/docs`

## Testing

```bash
cd backend
pytest

cd frontend
npm run build
```

Backend includes 78 tests covering ingestion, retrieval, citation verification, authentication, FAISS persistence, repository isolation, and LLM integrations.

## Project Structure

```text
AI-Software-Engineer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── ingestion/
│   │   ├── rag/
│   │   ├── llm/
│   │   └── services/
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   └── src/
├── scripts/
│   └── smoke_test.py
└── README.md
```

## License

Add an appropriate open-source license before distributing the project.

---

**Built with Python, FastAPI, Tree-sitter, FAISS, LangGraph, React, and PostgreSQL.**
