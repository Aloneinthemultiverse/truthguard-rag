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
hallucination 20%→7%, correct behavior 67%→87%, silent arbitration 3/3→0/3,
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
