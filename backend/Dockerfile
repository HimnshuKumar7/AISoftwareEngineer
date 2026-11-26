FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_CACHE_DIR=/app/models \
    DATA_DIR=/tmp/ai-software-engineer \
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=2

# git is required to clone repositories at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch first (a few hundred MB instead of ~2 GB of CUDA libraries).
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY schema.sql ./schema.sql

# Bake the MiniLM weights into the image so the running service never depends on Hugging Face.
RUN python -m app.scripts.download_model

RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 10000
# Render injects $PORT. A single worker keeps one copy of the embedding model in RAM.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
