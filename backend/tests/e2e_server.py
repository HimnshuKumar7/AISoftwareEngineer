"""LOCAL VERIFICATION ONLY: runs the real FastAPI app with the test doubles (hashing embedder + scripted LLM)
because this sandbox cannot download MiniLM or reach an LLM API. Never used in deployment."""
import os, sys, tempfile
tmp = tempfile.mkdtemp(prefix="ase-e2e-")
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/e2e.db", JWT_SECRET="e2e-" + "s" * 40, ENVIRONMENT="test",
                  DATA_DIR=f"{tmp}/data", CORS_ORIGINS="https://app.example.com", LOG_LEVEL="WARNING",
                  LLM_PROVIDER="groq", GROQ_API_KEY="x")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.conftest import HashingEmbedder, ScriptedLLM  # noqa: E402
from app.ingestion import embedder as em  # noqa: E402
import app.services.query_service as qs  # noqa: E402
em._embedder = HashingEmbedder()
_llm = ScriptedLLM()
qs.get_llm = lambda provider=None, model=None: _llm
import uvicorn  # noqa: E402
from app.main import app  # noqa: E402
uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8765")), log_level="warning")
