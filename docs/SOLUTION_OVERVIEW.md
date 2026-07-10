# Solution Overview — Self-Correcting RAG Pipeline (v2)

## The one-paragraph pitch

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
