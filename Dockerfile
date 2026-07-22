# TruthGuard API — Hugging Face Spaces (Docker SDK).
#
# Spaces gives 2 vCPU / 16 GB free, which is enough for the embedder and the
# cross-encoder. The models are baked in at build time rather than downloaded on
# first request, so the first question does not pay ~54s of model loading.
FROM python:3.11-slim

# tesseract is the tier-1 OCR engine; libgl/libglib are needed by the imaging deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr libtesseract-dev libgl1 libglib2.0-0 git \
    && rm -rf /var/lib/apt/lists/*

# Spaces runs as a non-root user; HF caches must be writable by it.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

USER user

# Pre-download the two local models into the image. Without this the first
# request pays the download and load cost, and Spaces may time out the boot.
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('all-MiniLM-L6-v2'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2'); \
print('models cached')"

COPY --chown=user . .

# Public deployment posture: readable and askable by anyone, writable by nobody.
# TG_READONLY blocks /ingest and /config regardless of whether a token is set.
ENV TG_READONLY=1 \
    TG_STORAGE_DIR=/app/storage/truthguard \
    TG_CORPUS_DIR=/app/corpus \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# Spaces routes public traffic to 7860.
EXPOSE 7860
CMD ["uvicorn", "truthguard.api:app", "--host", "0.0.0.0", "--port", "7860"]
