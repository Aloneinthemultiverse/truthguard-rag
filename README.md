# TruthGuard RAG — Self-Correcting RAG Pipeline

**OneInbox AI Internship Hackathon 2026 · AI Engineer track · Problem Statement 1**

A RAG system over messy documents (native PDFs, scans needing OCR, code embedded in
PDFs) that **detects insufficient, contradictory, or ambiguous context and corrects
itself** — re-querying, dual-answering conflicts, asking clarifying questions, or
refusing with gap analysis — instead of hallucinating.

**Core thesis: the generator LLM is never called until retrieved context passes an
assessment gate. Hallucination is blocked structurally, not prompted away.**

## Quick start

```bash
pip install -r requirements.txt
# OCR engine (Tier 1):
winget install UB-Mannheim.TesseractOCR

cp .env.example .env      # set LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
                          # (any Anthropic-compatible endpoint)

python -m truthguard.make_corpus         # generate the seeded trap corpus
python -m truthguard.main ingest         # ingest + build index
python -m truthguard.main ask "What is the travel reimbursement limit per trip?"
python -m eval.run_eval --both           # baseline vs corrected ablation
```

## What to try (the traps)

| Ask | Watch it |
|---|---|
| `"What is the travel reimbursement limit per trip?"` | **dual-answer**: 2023 says $300, 2024 says $500 — cited, never arbitrated |
| `"Who is the CEO of DataHub Ltd?"` | rewrite loop → **refusal with gap analysis** |
| `"What is the penalty for filing an expense claim late?"` | answered **from a scanned page** (OCR, confidence shown in citation) |
| `"What does the retry_with_backoff function do?"` | code **quoted verbatim** from inside a PDF |
| `"What is the limit?"` | **multiple-choice clarifying question** |
| Add `--baseline` to any | the same pipeline with the correction layer off |

## Architecture (docs/ARCHITECTURE.md for the full picture)

```
ask -> RETRIEVE (multi-query, vector+BM25, RRF, cross-encoder rerank,
                 OCR/injection down-weighting)
    -> ASSESS  (sufficiency; query-time triple clash — scope-aware,
                unit-normalized, evidence-voted; answerability verdict)
    -> CORRECT (answer+cite / rewrite<=2 / dual-answer / clarify /
                refuse+gaps; confidence bands; trace log)
```

Ingestion: per-page **two-tier OCR ladder** (native -> Tesseract/PaddleOCR ->
Mistral OCR API escalation, budget-capped), code detection (fences/monospace/
symbol density, stored verbatim), structure-aware chunking, full provenance tags.

## Evaluation

15 gold questions across 5 categories (answerable / unanswerable / contradictory /
OCR-dependent / ambiguous), deliberately seeded traps (disclosed), LLM judge at
temp 0, and a **true one-flag ablation** — `--baseline` runs the identical binary
with assessment/correction bypassed. Results: `eval/results.md`.

## Repo layout

```
truthguard/        the pipeline (config, ocr, chunker, pipeline, chunk_store,
                   retrieve, assess, controller, llm, main, make_corpus)
eval/              gold.json, run_eval.py, results.md
corpus/            generated seeded documents
decisiongraph/     dg-core memory engine (substrate; decision memory, RRF, etc.)
docs/              PRD, architecture, solution overview, project master
```

Built on **dg-core** (DecisionGraph memory engine) with feature extraction from:
markitdown (Microsoft), PaddleOCR, turbovec (TurboQuant), GitNexus (triple-clash
pattern), gbrain (rerank + gap analysis patterns).
