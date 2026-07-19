**Hackathon:** OneInbox AI Internship Hackathon 2026 | **Track:** AI Engineer | **Problem Statement 1:** Self-Correcting RAG Pipeline
**Repo:** github.com/Aloneinthemultiverse/truthguard-rag | **Status:** BUILT & MEASURED (not a proposal)

---

# Product Requirements Document (PRD): TruthGuard RAG

## 1. Executive Summary
TruthGuard RAG is a high-precision, self-correcting Retrieval-Augmented Generation (RAG) system designed to transform messy, unstructured data into a verifiable "Institutional Brain." This directly addresses Problem Statement 1 — a RAG system over messy, unstructured documents (mixed PDFs, scanned images needing OCR, inconsistent formatting) that detects when retrieved context is insufficient or contradictory and re-queries, asks clarifying questions, or returns low-confidence responses instead of hallucinating — plus an evaluation harness comparing hallucination rates before/after the self-correction layer. Unlike standard RAG pipelines that blindly generate answers, TruthGuard implements a structural assessment gate that treats data as a logic puzzle, ensuring every response is grounded in "Compiled Truth."

## 2. Problem Statement
Standard RAG systems suffer from four critical failure modes:
*   **Blindness:** Inability to process unread scans or complex layouts.
*   **Omission-Hallucination:** Fabricating answers when the corpus lacks the necessary information.
*   **Silent Arbitration:** Arbitrarily picking one side when sources provide contradictory data.
*   **Ambiguity-Guessing:** Making assumptions about vague user queries instead of seeking clarification.

## 3. Goals & Objectives
*   **Structural Integrity:** Prevent hallucinations by decoupling retrieval assessment from generation.
*   **Multi-Plane Memory:** Maintain a global, 3-plane context graph (Chat, Knowledge, Code) that persists across sessions.
*   **Efficiency:** Maintain $O(\text{neighborhood})$ context retrieval costs regardless of conversation length.
*   **Verifiability:** Provide a machine-readable trace for every decision made by the system.

## 4. Target Users / Stakeholders
*   **AI Engineers:** Requiring a robust, measurable RAG framework.
*   **Developers:** Needing a code-aware assistant that understands repository structure.
*   **Knowledge Workers:** Interacting with large, messy, and potentially contradictory document corpora.

## 5. Functional Requirements

### 5.1 Ingestion & Processing
*   **Resumable Pipeline:** Checkpointed ingestion that resumes from the last processed chunk.
*   **Two-Tier OCR:** 
    *   **Tier 1:** Tesseract for standard text.
    *   **Tier 2:** Mistral OCR API escalation for low-confidence pages ($<0.85$), garbage token detection ($>20\%$), or complex diagrams.
*   **Structure-Aware Chunking:** Table-aware chunking (never splits tables) and monospace-density detection for atomic code block preservation.

### 5.2 Indexing & Retrieval
*   **Hybrid Search:** Combination of `turbovec` quantized vector index (SIMD-accelerated) and BM25 keyword search.
*   **Superposed Multi-Query:** Parallel execution of up to 3 LLM-generated query interpretations fused via Reciprocal Rank Fusion (RRF).
*   **Reranking:** Cross-encoder reranking of top-50 candidates down to top-10.

### 5.3 Assessment Engine (The Gatekeeper)
*   **Triple Extraction:** Query-time extraction of (Subject, Relation, Object) triples from retrieved chunks.
*   **Contradiction Detection:** Identification of conflicting triples (same S+R, different O) with scope-awareness (e.g., "intern limits" vs "staff limits").
*   **Evidence Voting:** Programmatic weighting of sources; OCR outliers are flagged as potential errors rather than truths.

### 5.4 Self-Correction State Machine
*   **Confidence Bands:** 
    *   $\ge 0.75$: Direct answer with citations.
    *   $0.4 - 0.75$: Hedged response.
    *   $< 0.4$: Refusal with gap analysis.
*   **Correction Logic:** Automatic query rewriting (max 2 attempts), dual-answer delivery for contradictions, and multiple-choice clarification for ambiguity.

### 5.5 3-Plane Memory (DecisionGraph)
*   **X-Plane (Chat Spine):** Chronological turn nodes with lifecycle tracking (confidence, decay, supersede).
*   **Y+ Plane (Knowledge):** Semantic communities of document entities.
*   **Y- Plane (Code):** Structural call-graph communities via GitNexus (tree-sitter).
*   **Community Intelligence:** Louvain detection and LLM-generated "Compiled Truth" summaries per community.

### 5.6 Recall Engine
*   **Long-term Retrieval:** Scores past turns by $\text{Similarity} \times \text{Confidence}$.
*   **Neighborhood Walk:** Retrieves context from old conversations without replaying history.

### 5.7 Deployment & Interface
*   **MCP Server:** stdio-based server exposing 7 tools: `ask`, `recall`, `ingest_document`, `link_code_repo`, `rebuild_communities`, `graph_stats`, `live_view_url`.
*   **Visualization:** Embedded HTTP server streaming a live, auto-refreshing 3D graph view.

## 6. Non-Functional Requirements
*   **Performance:** SIMD-accelerated search and 4-bit quantization (31GB to 4GB reduction).
*   **Reliability:** Resumable ingestion and deterministic state machine for orchestration.
*   **Scalability:** $O(\text{neighborhood})$ graph traversal ensures performance does not degrade with history.
*   **Security:** Metadata filtering and down-weighting of chunks containing prompt-injection signatures.

## 7. System Architecture Overview
The system is organized into five layers:
1.  **Client Layer:** CLI, Eval Runner, and MCP Server.
2.  **Orchestration Layer:** Self-Correction Controller, Retrieval Engine, Assessment Engine, and Recall Engine.
3.  **Ingestion Layer:** Resumable pipeline with Tiered OCR.
4.  **Data Layer:** DecisionGraph-based 3-plane memory, Vector Index, and Metadata DB.
5.  **Model Layer:** Provider-agnostic LLM interface and local embedding models.

## 8. Tech Stack
*   **Languages:** Python (Core logic, `http.server` stdlib).
*   **Graph/Data:** NetworkX, SQLite, `dg-core`.
*   **Search:** `turbovec` (TurboQuant), `rank-bm25`, `sentence-transformers`.
*   **Parsing:** `tree-sitter` (GitNexus), `markitdown`, `Tesseract`, `Mistral OCR API`.
*   **Visualization:** `3d-force-graph (Three.js)`.
*   **Interface:** MCP SDK, Click.

## 9. Data Requirements
*   **Vector Store:** Quantized embeddings for semantic search.
*   **Metadata Store:** SQLite for provenance (file, page, OCR confidence).
*   **Triple Store:** Ephemeral in-memory store for query-time contradiction checks.
*   **Graph Store:** NetworkX/SQLite for the 3-plane DecisionGraph.

## 10. API Specifications (MCP Tools)
*   `ask(query)`: Triggers the self-correcting pipeline.
*   `recall(query)`: Searches global history for past compiled truths.
*   `ingest_document(path)`: Adds new messy docs to the corpus.
*   `link_code_repo(path)`: Triggers GitNexus structural parsing.
*   `live_view_url()`: Returns the URL for the 3D graph visualization.

## 11. Security Requirements
*   **Prompt Injection Mitigation:** Chunks containing injection traps are automatically down-weighted during retrieval.
*   **Local-First:** Embeddings and metadata are stored locally; external LLM calls are provider-agnostic and configurable via `.env`.

## 12. Deployment & Infrastructure
*   **Environment:** Python 3.10+, configured via `.env` (LLM_PROVIDER, API_KEY, BASE_URL).
*   **Server:** Python `http.server` for visualization streaming.
*   **Client:** Compatible with any MCP client (Claude Desktop, Cursor, etc.).

## 13. Success Metrics
Measured via a one-flag ablation (`--baseline` vs `--corrected`) on 15 gold questions at temperature 0:
*   **Hallucination Rate:** 20% → 7%
*   **Correct-Behavior Rate:** 67% → 87%
*   **Silent Arbitration (Contradictions):** 3/3 → 0/3 (System now cites both sides)
*   **Ambiguity Clarification:** 0/2 → 2/2
*   **Adversarial Battery:** Zero fabrications; planted $9,999 injection values never leaked.

## 14. Evaluation Harness
*   **Gold Dataset:** 15 questions across 5 categories:
    1.  **Answerable (5):** Direct facts in corpus.
    2.  **Unanswerable (3):** Facts absent from corpus.
    3.  **Contradictory (3):** Seeded with two conflicting policy versions.
    4.  **OCR-Dependent (2):** Facts hidden in low-quality scans.
    5.  **Ambiguous (2):** Vague queries requiring clarification.
*   **Trap Corpus:** Deliberately seeded with conflicting policies, scan-only facts, and code-in-PDF.
*   **Judge:** LLM judge at temperature 0 comparing output against expected-behavior labels.

## 15. Open Questions & Risks
*   **Honest Scope Note:** 
    *   **Implemented:** Full pipeline, 3-plane memory, MCP server, and evaluation harness.
    *   **Designed/Roadmap:** Supersede triggers (auto-forgetting), live file-watch incremental re-indexing (currently manual via GitNexus), table extraction, and multimodal encoders (CLIP/Whisper).
*   **Risk:** High-intensity Tier-2 OCR usage may impact cost/latency; mitigated by `MAX_TIER2_PAGES` budget cap.