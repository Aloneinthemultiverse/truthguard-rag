# Full-Stack Architecture — v2 (chunk-first)
## Self-Correcting RAG Pipeline

**Supersedes v1 (graph-first).** Backbone = provenance-tagged chunks in a quantized vector index; the knowledge graph is a query-time contradiction sidecar. Components marked ★NEW are built for the competition; the rest come from dg-core or pip.

---

## 1. System diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                 │
│    CLI main.py: ingest / ask / stats     eval/run_eval.py ★NEW            │
│                                          --baseline | --corrected        │
└────────────────┬─────────────────────────────────┬───────────────────────┘
                 ▼                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│               SELF-CORRECTION CONTROLLER ★NEW (controller.py)             │
│                                                                           │
│   ┌──────────┐    ┌──────────┐   verdict  ┌─────────────────────────────┐ │
│   │ RETRIEVE │───▶│  ASSESS  │───────────▶│ SUFFICIENT → ANSWER          │ │
│   └────▲─────┘    └──────────┘            │  + citations + confidence   │ │
│        │ rewritten     │                  │  (code chunks QUOTED verbatim)│ │
│        │ query         │                  ├─────────────────────────────┤ │
│   ┌────┴────────┐      │                  │ CONTRADICTORY → DUAL-ANSWER  │ │
│   │QUERY REWRITE│◀─────┘                  │  both sources cited, never  │ │
│   │(LLM, ≤2, must│                        │  arbitrate, ask which applies│ │
│   │differ)      │                         ├─────────────────────────────┤ │
│   └─────────────┘                         │ AMBIGUOUS → CLARIFY (1 re-run)│ │
│                                           ├─────────────────────────────┤ │
│   confidence = f(sim, verdict,            │ EXHAUSTED → REFUSE + GAP     │ │
│   contradiction, ocr_ratio)               │  ANALYSIS "covers X,Y; not Z"│ │
│   bands: ≥.75 / .4–.75 hedge / <.4 refuse └─────────────────────────────┘ │
│   trace log: every hop recorded → decision memory (audit)                 │
└──────────┬──────────────────────────────────┬─────────────────────────────┘
           ▼                                  ▼
┌───────────────────────────┐  ┌───────────────────────────────────────────┐
│  ASSESSMENT LAYER ★NEW    │  │           RETRIEVAL LAYER                 │
│  (assess.py)              │  │                                           │
│                           │  │ intent router (regex, dg-core)           │
│ 1 sufficiency: max chunk  │  │        │                                  │
│   sim vs threshold        │  │ superposed multi-query ★NEW: ≤3 LLM      │
│   (check_uncertainty      │  │ interpretations retrieved in parallel    │
│   pattern, dg-core)       │  │        │                                  │
│ 2 triple-clash ★NEW:      │  │ ┌──────▼──────┐   ┌──────────────────┐   │
│   triples from top-10     │  │ │ turbovec    │   │ BM25 keyword     │   │
│   chunks only (1 LLM) →   │  │ │ quantized   │   │ (rank-bm25)      │   │
│   same (subj,rel) diff    │  │ │ vector index│   │ ids·sections·code│   │
│   obj = clash (dict       │  │ └──────┬──────┘   └────────┬─────────┘   │
│   lookup, 0 LLM)          │  │        └── RRF fusion ─────┘ (dg-core)   │
│ 3 clash verify (1 LLM)    │  │                 │                        │
│ 4 answerability (1 LLM):  │  │   cross-encoder RERANK ★NEW top50→top10  │
│   SUFFICIENT|PARTIAL|     │  │                 │                        │
│   INSUFFICIENT|AMBIGUOUS  │  │   provenance weighting: low ocr% ↓       │
└───────────────────────────┘  └───────────────────────────────────────────┘
                                            │
                                            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        INDEX / MEMORY LAYER                               │
│                                                                           │
│  Chunk store ★NEW (chunk_store.py)          Decision memory (dg-core)    │
│   text + {file, page, native|ocr, ocr%,      every answer = living node: │
│   content_type, language}                    confidence · outcome ·      │
│   embeddings → turbovec (2/4-bit,            decay · supersede · links   │
│   ~16x smaller, SIMD; numpy fallback)        (the audit graph)           │
│                                                                           │
│  [optional --build-graph flag: ingest-time KG for corpus-wide            │
│   contradiction scan — post-M5 upgrade only]                             │
│  Storage: ./storage/<workspace>/ — pickle + SQLite, no external DB       │
└──────────────────────────────────────────────────────────────────────────┘
                                            ▲
                                            │
┌──────────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                                    │
│                                                                           │
│  files (PDF·DOCX·PPTX·XLSX·image·HTML)                                    │
│    → markitdown → Markdown (single downstream path)                       │
│    → scan detector ★NEW: page text <50 chars → TWO-TIER OCR ★NEW          │
│      T1: PaddleOCR local (per-box confidence %; pytesseract fallback)     │
│      T2: Mistral OCR API — DYNAMIC per-page escalation when T1 fails:     │
│      conf<0.85 | garbage≥20% | chart/diagram signature | image-heavy      │
│      → structured MD + figures (reason logged, MAX_TIER2_PAGES cap;       │
│      assess can retro-escalate a page on suspected OCR-error clash)       │
│    → Figure Asset Store ★NEW: diagrams as first-class assets              │
│      {asset_id, file, page, bbox, image, understanding_summary,           │
│       extracted_data, summary_embedding} — summaries retrievable like     │
│      chunks; chunks carry figure_refs; cite file·page·Figure N            │
│    → code detector ★NEW: md fences pass through; printed-PDF code via     │
│      monospace fonts + symbol density + keywords → verbatim, atomic       │
│    → structure-aware chunker ★NEW: heading splits, ~1000 chars,           │
│      never cuts fences/tables → provenance tags                           │
│    → checkpointed pipeline (dg-core): resume after crash                  │
└──────────────────────────────────────────────────────────────────────────┘
                                            ▲
┌──────────────────────────────────────────────────────────────────────────┐
│                          MODEL LAYER                                      │
│  LLM (Anthropic-compatible endpoint, .env) — used by: interpretations ·  │
│   triple extraction (query-time) · clash verify · answerability ·        │
│   rewrite · answer · eval judge (temp 0)                                  │
│  Embeddings: sentence-transformers MiniLM (local, lazy)                   │
│  Rerank: cross-encoder ms-marco-MiniLM (local)                            │
└──────────────────────────────────────────────────────────────────────────┘
```

## 2. Component inventory

| Layer | Component | File | Source |
|---|---|---|---|
| Ingest | Universal converter | markitdown (pip) | Microsoft |
| Ingest | Scan detect + two-tier OCR + confidence | `ocr.py` | ★NEW (PaddleOCR T1 / Mistral OCR T2) |
| Ingest | Figure Asset Store (diagram refs + summaries) | `figures.py` | ★NEW (Mistral OCR) |
| Ingest | Code detection (fences + monospace + density) | `chunker.py` | ★NEW |
| Ingest | Structure-aware chunker + provenance | `chunker.py` | ★NEW |
| Ingest | Checkpoint/resume | dg-core `ingest.py` pattern | dg-core |
| Index | Quantized vector index | turbovec (pip) + `chunk_store.py` | RyanCodrai / ★NEW |
| Index | BM25 | rank-bm25 + `chunk_store.py` | pip / ★NEW |
| Retrieve | Intent router | dg-core `query.py` | dg-core (gbrain #8) |
| Retrieve | Superposed multi-query | `retrieve.py` | ★NEW (quantum-inspired) |
| Retrieve | RRF fusion | dg-core `query.py` | dg-core (gbrain #2) |
| Retrieve | Cross-encoder rerank | `retrieve.py` | ★NEW (gbrain pattern) |
| Assess | Sufficiency | `assess.py` (check_uncertainty pattern) | dg-core |
| Assess | Triple-clash + verify | `assess.py` | ★NEW (GitNexus pattern) |
| Assess | Answerability verdict | `assess.py` | ★NEW |
| Correct | State machine + confidence + trace + gaps | `controller.py` | ★NEW (gaps: gbrain) |
| Memory | Decision audit graph | dg-core `decisions.py` | dg-core |
| Eval | Gold set + judge + ablation report | `eval/` | ★NEW |

## 3. One corrected query — sequence & LLM budget

```
question → intent (0) → interpretations ≤3 (LLM 1) → turbovec ∥ BM25 → RRF
→ rerank (local) → provenance weighting
→ ASSESS: sufficiency (0) · triples from top-10 (LLM 2) · clash lookup (0)
  · verify if clash (LLM 3) · answerability (LLM 4)
→ branch: answer (LLM 5) | rewrite (LLM 5) + loop | dual-answer (template)
  | clarify (template) | refuse + gaps (template)
→ trace + decision node stored
```
Typical 2–4 calls (no clash, no rewrite); hard cap 6.

## 4. Data model

```python
Chunk       {id, text, embedding_id, source_file, page,
             extraction: native|ocr, ocr_confidence: float|None,
             content_type: prose|code|table, language: str|None}
FigureAsset {asset_id, source_file, page, bbox, image_path,
             understanding_summary, extracted_data: dict|None,
             summary_embedding_id}   # chunks link via figure_refs
Assessment  {sufficiency: float,
             verdict: SUFFICIENT|PARTIAL|INSUFFICIENT|AMBIGUOUS,
             contradictions: [{subject, relation,
                               claims: [{object, source_chunk}] , severity}]}
Trace       [{step, action: retrieve|assess|rewrite|clarify|answer|
              dual_answer|refuse, detail, llm_calls}]
Response    {text, kind: answer|dual_answer|clarify|refusal,
             confidence: float, band: high|hedge|refuse,
             citations: [chunk_id → file·page·ocr%], gaps: [str]|None,
             trace: Trace}
GoldItem    {question, category: answerable|unanswerable|contradictory|
             ocr_dependent|ambiguous, gold_answer|None,
             expected: answer|refuse|dual_answer|clarify, gold_sources,
             scripted_followup: str|None}
Judgment    {label: correct|hallucinated|correctly_refused|
             incorrectly_refused|correctly_clarified|correct_dual_answer,
             rationale}
```

## 5. Design decisions (with rationale)

1. **Chunk-first, not graph-first.** Triple extraction is lossy for precise policy text and costs 1 LLM call/chunk at ingest; passages with citations are what "RAG" means to evaluators. The graph earns its place only where it beats vectors.
2. **Graph = query-time contradiction sidecar.** Clash = same (subject, relation) → different objects: a dictionary lookup over ~10 chunks' triples, not O(n²) LLM passage comparison. ~95% ingest-cost reduction vs v1.
3. **Assess before generate.** The generator never sees failed context — hallucination blocked structurally.
4. **Never arbitrate contradictions.** Always dual-answer with citations; silent side-picking is the failure mode being eliminated.
5. **Provenance as signal.** OCR confidence propagates page → chunk → retrieval weight → answer confidence band.
6. **Superposed multi-query.** Ambiguous questions retrieved under ≤3 interpretations in parallel; RRF = interference; collapse at assessment or CLARIFY. (Quantum-inspired framing: one sentence in writeup, no hardware claims.)
7. **turbovec for scale story.** 31GB→4GB class compression, SIMD search, no training; numpy float32 fallback behind the same interface so it can never block the demo.
8. **Hard-capped loops.** Max 2 rewrites, each string-checked different; bounded cost, guaranteed termination.
9. **Baseline = same binary, one flag.** True ablation; the measured delta is attributable to the correction layer alone.
10. **Code is quoted, never paraphrased.** Detected via fences/monospace/density; stored atomic; identifiers keyword-indexed.

## 6. Relation to the 3-plane vision (post-competition)

This build constructs the **knowledge plane (y+)**: provenance chunks + turbovec + decision memory. Adding a conversation spine (x) and a GitNexus-style code plane (y−), cross-linked `grounds`/`references`, exposed over MCP so any model shares one memory → the context OS where the window holds O(neighborhood) instead of O(history). Captured separately; zero competition scope.
