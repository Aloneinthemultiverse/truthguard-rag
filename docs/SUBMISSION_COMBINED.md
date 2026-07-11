# SUBMISSION BUNDLE — Self-Correcting RAG (Problem Statement 1, AI Engineer track)

---

# Product Requirements Document (PRD) — v2
## Self-Correcting RAG Pipeline — "TruthGuard RAG"


> **IMPLEMENTATION STATUS (July 11):** this design is BUILT and MEASURED — not a proposal.
> Working system in `truthguard/` (repo: github.com/Aloneinthemultiverse/truthguard-rag).
> Eval via one-flag ablation: **hallucination 20%→7%, correct behavior 67%→93%, silent
> arbitration 3/3→0/3**. Hard-test battery (15 adversarial cases incl. prompt injection):
> zero fabrications. Implemented beyond the plan: figure/image references (FR-1.7),
> the 3-plane Session Context Graph (each plane built with DecisionGraph's own community
> recipe: 41 y+ semantic communities, 5 x topic communities, GitNexus y− clusters),
> GitNexus symbol linking with zero-LLM structural answers, and 2D + 3D interactive
> graph visualizations (`truthguard/viz.py`, `viz3d.py`).


**Version:** 2.0 (chunk-first redesign) · **Date:** 2026-07-08 · **Status:** Locked for build
**Base:** dg-core (DecisionGraph memory core) · **Supersedes:** v1 (graph-first design)
**Changes from v1:** knowledge graph demoted from ingest-time co-primary index to query-time contradiction sidecar; markitdown replaces document_handlers as front door; PaddleOCR (confidence-tagged) replaces bare pytesseract; turbovec replaces hand-rolled quantization; added rerank, superposed multi-query, gap-analysis refusals, code-in-PDF handling.

---

## 1. Problem Statement

Standard RAG answers every question with equal confidence. Four failure modes:

| # | Failure | Mechanism |
|---|---|---|
| P1 | **Blindness** | Scanned pages have no text layer; the retriever never sees them |
| P2 | **Omission hallucination** | Answer not in corpus; LLM fabricates from partial context |
| P3 | **Silent arbitration** | Two docs conflict; LLM picks one side without disclosure |
| P4 | **Ambiguity guessing** | Underspecified question; system guesses intent |

Core thesis: **hallucination must be prevented structurally, not prompted away** — the generator LLM is never invoked until retrieved context passes an assessment gate.

## 2. Goal

RAG over a messy corpus (native PDFs, scans requiring OCR, DOCX/MD/TXT, inconsistent formatting, code embedded in documents) that detects insufficient/contradictory/ambiguous context and re-queries, clarifies, dual-answers, or refuses with useful gap analysis — proven by an ablation eval harness comparing hallucination rates with the correction layer off vs on.

## 3. Non-Goals

Multi-tenant workspaces, agent marketplace, MCP platform, code-graph tooling (all cut from parent Decision_Graph). Ingest-time full knowledge-graph build (demoted; optional `--build-graph` flag only if time remains). Real-time ingestion. Fine-tuning. Production auth/scaling. The 3-plane context OS (post-competition roadmap only).

## 4. Functional Requirements

### FR-1 Ingestion (messy documents)
- **FR-1.1** Front door: **markitdown** converts PDF/DOCX/PPTX/XLSX/images/HTML → clean Markdown; single downstream path.
- **FR-1.2** Scan detection: PDF pages whose text layer yields <50 chars with rendered content → OCR via **PaddleOCR** (pytesseract fallback behind the same interface). Per-box OCR **confidence %** captured.
- **FR-1.3** Code detection: markdown fences pass through; printed-PDF code detected by monospace-font runs (pdfplumber font names) + symbol density + keyword hits. Code chunks: `content_type=code`, stored verbatim, atomic (never split), never triple-extracted; identifiers indexed as keywords.
- **FR-1.4** Structure-aware chunking: split on headings, ~1000 chars, never cuts code fences or tables. Every chunk tagged `{source_file, page, extraction: native|ocr, ocr_confidence, content_type, language}`.
- **FR-1.5** Checkpointed, resumable ingest (dg-core): crash at chunk N resumes at N.
- **FR-1.6** **Dynamic two-tier OCR (per-page escalation ladder)**: (1) native text layer if present (free); (2) Tier 1 PaddleOCR locally; (3) accept Tier 1 when mean box confidence ≥0.85 AND garbage-token ratio <20%; (4) escalate that page to Tier 2 **Mistral OCR API** when any trigger fires: low confidence, garbage output, chart/diagram signature (high ink, low text coverage), embedded images above area threshold. Escalation is per-PAGE not per-document; the reason is stored in provenance (`escalated_because`); ingestion report tallies tier usage + estimated API cost; `MAX_TIER2_PAGES` budget cap (beyond cap → Tier 1 output with low-confidence tags, downstream hedging handles honesty); no API key → ladder stops at Tier 1, nothing breaks.
- **FR-1.6b** **Retroactive escalation**: if assessment later flags a possible-OCR-error contradiction on a Tier 1 page, the controller may re-OCR that single page via Tier 2 and re-run the clash check — self-correction extending back into ingestion.
- **FR-1.7** **Figure Asset Store**: every diagram/chart extracted as a first-class asset `{asset_id, source_file, page, bbox, image_path, understanding_summary, extracted_data, summary_embedding}`. Figure summaries are retrievable like chunks; prose chunks carry `figure_refs`; answers cite `file · page · Figure N` and the UI can display the actual figure beside the answer.
- **FR-1.8** **No-migration onboarding**: our chunk/asset format is an INDEX, not a system of record. Organizations keep their existing databases/DMS; ingestion connectors copy + enrich (provenance, figure summaries) one-time, answers always reference back to the original source. Source changes → re-ingest that document only (O(doc), per FR-6.1).

### FR-2 Index & Retrieval
- **FR-2.1** Vector index: MiniLM embeddings in **turbovec** (TurboQuant quantization: 2/4-bit, ~16x compression, SIMD search, filtered search). Float32 numpy fallback behind the same interface.
- **FR-2.2** BM25 keyword index (exact terms: IDs, section numbers, code identifiers).
- **FR-2.3** Intent router (regex, zero-LLM): temporal/entity/event/general.
- **FR-2.4** **Superposed multi-query** (quantum-inspired): LLM generates ≤3 interpretations of the question; all retrieved in parallel; RRF fusion is the interference step; interpretation "collapses" at assessment or triggers CLARIFY.
- **FR-2.5** RRF fusion of all rankings (vector + keyword × interpretations).
- **FR-2.6** Cross-encoder **rerank**: top-50 fused → top-10.
- **FR-2.7** Provenance-aware weighting: low `ocr_confidence` chunks down-weighted.

### FR-3 Assessment (detect — no generation yet)
- **FR-3.1** Sufficiency: max chunk similarity vs threshold (from dg-core `check_uncertainty` pattern, applied to chunk embeddings); below → INSUFFICIENT.
- **FR-3.2** Contradiction, heuristic: extract triples **from the retrieved top-10 only** (1 LLM call); clash = same (subject, relation) with different objects — dictionary lookup, zero extra LLM.
- **FR-3.3** Contradiction, verify: 1 LLM call over clash candidates → `{contradictory, claims:[{statement, source}], severity}`.
- **FR-3.4** Answerability: 1 LLM call → SUFFICIENT | PARTIAL | INSUFFICIENT | AMBIGUOUS_QUESTION.

### FR-4 Self-Correction Controller
- **FR-4.1** State machine: SUFFICIENT → answer + citations; INSUFFICIENT/PARTIAL → LLM query rewrite (must differ from all prior queries, string-checked) → re-retrieve, **max 2 rewrites**; CONTRADICTORY → dual-answer citing both sources, never arbitrate, ask which context applies; AMBIGUOUS → clarifying question (follow-up re-runs once); EXHAUSTED → refusal + **gap analysis** ("corpus covers X, Y; nothing on Z").
- **FR-4.2** Confidence: `f(retrieval_sim, answerability, contradiction_flag, ocr_ratio)` ∈ [0,1]; bands ≥0.75 answer / 0.4–0.75 hedge / <0.4 refuse. Score + band on every response.
- **FR-4.3** Trace: machine-readable hop log on every response; answers replayable.
- **FR-4.4** Code answers: retrieved code chunks quoted verbatim, never paraphrased; cited as file · page · code block.
- **FR-4.5** Every answer stored as a decision node (dg-core memory: confidence, outcome slot, decay, supersede) — the audit trail.

### FR-5 Evaluation Harness
- **FR-5.1** Gold set: **15 questions** — answerable 5, unanswerable 3, contradictory 3, OCR-dependent 2, ambiguous 2. Each: `{question, category, gold_answer|null, expected: answer|refuse|dual_answer|clarify, gold_sources}`.
- **FR-5.2** Seeded corpus: deliberately planted traps — two conflicting policy versions, one scan-only fact, absent topics, an ambiguous term, code inside a PDF. Disclosed openly in the writeup.
- **FR-5.3** True ablation: `--baseline` bypasses FR-3/FR-4 on the SAME binary; `--corrected` runs full pipeline.
- **FR-5.4** LLM judge (temp 0, rubric + few-shot anchors): correct | hallucinated | correctly_refused | incorrectly_refused | correctly_clarified | correct_dual_answer. All 15 hand-checked.
- **FR-5.5** Report: per-question table + hallucination rate, correct-behavior rate, refusal precision for both modes → `eval/results.md` + JSON.

## 5. Non-Functional Requirements

| NFR | Target |
|---|---|
| Query latency (corrected) | ≤30s p95 incl. 2 correction loops |
| LLM cost | 2–4 calls typical, hard cap 6 |
| Ingest resumability | checkpoint every 50 chunks |
| Eval determinism | judge temp 0, fixed gold set, seeds logged |
| Footprint | pure Python + turbovec (pip); no external DB; pickle/SQLite |
| Traceability | every answer reproducible from trace + chunk ids |

### 5.1 Scalability (how this design grows from demo corpus to production)

| Axis | Mechanism | Headroom |
|---|---|---|
| **Corpus size** | turbovec 2/4-bit quantization: 10M docs ≈ 31GB float32 → **~4GB**, SIMD brute-force search (no HNSW build/rebuild cost, no training phase) | demo: hundreds of chunks → production: 10M+ chunks on one commodity box |
| **Ingest throughput** | per-document independent pipeline (embarrassingly parallel); checkpoint/resume; incremental adds are O(new doc) with stable IDs | horizontal: N workers ingest N docs concurrently, no coordination needed |
| **OCR cost** | dynamic per-PAGE escalation ladder — native (free) → PaddleOCR (local, free) → Mistral OCR API only on trigger; `MAX_TIER2_PAGES` budget cap | cost scales with *hard pages*, not corpus size; tallied per ingest report |
| **Query path** | stateless per query (retrieve → assess → correct); no session affinity; LLM calls capped at 6 | horizontal replicas behind a load balancer; latency dominated by LLM API, not our pipeline |
| **LLM cost** | assessment prompts see only top-10 chunks (bounded context); triples extracted at query time from retrieved chunks only (not per corpus chunk — ~95% cheaper than ingest-time graph) | cost per query is O(1) w.r.t. corpus size |
| **Multi-tenancy** | per-workspace storage isolation inherited from DecisionGraph (`storage/<workspace>/`) — separate index, memory, and audit graph per tenant | tenant count scales with disk, not with architectural change |
| **Freshness at scale** | supersede/decay run lazily (once/day, zero-LLM); contradiction surfacing is query-time so stale data can't hide regardless of corpus size | maintenance cost stays flat |

Bottleneck honesty: the single scaling wall is LLM API rate limits under high QPS — mitigated by capped calls/query, response caching being deliberately absent only at the *answer* level (retrieval-layer caching of embeddings is free), and provider failover being a config swap (any Anthropic-compatible endpoint).

## 6. Success Metrics

| Metric | Baseline | Target |
|---|---|---|
| Hallucination on unanswerable Qs | ~80–100% | ≤10% |
| Silent arbitration on contradictions | ~100% | 0% |
| Recall on OCR-dependent Qs | ~0% | ≥80% |
| Overall correct-behavior rate | ~40% | ≥85% |
| Wrong refusals | — | ≤1/15 |

## 7. Milestones

| M | Deliverable | Demo proof |
|---|---|---|
| 1 | Seeded corpus + gold set | show planted traps |
| 2 | Ingest (markitdown + PaddleOCR + chunker) | chunks with provenance tags |
| 3 | Index + retrieve (turbovec + BM25 + RRF + rerank) | question → top-10 cited passages |
| 4 | Assess layer | planted contradiction auto-flagged |
| 5 | Controller | rewrite / dual-answer / clarify / refuse+gaps live, trace visible |
| 6 | Eval harness + report | before/after hallucination table |

Post-M5 upgrades only if time: superposed multi-query, rerank tuning, `--build-graph` (corpus-wide contradiction scan), deepwiki-style corpus wiki.

**Cut order under time pressure:** corpus wiki → superposed multi-query → turbovec (→ numpy) → rerank → PaddleOCR (→ pytesseract). **Never cut:** controller, dual-answer, eval table.

## 8. Growth & Freshness Requirements

- **FR-6.1** Incremental ingest: adding a document is O(new doc) — stable vector IDs (turbovec IdMapIndex), no corpus re-processing.
- **FR-6.2** No answer caching: every query re-retrieves; new knowledge is live immediately.
- **FR-6.3** Staleness surfacing: conflicting facts (old vs new doc) MUST trigger the contradiction path (dual-answer) — the system never silently serves either version. *(Competition scope — same mechanism as FR-3.2/3.3.)*
- **FR-6.4** Supersede: confirmed-stale chunks/decisions marked inactive with a `supersedes` link; excluded from retrieval, retained in immutable timeline. *(Decisions: free via dg-core. Chunks: post-M5.)*
- **FR-6.5** Decay: unaccessed content loses confidence over time (dg-core dream cycle); retrieval scores similarity × confidence. *(Post-M5 for chunks.)*
- **FR-6.6** Recency tiebreak among non-contradicting chunks via provenance dates. *(Post-M5.)*

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| PaddleOCR install friction | pytesseract fallback behind one OCR interface |
| turbovec immaturity | float32 numpy fallback behind one index interface |
| LLM judge bias | temp 0, rubric, few-shot anchors, hand-check all 15 |
| Correction loop oscillation | max 2 rewrites; rewrite must differ (string check) |
| Over-refusal | refusal precision first-class metric; tune threshold on answerable slice |
| Lossy triples | triples used ONLY for clash detection, never for answering |
| Scope creep | 3-plane vision hard-parked in vision doc |
| Demo failure live | corpus pre-ingested before demo; never ingest live |

## 10. Resolved Questions (were open in v1)

1. Judge model → temp-0 + rubric + hand-check (small set makes this feasible).
2. Clarification UX → returned question object; eval supplies scripted follow-ups.
3. Dual-answers count as correct **only if both sources cited** → yes.
4. GraphRAG vs plain RAG → chunk-first backbone; graph = query-time contradiction sidecar only.
5. Quantization → turbovec (adopted); 0xsero/turboquant rejected (KV-cache/inference domain, not document retrieval).



---

# Full-Stack Architecture — v2 (chunk-first)
## Self-Correcting RAG Pipeline


> **IMPLEMENTATION STATUS (July 11):** this design is BUILT and MEASURED — not a proposal.
> Working system in `truthguard/` (repo: github.com/Aloneinthemultiverse/truthguard-rag).
> Eval via one-flag ablation: **hallucination 20%→7%, correct behavior 67%→93%, silent
> arbitration 3/3→0/3**. Hard-test battery (15 adversarial cases incl. prompt injection):
> zero fabrications. Implemented beyond the plan: figure/image references (FR-1.7),
> the 3-plane Session Context Graph (each plane built with DecisionGraph's own community
> recipe: 41 y+ semantic communities, 5 x topic communities, GitNexus y− clusters),
> GitNexus symbol linking with zero-LLM structural answers, and 2D + 3D interactive
> graph visualizations (`truthguard/viz.py`, `viz3d.py`).


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



---

# Solution Overview — Self-Correcting RAG Pipeline (v2)

## The one-paragraph pitch


> **IMPLEMENTATION STATUS (July 11):** this design is BUILT and MEASURED — not a proposal.
> Working system in `truthguard/` (repo: github.com/Aloneinthemultiverse/truthguard-rag).
> Eval via one-flag ablation: **hallucination 20%→7%, correct behavior 67%→93%, silent
> arbitration 3/3→0/3**. Hard-test battery (15 adversarial cases incl. prompt injection):
> zero fabrications. Implemented beyond the plan: figure/image references (FR-1.7),
> the 3-plane Session Context Graph (each plane built with DecisionGraph's own community
> recipe: 41 y+ semantic communities, 5 x topic communities, GitNexus y− clusters),
> GitNexus symbol linking with zero-LLM structural answers, and 2D + 3D interactive
> graph visualizations (`truthguard/viz.py`, `viz3d.py`).


Most RAG systems have one move: retrieve, then answer — confidently, every time, even when the corpus doesn't contain the answer, contradicts itself, or the relevant page is a scan the retriever never read. Our system adds a **metacognitive layer**: after every retrieval it *assesses* its own context (Is this sufficient? Do my sources disagree? Is the question even unambiguous?) and then *chooses* the honest action — answer with citations, re-query with a rewritten search, surface both sides of a contradiction, ask a clarifying question, or refuse with a gap analysis of what the corpus is missing. An ablation-style evaluation harness over a deliberately seeded messy corpus (planted contradictions, scanned-only facts, code inside PDFs, unanswerable questions) measures hallucination rates with the layer switched off vs. on — same binary, one flag.

## Why this design wins

**1. Hallucination is prevented structurally, not prompted away.**
The generator LLM is never invoked until the context passes an assessment gate. "Please don't hallucinate" prompts fail; a controller that refuses to call the generator on bad context cannot fabricate.

**2. It handles all four failure modes, each with its own detector and its own corrective action.**
- *Blindness* (scans invisible) → per-page text-density detection routes pages through PaddleOCR; per-box **confidence % propagates** page → chunk → retrieval weight → final answer confidence band.
- *Omission* (answer not in corpus) → sufficiency check + answerability judgment → query-rewrite loop (max 2, each rewrite string-checked different) → explicit refusal.
- *Arbitration* (sources conflict) → triple-clash detection → **dual-answer citing both sources; the system never silently picks a side**.
- *Guessing* (ambiguous question) → AMBIGUOUS verdict → clarifying question; the follow-up re-runs the loop once.

**3. Contradiction detection is structurally cheap — our differentiator.**
Triples are extracted **only from the ~10 retrieved chunks at query time** (one LLM call, not one per corpus chunk). "Two docs disagree" then reduces to *same subject + same relation, different object* — a dictionary lookup, not an O(n²) LLM comparison. Vector-only pipelines cannot see disagreement at all; this is the hard part of the brief and the part most competing solutions will skip.

**4. Refusals are useful, not dead ends.**
A failed answer returns **gap analysis**: "the corpus covers X and Y; it contains nothing on Z, which your question requires" — plus the closest topic it *does* know. (Pattern adopted from gbrain, whose measured +31.4 P@5 from graph-enabled retrieval also independently validates keeping a graph layer where it beats vectors.)

**5. Retrieval is state-of-practice, not exotic.**
markitdown normalizes every format to Markdown (code arrives as fenced blocks free of charge; printed-PDF code is caught by monospace-font detection and always **quoted verbatim, never paraphrased**). Chunks with full provenance go into **turbovec** — Google's TurboQuant quantization, 31GB→4GB-class compression, SIMD search faster than FAISS — plus BM25 for exact terms, fused with Reciprocal Rank Fusion, sharpened by a cross-encoder rerank. Ambiguous questions are retrieved under up to 3 parallel interpretations ("superposed" multi-query — fusion acts as the interference step, and the interpretation collapses at assessment or triggers a clarifying question).

**6. Every answer is auditable.**
Each response carries a machine-readable trace (`retrieve → assess:INSUFFICIENT → rewrite:"…" → assess:SUFFICIENT → answer`), citations to chunk-level provenance (file · page · native/OCR · confidence), a numeric confidence with bands (≥0.75 answer / 0.4–0.75 hedge / <0.4 refuse), and is stored as a node in a persistent decision memory (confidence, outcome, decay, supersede) — the audit trail doubles as institutional memory.

**7. The evaluation is a true ablation.**
`--baseline` runs the *identical* pipeline with assessment/correction bypassed — same retriever, same generator, same corpus, one flag. The measured delta in hallucination rate is attributable purely to the self-correction layer. The corpus traps are seeded deliberately and disclosed openly.

## How it works, end to end

**Ingest (once).** Mixed documents → markitdown → Markdown. Pages with no text layer → PaddleOCR with confidence tags. Code detected (fences / monospace fonts / symbol density) → stored verbatim and atomic. Structure-aware chunking (heading-based, never splits code or tables) with provenance tags `{file, page, native|ocr, ocr%, content_type}`. Checkpointed — a crash resumes, not restarts.

**Index (once).** MiniLM embeddings quantized into turbovec; BM25 over the same chunks; code identifiers keyword-indexed.

**Retrieve (per question).** Intent routing (regex, free) → up to 3 question interpretations retrieved in parallel → RRF fusion → cross-encoder rerank to top-10 → low-confidence OCR down-weighted.

**Assess (per question — nothing generated yet).** Four checks, cheapest first: embedding sufficiency; query-time triple extraction over the top-10; clash dictionary lookup; LLM verify on candidates; LLM answerability verdict (SUFFICIENT / PARTIAL / INSUFFICIENT / AMBIGUOUS).

**Correct.** The state machine routes: answer + citations + confidence · rewrite-and-retry (≤2) · dual-answer with both sources · clarifying question · refusal with gap analysis. Typical cost 2–4 LLM calls, hard cap 6.

**Remember.** Every answer becomes a decision node with confidence and an outcome slot in persistent memory.

**Evaluate.** 15 gold questions (5 answerable / 3 unanswerable / 3 contradictory / 2 OCR-dependent / 2 ambiguous) with expected-behavior labels and scripted clarification follow-ups; LLM judge at temperature 0 with rubric; per-question table + hallucination rate, correct-behavior rate, and refusal precision for baseline vs corrected.

## Expected headline result

| Metric | Baseline | Self-corrected |
|---|---|---|
| Hallucination on unanswerable questions | ~80–100% | **≤10%** |
| Silent arbitration on contradictions | ~100% | **0%** |
| Recall on OCR-dependent facts | ~0% | **≥80%** |
| Overall correct-behavior rate | ~40% | **≥85%** |

## Foundation and provenance

The substrate is **dg-core** — the memory engine extracted from the DecisionGraph project — contributing checkpointed ingestion, keyword+RRF hybrid retrieval, the intent router, the `check_uncertainty` sufficiency pattern, and the decision-memory audit graph. Feature extraction, not dependency stacking: **markitdown** (Microsoft) normalizes formats; **PaddleOCR** reads scans with confidence; **turbovec** (TurboQuant) compresses the index; **GitNexus**'s graph pattern powers contradiction detection; **gbrain** contributes the rerank stage and gap-analysis refusals (four more of its patterns arrived pre-inherited inside dg-core). Deliberately rejected: 0xsero/turboquant (KV-cache compression — inference domain, not document retrieval), FreeOCR-AI (redundant), heavyweight frameworks (no LangChain — every component is explainable). Pure Python, local embeddings, any Anthropic-compatible LLM endpoint, no external database.

## Deliverables map

| Competition requirement | Where satisfied |
|---|---|
| RAG over messy docs (PDF + OCR + inconsistent formatting) | markitdown + `ocr.py` + `chunker.py` |
| Code embedded in documents | fence/monospace detection; verbatim atomic storage; quote-don't-paraphrase rule |
| Detect insufficient context | sufficiency check + answerability verdict (`assess.py`) |
| Detect contradictory context | query-time triple-clash + LLM verify (`assess.py`) |
| Intelligently re-query | rewrite loop, ≤2, dedup-checked (`controller.py`) |
| Ask clarifying questions | AMBIGUOUS branch + scripted follow-up re-run (`controller.py`) |
| Explicit low-confidence responses | confidence bands + refusal with gap analysis (`controller.py`) |
| Eval harness, 10–15 questions | `eval/gold.json` — 15 Qs, 5 categories, seeded traps disclosed |
| Hallucination rate before vs after | `eval/run_eval.py --baseline` vs `--corrected` → `eval/results.md` |

## How it grows — and stays out of outdated data

**Growth is append-only and O(new doc):** each document ingests independently (stable turbovec IDs, cheap BM25 re-index, checkpointed batches), and since nothing is cached at the answer level, new knowledge is live on the very next question — yesterday's gap-analysis refusal even names what to ingest next.

**Staleness cannot hide:** when a new document contradicts an old one, the triple-clash check fires at query time and the system dual-answers with both sources — it is structurally incapable of silently serving the stale version. Confirmed-stale content is **superseded** (inactive, linked `supersedes`, out of retrieval) into an immutable timeline rather than deleted — history stays queryable. Unused knowledge additionally **decays**: retrieval scores similarity × confidence, and confidence erodes on content untouched for 90 days (dg-core dream cycle), with recency as the tiebreak among non-conflicting chunks.

## After the competition

This build is milestone zero of the 3-plane context OS: the provenance chunk store + turbovec + decision memory **is** the knowledge plane (y+). Adding a conversation spine (x) and a GitNexus-style code plane (y−), cross-linked and exposed over MCP so Claude/Gemini/GPT share one memory, turns the competition artifact into a system where the context window holds a neighborhood, not a history.



---

# PROJECT MASTER — Self-Correcting RAG ("TruthGuard RAG")
### The complete A→Z of everything we've designed

**Date:** 2026-07-08 · **Base:** dg-core (extracted DecisionGraph memory core)
**Competition brief:** RAG over messy unstructured docs (mixed PDFs, scans needing OCR, inconsistent formatting) that detects insufficient/contradictory context and re-queries, clarifies, or returns low-confidence responses instead of hallucinating — with a 10–15 question eval harness comparing hallucination rates before/after the self-correction layer.

---

## A. The problem, decomposed

Standard RAG has one move — retrieve, then answer — and it answers *confidently every time*. Four distinct failure modes:

| # | Failure | Mechanism | Example |
|---|---|---|---|
| P1 | **Blindness** | Scanned pages have no text layer; retriever never sees them | Penalty clause exists only in a scanned appendix → "no information" or invented penalty |
| P2 | **Omission hallucination** | Answer isn't in the corpus; LLM fabricates from partial context | "Who is vendor X's CEO?" → invents a name |
| P3 | **Silent arbitration** | Two docs conflict; LLM picks one without telling you | 2023 policy says $300, 2024 says $500 → answers "$300", no warning |
| P4 | **Ambiguity guessing** | Question underspecified; system guesses intent | "What's the limit?" → answers for the wrong category |

Enterprise reality: a confidently wrong answer is worse than "I don't know."

## B. The core insight (our thesis)

**Hallucination must be prevented structurally, not prompted away.** The generator LLM is never called until the retrieved context passes an assessment gate. A model that isn't invoked on bad context cannot fabricate from it. Everything else in the design serves this gate.

Second insight: **each failure mode needs a different detector and a different corrective action** — one "confidence score" is not enough. Insufficient → rewrite & retry. Contradictory → show both sides. Ambiguous → ask. Exhausted → refuse *usefully*.

## C. Solution in one flow

```
question
 → intent routing (regex, free)
 → SUPERPOSED RETRIEVAL: 3 LLM interpretations of the question, retrieved in
   parallel (quantum-inspired multi-query; RRF fusion = the interference step)
   over turbovec (quantized vectors) + BM25 → RRF → cross-encoder rerank → top-10
 → ASSESS (no generation yet):
     1. sufficiency: max chunk similarity below threshold? (embeddings only)
     2. contradiction: extract triples FROM THE 10 RETRIEVED CHUNKS (1 LLM call),
        clash = same (subject, relation) → different objects → 1 verify call
     3. answerability: SUFFICIENT | PARTIAL | INSUFFICIENT | AMBIGUOUS (1 LLM call)
 → CORRECT (state machine, hard caps):
     SUFFICIENT     → answer + citations (file·page·ocr%) + confidence score
     INSUFFICIENT   → LLM rewrites query (must differ from prior) → loop, max 2
     CONTRADICTORY  → dual-answer: "Source A (p.3) says X; Source B (p.5) says Y
                      — which context applies?" NEVER arbitrate.
     AMBIGUOUS      → clarifying question; follow-up re-runs once
     EXHAUSTED      → refusal + GAP ANALYSIS: "corpus covers X,Y; nothing on Z"
 → trace log (every hop) + decision-memory node (question, answer, confidence,
   outcome slot)
```
Cost: 2–4 LLM calls typical, hard cap 6.

## D. Feature inventory — all 18, with source attribution

### Ingest (once)
1. **markitdown** (Microsoft) — universal converter: PDF/DOCX/PPTX/image/HTML → clean Markdown. One downstream path; code arrives as fenced blocks — answers "what if the PDF has code?" for free (code chunks stored verbatim, never triple-extracted, quoted not paraphrased in answers).
2. **Two-tier OCR** — Tier 1: **PaddleOCR** (local, free, per-box confidence %) for plain scanned text. Tier 2: **Mistral OCR API**, escalated **dynamically per page** — triggers: Tier 1 confidence <0.85, garbage-token ratio ≥20%, chart/diagram signature (high ink / low text), image-heavy page — returning structured Markdown + extracted figures. Escalation reason stored in provenance; ingestion report tallies tier usage + cost; `MAX_TIER2_PAGES` budget cap; offline = Tier 1 only, nothing breaks. Assessment can **retroactively escalate** a single page when it suspects an OCR-error contradiction. Solves P1 fully, including the charts/handwriting edge case (#12 — upgraded from "deferred" to solved-in-design).
   **Figure Asset Store:** every diagram/chart becomes a first-class asset `{asset_id, file, page, bbox, image, understanding_summary, extracted_data, summary_embedding}` — figure summaries are retrievable like chunks, prose chunks carry `figure_refs`, answers cite `file · page · Figure N`, and the UI shows the actual diagram beside the answer.
   **No-migration onboarding:** our format is an INDEX, not a system of record — organizations keep their databases/DMS; connectors copy + enrich once (provenance, figure summaries); every answer references back to the original source; changed source docs re-ingest individually (O(doc)).
3. **Structure-aware chunker** (ours) — split on headings ~1000 chars; never cuts code fences/tables; every chunk tagged `{file, page, native|ocr, ocr%, content_type, language}`.
   **Code detection for printed PDFs:** beyond markdown fences, code blocks inside PDFs are detected via (a) monospace-font runs (pdfplumber exposes font names), (b) symbol-density ratio (`{};()=>`), (c) keyword hits (`def|class|function|import|return`). Detected code → `content_type: code`, stored **verbatim and atomic** (never split mid-block), never triple-extracted; identifiers (function/class names) added as keyword-searchable terms. **Generation rule:** when a code chunk is retrieved, the generator must QUOTE it, never paraphrase; citation shows file · page · "code block".
4. **Checkpointed extraction** (dg-core) — crash at chunk N resumes at N.

### Index (once)
5. **turbovec** (RyanCodrai; Google TurboQuant algorithm) — quantized vector index: 10M docs 31GB float32 → 4GB, SIMD search faster than FAISS, no training phase, filtered search. Rust + pip.
6. **BM25 keyword index** (dg-core) — exact terms vectors miss: IDs, section numbers, function names.

### Retrieve (per query)
7. **Intent router** (dg-core, gbrain #8 pattern) — regex classifier, zero LLM.
8. **Superposed multi-query** (ours, quantum-inspired) — 3 interpretations retrieved in parallel; fusion interferes them; ambiguity "collapses" at assessment or triggers clarify.
9. **RRF fusion** (dg-core, gbrain #2 pattern) — merges all rankings, no tuning.
10. **Cross-encoder rerank** (gbrain pattern) — top-50 → top-10; gbrain measured +31.4 P@5 from graph+rerank.

### Assess (per query — the "detect" layer)
11. **check_uncertainty** (dg-core) — corpus-level sufficiency; refuses off-topic early.
12. **Triple-clash contradiction detection** (GitNexus graph pattern) — query-time triples from retrieved chunks only; clash = dictionary lookup; 1 verify call. Solves P3.
13. **Answerability verdict** (ours) — one LLM call, 4-way verdict. Solves P2/P4 detection.

### Correct (per query — the "self-correction" layer)
14. **Controller state machine** (ours) — the five branches, retry caps, dedupe of rewrites.
    **Confidence score formula:** `confidence = f(retrieval_similarity, answerability_verdict, contradiction_flag, ocr_ratio)` ∈ [0,1] — e.g. weighted product: top-chunk sim × verdict weight (SUFFICIENT 1.0 / PARTIAL 0.7) × (0.5 if unresolved contradiction) × (1 − 0.3·ocr_low_conf_ratio). **Bands:** ≥0.75 answer plainly · 0.4–0.75 answer with hedge ("based on limited evidence…") · <0.4 refuse. Every response carries the numeric score + band.
    **Clarification round-trip:** the AMBIGUOUS branch returns a question object; the user's follow-up is appended and the loop re-runs exactly once (eval harness supplies scripted follow-ups).
15. **Gap analysis in refusals** (gbrain pattern) — refusals name what's missing.
16. **Trace log** (ours) — machine-readable hop record; every answer replayable.
17. **Decision memory** (dg-core) — answers stored with confidence/outcome/decay/supersede; the audit graph.

### Prove (once)
18. **Eval harness** (ours) — 15 gold questions in 5 categories (answerable 5 / unanswerable 3 / contradictory 3 / OCR-dependent 2 / ambiguous 2), expected-behavior labels, LLM judge @ temp 0 with rubric, `--baseline` vs `--corrected` as a one-flag ablation of the SAME pipeline → hallucination-rate table.

## E. The three graphs (what happened to "graph RAG")

| Graph | Role now | Why |
|---|---|---|
| Knowledge graph (triples/communities) | **Demoted to query-time sidecar** — its one job is contradiction detection over retrieved chunks | Triple extraction is lossy for precise policy text; per-chunk ingest LLM calls are slow/costly; judges expect passage-RAG with citations. Graph kept only where it beats vectors: detecting disagreement |
| Decision graph | **Unchanged** — audit memory of every answer (confidence, outcome, decay, supersede) | Doubles as the "explicit low-confidence response" record the brief asks for |
| 3-plane context graph (chat spine x, knowledge y+, code y− via GitNexus) | **Parked as post-competition vision** (`CONTEXT_GRAPH_VISION`) | The competition build IS the y+ plane's foundation (provenance chunks + turbovec + decision memory); spine and code plane come after the deadline |

Optional flag if time remains: `--build-graph` re-enables ingest-time graph for corpus-wide contradiction scanning ("find ALL conflicts in these documents") — flashy demo, strictly a bolt-on.

## F. What we already have vs what we build

**In hand (dg-core, 13 modules, ~2,400 LOC, import-verified):** ingest pipeline w/ checkpoints, document handlers (text-layer), entity resolution, Louvain communities, beam/keyword/RRF retrieval, intent router, check_uncertainty, multi-graph search, full decision memory (confidence/decay/outcomes/supersede/autolink/compiled-truth), consolidation + dream cycle, lazy loading (<1s cold boot).

**To build (7 components):** `ocr.py` (detect+PaddleOCR+confidence), `chunk_store.py` (provenance chunks + turbovec + BM25), rerank stage, `assess.py` (clash + answerability), `controller.py` (state machine + trace + confidence + gap analysis), `eval/` (gold set + judge + report), seeded corpus.

**Deliberately dropped:** 0xsero/turboquant (KV-cache compression for inference — wrong domain), FreeOCR-AI (redundant vs Paddle), llm_wiki (overlaps deepwiki), PGLite/pgvector, HNSW, all of AgentNet + Mission Control + MCP platform code.

**gbrain accounting (4 inherited / 2 adopted / 5 skipped):**
- *Inherited free via dg-core* (the DG author had already ported these — source is annotated `gbrain #N`): compiled truth + immutable timeline (#1), keyword+RRF fusion (#2), self-wiring autolink (#5), heuristic intent router (#8).
- *Adopted now:* cross-encoder rerank (their +31.4 P@5 evidence), gap-analysis refusals.
- *Skipped:* PGLite/pgvector storage, HNSW (turbovec replaces), Minions job queue, schema packs, multi-user OAuth.
- *Citable validation:* gbrain's measured +31.4 P@5 from graph-enabled retrieval independently supports keeping a graph layer where it beats vectors.

## G. Build plan — 6 milestones, each independently demoable

| M | Build | Demo proof |
|---|---|---|
| 1 | Seeded corpus + gold set (plant: 2 conflicting policy versions, 1 scan-only fact, absent topics, ambiguous Qs, code-in-PDF) | show the planted traps |
| 2 | Ingest: markitdown + OCR + chunker | chunks printed with provenance tags |
| 3 | Index + retrieve: turbovec + BM25 + RRF + rerank | question → top-10 cited passages |
| 4 | Assess | planted contradiction flagged automatically |
| 5 | Controller | full Q&A: rewrite loop, dual-answer, clarify, refusal-with-gaps, trace visible |
| 6 | Eval harness | the before/after hallucination table |

Upgrades after M5 (only if time): superposed multi-query, rerank tuning, `--build-graph`, corpus wiki (deepwiki pattern), quantum framing paragraph.

## H. Expected headline numbers

| Metric | Baseline | Corrected (target) |
|---|---|---|
| Hallucination on unanswerable Qs | ~80–100% | ≤10% |
| Silent arbitration on contradictions | ~100% | 0% |
| Recall on OCR-dependent facts | ~0% | ≥80% |
| Overall correct-behavior rate | ~40% | ≥85% |
| Wrong refusals | — | ≤1/15 |

The ablation design (same binary, one flag) makes the delta attributable purely to the self-correction layer.

## I. Tech stack

Python 3.11+ · markitdown · PaddleOCR (pytesseract fallback) · sentence-transformers MiniLM (local) · turbovec (pip) · rank-bm25 · NetworkX · any Anthropic-compatible LLM endpoint (config via .env) · no external DB · pickle/SQLite storage · CLI first (FastAPI wrapper optional for demo UI).

## J. Risks & mitigations (carried from PRD)

| Risk | Mitigation |
|---|---|
| PaddleOCR install friction (paddle runtime) | pytesseract fallback path; OCR behind an interface |
| turbovec immaturity | float32 numpy fallback behind same interface; quantize last |
| Judge-model bias | temp 0 + rubric + few-shot anchors; hand-check all 15 |
| Correction loop oscillation | max 2 rewrites; rewrite must differ (string check) |
| Over-refusal | refusal precision is a first-class metric; tune on answerable slice |
| Lossy triples | triples only used for clash detection, never for answering |
| Scope creep (the 3-plane vision) | hard-parked; vision doc only |

## K. Demo script (the 5-minute judge walkthrough)

1. Show the messy corpus: native PDFs + a crooked scan + a doc with code + two policy versions that disagree.
2. Ask an answerable Q → cited answer with file·page, confidence 0.9.
3. Ask the unanswerable Q → baseline flag ON: watch it hallucinate. Flag OFF: refusal + gap analysis.
4. Ask the contradiction Q → dual-answer, both sources cited, asks which policy year applies.
5. Ask the OCR Q → answer quoting the scanned page, "ocr 91%" tag visible in the citation.
6. Ask the ambiguous Q → clarifying question; answer the follow-up → resolved.
7. Run `python -m eval --both` → the before/after table renders.
8. Close with the trace log of question 3: retrieve → assess:INSUFFICIENT → rewrite → assess → refuse+gaps.

## L. Growth & freshness — how the system grows and stays out of outdated data

**Growth (append-only, O(new doc)):**
1. Incremental ingest — each doc processed independently; turbovec `IdMapIndex` keeps stable IDs across additions/deletions, BM25 re-indexes cheaply, checkpointing resumes crashed batches. Adding doc #501 never touches the other 500.
2. No answer-level caching — every question re-retrieves, so yesterday's refusal becomes today's answer the moment a covering doc lands. **Gap-analysis refusals are literally the ingestion to-do list** ("corpus has nothing on Z" → ingest Z).
3. Decision memory densifies with use — every answer auto-links to related past decisions (`shares_community`, zero LLM).

**Freshness (four layered mechanisms):**
1. **Contradiction detection IS the staleness detector.** A new policy doc clashing with an old one fires the triple-clash check at query time — the system *cannot* silently serve the stale value because it can't silently serve either: it dual-answers with both dates/sources and asks which applies. Staleness surfaces itself.
2. **Supersede — explicit retirement.** dg-core's `supersede(old, new)` marks content inactive with a `supersedes` edge; superseded chunks drop out of retrieval but remain in the **immutable timeline** (history stays queryable: "what was the limit in 2023?").
3. **Decay — automatic forgetting.** Confidence −0.1 per pass on content unaccessed 90 days; <0.2 → inactive. Retrieval scores `similarity × confidence`, so unused aging knowledge fades gradually. Runs lazily once/day, zero LLM (dream cycle).
4. **Recency tiebreak.** Ingest/doc dates in provenance; newer wins ties among *non*-contradicting chunks — genuine conflicts route to mechanism 1 instead.

**Status:** incremental ingest + contradiction-as-staleness are in competition scope (M2–M4); decision decay/supersede comes free from dg-core; chunk-level supersede + recency weighting are designed but post-M5 (~30 lines).

**Judge one-liner:** "Growth is append-only and O(new doc); staleness can't hide because conflicting facts collide structurally at query time, and confirmed-stale content is superseded into an immutable timeline rather than deleted."

**Code plane (y−) growth — live, not batch:** when code is written DURING a conversation, the code graph updates **incrementally per file-edit** — re-parse only the changed file (milliseconds), splice its symbols/edges; **stable symbol IDs** (`Function:path:name`) preserve spine `references` edges from earlier turns, so history survives edits. Deferred enrichment (LLM summaries/embeddings) is tracked with a **stale flag** and answers over stale files carry a provenance note. At session **finalization**, a full re-index + consolidation pass (dream cycle) catches cross-file effects and writes the session's changes back as a summary decision on the spine. Incremental for truth-now, batch for truth-deep. (Pattern proven in the parent Decision_Graph: `update_files` + `semantic_stale` tools.)

## M. Build-sprint results (implemented & measured, July 10–11)

**Pipeline:** all milestones M1–M6 built and live-tested. **Eval (true ablation):
hallucination 20%→7%, correct behavior 67%→93%, silent arbitration 3/3→0/3,
ambiguous clarification 0/2→2/2.** Hard-test battery (15 adversarial cases +
injection + empty-corpus + code-freshness): zero fabrications; the planted
injection value ($9,999) never appeared in any answer.

**Three planes, each built with DecisionGraph's own recipe, cross-wired:**
y+ = dg-core pipeline verbatim (72 triples → 108 resolved entities → 41 Louvain
communities with LLM summaries, DG storage format — DG's `beam_query` runs on it
unchanged); x = conversation-topic communities (4 topics over 23 turns, DG
compile_topic style); y− = GitNexus code clusters + `calls` edges + stable symbol
IDs; cross-plane `grounds`/`references`/`references_symbol`/`member_of` edges.
Figures are first-class cited assets (bbox + caption + OCR, `[Figure N]`
citations, image paths returned for UI display).

**Key architectural finding:** raw DG semantic beam search ranked the injection
poison FIRST (community "$9,999 travel limit", sim 0.702) — while the corrected
pipeline never leaked it. This empirically validates the core design decision:
the knowledge graph serves retrieval/contradiction-detection BEHIND the
assessment gate, never as an unguarded answer source.

**Known limitations (honest):** tiny-corpus community over-fragmentation (41
communities/108 entities; self-heals at scale with min_size=5); 2 garbled
community summaries from noisy triples; retro re-OCR (FR-1.6b) designed but not
implemented; Mistral OCR Tier-2 wired but untested (no key); multi-hop reasoning
degrades to honest refusal.

## N. Post-competition roadmap (the vision)

The 3-plane context OS: conversation spine (x) + knowledge plane (y+, built by this project) + code plane (y−, GitNexus pattern), cross-linked with `grounds`/`references` edges, one turbovec index over all planes, exposed via MCP so Claude/Gemini/GPT share one memory. Context window becomes O(neighborhood) instead of O(history). The competition artifact is milestone zero of this product.



---
