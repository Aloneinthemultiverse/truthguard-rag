import os
from dotenv import load_dotenv

load_dotenv()

# LLM (Anthropic-compatible endpoint)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.anthropic.com")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")   # "anthropic" | "openai" (NVIDIA NIM)
MAX_LLM_CALLS_PER_QUERY = 6

# Embeddings (local)
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Storage
STORAGE_DIR = os.getenv("TG_STORAGE_DIR", "./storage/truthguard")
CORPUS_DIR = os.getenv("TG_CORPUS_DIR", "./corpus")

# Chunking
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

# OCR ladder (FR-1.6)
OCR_TIER1_MIN_CONF = 0.85       # below -> escalate
OCR_GARBAGE_RATIO_MAX = 0.20    # above -> escalate
MAX_TIER2_PAGES = int(os.getenv("TG_MAX_TIER2_PAGES", "20"))
MISTRAL_OCR_API_KEY = os.getenv("MISTRAL_OCR_API_KEY", "")

# Tier-2 escalation backend: none | dots | ollama | mistral.
# Default "none" keeps the pipeline free and dependency-light — Tesseract alone
# handles ordinary scans. "dots" targets a self-hosted dots.ocr behind vLLM,
# which needs a CUDA GPU with ~9-16 GB VRAM on the serving host.
# Tier-1 engine: tesseract | doctr.
# Tesseract is the default because it starts instantly and needs no weights.
# docTR is a deep-learning detector+recognizer: better on poor scans and much
# better at reading order on multi-column pages, at roughly 1.6x the time per
# page plus a one-off model load. Measured on a rasterized two-column paper:
# tesseract 82.1% word recall, docTR 84.4% — and docTR kept the title first
# where tesseract hoisted a margin stamp to the top.
#   auto       (default) quality-driven ladder — see ocr._tier1_ocr
#   tesseract  fast, instant start, weakest on multi-column and poor scans
#   doctr      detection-then-recognition; better reading order and poor scans
#   paddleocr  angle-invariant; best on rotated or scattered text (maps, photos)
OCR_ENGINE = os.getenv("TG_OCR_ENGINE", "auto")

# PaddleOCR runs out-of-process: paddlepaddle has no wheel for Python 3.13+, so
# it lives in its own virtualenv and is invoked as a subprocess.
PADDLE_PYTHON = os.getenv(
    "TG_PADDLE_PYTHON",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 ".venv-paddle", "Scripts", "python.exe"))
PADDLE_TIMEOUT = int(os.getenv("TG_PADDLE_TIMEOUT", "180"))

OCR_TIER2_BACKEND = os.getenv("TG_OCR_TIER2", "none")
OCR_TIER2_URL = os.getenv("TG_OCR_TIER2_URL", "http://127.0.0.1:8000/v1")
OCR_TIER2_MODEL = os.getenv("TG_OCR_TIER2_MODEL", "rednote-hilab/dots.ocr")
OCR_TIER2_KEY = os.getenv("TG_OCR_TIER2_KEY", "")
OCR_TIER2_TIMEOUT = int(os.getenv("TG_OCR_TIER2_TIMEOUT", "120"))

# Retrieval
TOP_K_FUSED = 50                # into rerank
TOP_K_FINAL = 10                # into assessment
CONTEXT_BUDGET_TOKENS = int(os.getenv("TG_CONTEXT_BUDGET", "4000"))  # hard cap on get_context
N_INTERPRETATIONS = 3           # superposed multi-query
RRF_K = 60

# Assessment (FR-3)
SUFFICIENCY_MIN_SIM = 0.30      # below -> INSUFFICIENT early

# Controller (FR-4)
MAX_REWRITES = 2
CONF_ANSWER = 0.75              # bands: >=0.75 answer / 0.4-0.75 hedge / <0.4 refuse
CONF_HEDGE = 0.40
