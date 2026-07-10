# Existing Product Architecture — dg-core (as-is, today)

What we have **in hand right now**: the DecisionGraph memory core, 13 Python modules,
extracted and verified standalone (v0.3.0). No OCR, no contradiction detection, no
self-correction controller, no eval harness — this is the inventory *before* the
competition build.

---

## 1. Big picture

Two persistent memories fed by one ingestion pipeline, queried through three modes,
maintained by a "sleep" cycle.

```
                          ┌────────────────────────────────┐
                          │        PUBLIC API (core.py)     │
                          │  DecisionGraph(storage_dir)     │
                          │  .ingest(path)  .query(q, mode) │
                          │  .get_decisions()  .stats()     │
                          └───────┬──────────────┬─────────┘
                 INGEST PATH      │              │      QUERY PATH
                                  ▼              ▼
┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
│      INGESTION PIPELINE (8 stages)  │  │        QUERY MODES (agent.py)       │
│                                     │  │                                     │
│ 1 read_document()                   │  │  normal  — decision memory only,    │
│   document_handlers.py              │  │            1 LLM call, no graph     │
│   PDF (pdfplumber) / DOCX / MD / TXT│  │  session — 1-pass beam retrieval +  │
│ 2 chunk_text()  1000 chars/100 ovlp │  │            memory + 1 LLM call      │
│ 3 extract_all_triples()  ingest.py  │  │  deep    — ReAct loop (≤8 steps):   │
│   LLM → (subj, rel, obj) JSON       │  │            THINK → ACT:query_graph  │
│   3 retries, JSON repair, checkpoint│  │            → OBSERVATION → … ANSWER │
│   every 50 chunks (resumable)       │  │            forced-answer after 3    │
│ 4 build_graph()  → MultiDiGraph     │  │            queries or step cap      │
│ 5 merge_graphs() with existing      │  └──────────────────┬──────────────────┘
│ 6 entity_resolution()  graph.py     │                     │ uses
│   embed all nodes, merge ≥0.92 cos  │                     ▼
│ 7 detect_communities()  Louvain,    │  ┌─────────────────────────────────────┐
│   fold clusters <5 into neighbors   │  │     RETRIEVAL TOOLKIT (query.py)    │
│ 8 summarize_communities()  1 LLM    │  │                                     │
│   sentence each → embed summaries   │  │ beam_query()      top-3 communities │
└──────────────────┬──────────────────┘  │   by cosine → expand node edges     │
                   │ writes              │   → ≤60 fact triples                │
                   ▼                     │ keyword_search()  BM25-ish over     │
┌─────────────────────────────────────┐  │   graph edges, zero-LLM, zero-dep   │
│   MEMORY 1: KNOWLEDGE GRAPH         │  │ rrf_fuse()        Reciprocal Rank   │
│   NetworkX MultiDiGraph             │  │   Fusion of any ranked lists        │
│   nodes = concepts                  │  │ classify_intent() regex router:     │
│   edges = relations (multi)         │  │   temporal|entity|event|general     │
│   + communities {cid: [nodes]}      │  │   → maps to deep/session mode       │
│   + summaries {cid: text}           │  │ check_uncertainty() max community   │
│   + summary embeddings (MiniLM)     │  │   sim < 0.3 → REFUSE + suggestion   │
└─────────────────────────────────────┘  │ multi_graph_beam_query() search N   │
                                         │   graphs, source-tag + dedupe       │
┌─────────────────────────────────────┐  └─────────────────────────────────────┘
│   MEMORY 2: DECISION MEMORY         │
│   decisions.py — NetworkX DiGraph   │  ┌─────────────────────────────────────┐
│                                     │  │   MAINTENANCE ("sleep")             │
│ DecisionNode: question, answer,     │  │                                     │
│   reasoning, communities_used,      │  │ consolidate.py — scan ended session │
│   confidence 0-1, outcome, access   │  │   scratchpads (kernel_cag/*.json) → │
│   count, is_active, superseded_by   │  │   aggregate churn+decisions → write │
│                                     │  │   summary decision → archive        │
│ decay: -0.1 conf if unused 90d,     │  │ dream.py — run_dream_cycle():       │
│   1x/day lazy; inactive < 0.2       │  │   decay → dedupe → relink →         │
│ outcomes: success +0.1 / fail -0.3  │  │   (optional) compile topics         │
│ retrieval score = sim × conf ×      │  │ Zero-LLM on the hot path            │
│   outcome_weight (1.2/0.8)          │  └─────────────────────────────────────┘
│ links: caused_by / depends_on /     │
│   related_to / supersedes /         │  ┌─────────────────────────────────────┐
│   shares_community (auto, no LLM)   │  │   MODEL LAYER                       │
│ compiled truth per topic (LLM) +    │  │ LLM: anthropic SDK → any Anthropic- │
│   immutable timeline                │  │   compatible base_url (config/.env) │
│ auto-save on store; legacy-pickle   │  │ Embeddings: sentence-transformers   │
│   migration shim                    │  │   all-MiniLM-L6-v2, LAZY-loaded     │
└─────────────────────────────────────┘  │   (cold boot <1s until needed)      │
                                         └─────────────────────────────────────┘
```

## 2. Module inventory (13 files, ~2,400 LOC)

| Module | LOC | Responsibility | LLM calls |
|---|---|---|---|
| `core.py` | 184 | `DecisionGraph` facade: per-instance `storage_dir` isolation, lazy graph+embedder loading, 8-stage ingest orchestration, mode dispatch | — |
| `config.py` | ~35 | Env-driven: `LLM_BASE_URL/KEY/MODEL`, `EMBED_MODEL`, thresholds (entity-res 0.92, beam k=3, decision-sim 0.5, uncertainty 0.3), chunk 1000/100, max 8 ReAct steps, 3 query-mode constants | — |
| `document_handlers.py` | 108 | Format router: PDF via pdfplumber, DOCX via python-docx, MD/TXT direct. **Text-layer only — blind to scans** | — |
| `ingest.py` | 159 | Chunking, cleaning, LLM triple extraction (3-retry + regex JSON repair), checkpoint/resume every 50 chunks, graph build/merge | 1 per chunk |
| `ingest_sources.py` | 104 | URL/source fetch helpers feeding the same pipeline | — |
| `graph.py` | 120 | Entity resolution (cosine ≥0.92 node merge, shortest name wins), Louvain communities (min size 5, small→neighbor fold), community summaries, pickle save/load | 1 per community |
| `query.py` | 221 | beam_query, keyword_search, rrf_fuse, classify_intent, **check_uncertainty**, multi_graph_beam_query | 0 |
| `decisions.py` | 461 | DecisionMemory: store/query with confidence×outcome scoring, decay, supersede, autolink, compiled-truth+timeline, outcome patterns, migration shim, auto-persist | 1 (compile only) |
| `agent.py` | 393 | normal_mode, session_mode, react_agent (deep): THINK/ACT/ANSWER loop, past-decision priming, reasoning summarizer, auto-store answer as decision | 1–9 per query |
| `consolidate.py` | 174 | Sleep pass over session scratchpads: scan→aggregate→write-back→dream→archive; idempotent | 0 |
| `dream.py` | ~150 | Dream cycle: decay → dedupe → relink (→ optional topic compile) | 0–n |
| `logging_setup.py` | ~40 | Structured logger | — |
| `__init__.py` | 4 | Exports `DecisionGraph` (trimmed of platform imports) | — |

## 3. Storage layout (per workspace)

```
storage/<workspace>/
  graph_clean.pkl          # knowledge MultiDiGraph
  communities_clean.pkl    # {cid: [node names]}
  summaries_clean.pkl      # {cid: {nodes, summary}}
  decision_graph.pkl       # {graph, compiled, last_decay}  (new format, legacy-compatible)
  checkpoint_<doc>.pkl     # resumable ingest state {triples, chunk_idx}
  kernel_cag/              # session scratchpads consumed by consolidate.py
    <sid>.json … _archive/
```
All pickle — simple, portable, no DB dependency. Decision memory loads
independently of the knowledge graph (a workspace can hold decisions with zero
ingested docs).

## 4. What each existing capability gives the competition build

| Existing piece | Value for the RAG competition |
|---|---|
| 8-stage ingest w/ checkpoints | "Messy corpus" ingestion for free; crash-resumable on big doc sets |
| Knowledge graph triples | Makes contradiction detection a (subject, relation) dictionary lookup later |
| Hybrid retrieval + RRF | Better recall than pure-vector; already fused |
| `check_uncertainty` | The seed of the sufficiency gate — threshold + refusal message + suggestion already implemented |
| Intent router | Free query-mode routing, zero LLM |
| Decision memory | Audit trail: every answer stored with confidence + outcome slot — doubles as the "explicit low-confidence response" record |
| Consolidation/dream | Story depth: memory that decays and self-maintains (demo bonus, not scored) |
| Lazy loading | Fast CLI startup; embeddings only load when needed |

## 5. Known gaps (what does NOT exist yet)

1. **No OCR** — pdfplumber returns empty text on scanned pages; those facts are invisible.
2. **No chunk-level store** — only triples are retrievable; exact wording and niche facts lost in extraction can't be cited.
3. **No contradiction detection** — conflicting triples coexist silently in the graph.
4. **No answerability judgment** — `check_uncertainty` catches "off-topic," not "on-topic but incomplete."
5. **No self-correction loop** — deep mode re-queries but never rewrites a failed query, never clarifies, never chooses refuse-vs-answer deliberately.
6. **No provenance** — chunks carry no source file/page tags; answers can't cite.
7. **No eval harness** — zero measurement of hallucination rate.

These seven gaps are exactly the ★NEW components in `ARCHITECTURE.md` (target state).
