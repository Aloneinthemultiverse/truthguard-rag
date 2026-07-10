"""TruthGuard RAG — self-correcting RAG pipeline over messy documents.

The generator LLM is never called until retrieved context passes the
assessment gate. See docs/PRD.md and docs/ARCHITECTURE.md.
"""

__version__ = "0.1.0"
