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
