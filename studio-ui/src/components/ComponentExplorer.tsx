import { useState } from 'react'

const G = '#3ddc97'

type Comp = { id: string; label: string; kind: 'service' | 'database' | 'client'; layer: string
  tech: string[]; desc: string; detail?: string[] }

export const COMPONENTS: Comp[] = [
  // ── entry
  { id: 'corpus', label: 'Corpus Source', kind: 'client', layer: 'Entry',
    tech: ['PDF', 'DOCX', 'Source code'],
    desc: 'Messy documents: native PDFs, scanned pages with no text layer, and code embedded in documents.' },
  { id: 'cli', label: 'CLI & Eval Runner', kind: 'client', layer: 'Entry',
    tech: ['Python', 'Click'],
    desc: 'Commands: ingest / ask / stats. The eval harness runs 15 gold questions across five categories.',
    detail: ['answerable · unanswerable · contradictory · OCR-dependent · ambiguous',
      'one flag switches the correction layer off for a clean ablation'] },

  // ── ingestion
  { id: 'ingest', label: 'Ingestion Pipeline', kind: 'service', layer: 'Ingestion',
    tech: ['Unstructured-IO', 'pdfplumber', 'Tesseract', 'dots.ocr'],
    desc: 'Normalizes every format to Markdown, escalating through an OCR ladder when a page has no text layer.',
    detail: ['checkpointed and resumable — a crash at chunk N resumes at N',
      'code detected via monospace-font runs and symbol density, stored verbatim and atomic',
      'escalates to Tier 2 when confidence < 0.85 or garbage ratio > 20%'] },
  { id: 'mistral', label: 'Tier-2 OCR escalation', kind: 'service', layer: 'Ingestion',
    tech: ['dots.ocr', 'vision LLM', 'OpenAI-compatible'],
    desc: 'Optional escalation for pages tier 1 reads poorly. Pluggable and off by default — the pipeline needs no paid API.',
    detail: ['backends: self-hosted dots.ocr, any local vision model, or a hosted OCR API',
      'fires only below 0.85 confidence or above 20% garbage ratio',
      'unreachable backend degrades to the tier-1 result instead of failing the ingest'] },
  { id: 'embed', label: 'Embedding Model', kind: 'service', layer: 'Ingestion',
    tech: ['sentence-transformers', 'MiniLM', 'local'],
    desc: 'Local embedding model for chunking and query vectorization. No external API calls — index build costs zero LLM tokens.' },

  // ── storage
  { id: 'turbovec', label: 'turbovec index', kind: 'database', layer: 'Storage',
    tech: ['TurboQuant', 'SIMD'],
    desc: '2/4-bit quantized embeddings with SIMD-accelerated search — roughly 31GB of vectors compressed to 4GB.' },
  { id: 'bm25', label: 'BM25 index', kind: 'database', layer: 'Storage',
    tech: ['rank-bm25'],
    desc: 'Keyword index covering identifiers, section headings, and code symbols — the signal vectors miss.' },
  { id: 'meta', label: 'Chunk metadata', kind: 'database', layer: 'Storage',
    tech: ['SQLite'],
    desc: 'Provenance for every chunk: file, page, native or OCR, OCR confidence, content type, language.' },
  { id: 'figures', label: 'Figure asset store', kind: 'database', layer: 'Storage',
    tech: ['SQLite', 'Pillow'],
    desc: 'Diagram assets with bounding boxes, extracted images, and understanding summaries, linked back to text chunks.' },

  // ── retrieval + gate
  { id: 'retrieve', label: 'Retrieval Engine', kind: 'service', layer: 'Retrieval',
    tech: ['sentence-transformers', 'rank-bm25', 'entity match', 'cross-encoder'],
    desc: 'Three signals scored in parallel and fused by reciprocal rank, then reranked by a cross-encoder.',
    detail: ['superposed multi-query — up to 3 interpretations retrieved in parallel',
      'intent router (regex, zero-LLM) sends structural questions straight to the code graph',
      'provenance weighting down-ranks low-confidence OCR and injection phrasing'] },
  { id: 'assess', label: 'Assessment Engine', kind: 'service', layer: 'Gate',
    tech: ['Pydantic', 'triple extraction', 'evidence voting'],
    desc: 'The gate. Runs before generation and decides whether answering is warranted at all.',
    detail: ['sufficiency by embedding similarity — fails here cost zero LLM tokens',
      'query-time triple extraction from the top-10 chunks only',
      'contradiction = same subject+relation, overlapping validity, different canonical value',
      'evidence voting demotes a lone OCR outlier against agreeing sources'] },
  { id: 'qkg', label: 'Query-Time Knowledge Graph', kind: 'database', layer: 'Gate',
    tech: ['in-memory', 'triple store'],
    desc: 'Ephemeral (subject, relation, object) store built per query from retrieved chunks — never persisted, never stale.' },
  { id: 'controller', label: 'Self-Correction Controller', kind: 'service', layer: 'Gate',
    tech: ['state machine', 'dg-core'],
    desc: 'Routes the verdict to answer, dual-answer, clarify, rewrite, or refuse — and records the trace.',
    detail: ['confidence bands: ≥0.75 answer · 0.4–0.75 hedge · <0.4 refuse',
      'at most 2 rewrites, drift-checked; hard cap of 6 LLM calls per query',
      'every response carries a machine-readable trace, so answers are replayable'] },
  { id: 'llm', label: 'LLM Provider', kind: 'service', layer: 'Gate',
    tech: ['provider-agnostic'],
    desc: 'Anthropic-compatible or OpenAI-compatible (NVIDIA NIM, OpenAI, local) — switched by one env variable.' },

  // ── memory
  { id: 'scg', label: 'Session Context Graph', kind: 'database', layer: 'Memory',
    tech: ['NetworkX', 'Louvain', 'DecisionGraph recipe'],
    desc: 'The 3-plane global graph. Each plane is built with the full DecisionGraph recipe.',
    detail: ['Louvain community detection → community summaries → compiled truth per topic',
      'planes cross-wired by grounds / references / member_of / supersedes',
      'per-session chains so conversations stay distinct inside one global graph'] },
  { id: 'audit', label: 'Decision audit graph', kind: 'database', layer: 'Memory',
    tech: ['NetworkX', 'SQLite'],
    desc: 'Lifecycle for every turn — confidence, access count, decay, supersession. Spine nodes are decision nodes.' },
  { id: 'codegraph', label: 'Code Graph (GitNexus)', kind: 'database', layer: 'Memory',
    tech: ['tree-sitter', 'GitNexus', 'NetworkX'],
    desc: 'Structural code graph — symbols, calls, imports — with the DecisionGraph recipe applied to the call graph.',
    detail: ['AST function bodies extracted across 22+ languages',
      'code communities detected the same way document communities are'] },
  { id: 'recall', label: 'Recall Engine', kind: 'service', layer: 'Memory',
    tech: ['dg-core', 'NetworkX'],
    desc: "DecisionMemory.query: embeds a question and scores past turns by similarity × confidence over active memories.",
    detail: ['lazy daily decay; memories below 0.2 confidence deactivate',
      'access bookkeeping — retrieval itself keeps a memory alive',
      'community beam then neighborhood walk: O(neighborhood), not O(history)'] },

  // ── surface
  { id: 'mcp', label: 'MCP Server', kind: 'service', layer: 'Surface',
    tech: ['MCP SDK', 'stdio', '3d-force-graph'],
    desc: 'Exposes the whole system to any model — ask, recall, ingest, link repo, query the graph, live 3D view.',
    detail: ['same memory reachable from Claude, OpenCode, Cherry Studio, any MCP client',
      'embedded http server streams the live 3D graph as it grows'] },
  { id: 'multimodal', label: 'Multimodal Encoders', kind: 'service', layer: 'Roadmap',
    tech: ['CLIP', 'Whisper', 'table extractor'],
    desc: 'Images, audio transcripts and tables feeding the same index and the same communities. Roadmap, not built.' },
]

const LAYERS = ['Entry', 'Ingestion', 'Storage', 'Retrieval', 'Gate', 'Memory', 'Surface', 'Roadmap']
const KIND_MARK: Record<string, string> = { service: '▸', database: '▪', client: '◇' }

export function ComponentExplorer() {
  const [sel, setSel] = useState<Comp>(COMPONENTS.find(c => c.id === 'assess')!)
  const [layer, setLayer] = useState<string | null>(null)
  const shown = layer ? COMPONENTS.filter(c => c.layer === layer) : COMPONENTS

  return (
    <div className="rounded-xl border border-white/[0.09] bg-white/[0.02] p-6">
      <div className="flex flex-wrap gap-2 mb-6">
        <button onClick={() => setLayer(null)}
          className="text-[12px] px-3 py-1.5 rounded-lg border transition"
          style={!layer ? { background: G, borderColor: G, color: '#000', fontWeight: 500 }
            : { borderColor: 'rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.5)' }}>
          all {COMPONENTS.length}
        </button>
        {LAYERS.map(l => (
          <button key={l} onClick={() => setLayer(l === layer ? null : l)}
            className="text-[12px] px-3 py-1.5 rounded-lg border transition"
            style={layer === l ? { background: G, borderColor: G, color: '#000', fontWeight: 500 }
              : { borderColor: 'rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.5)' }}>{l}</button>
        ))}
      </div>

      <div className="grid md:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] gap-5">
        {/* list */}
        <div className="space-y-1.5 max-h-[420px] overflow-y-auto pr-1">
          {shown.map(c => {
            const on = sel.id === c.id
            return (
              <button key={c.id} onClick={() => setSel(c)}
                className="w-full text-left rounded-lg border px-3.5 py-2.5 transition-all duration-200"
                style={{
                  borderColor: on ? G : 'rgba(255,255,255,0.08)',
                  background: on ? 'rgba(61,220,151,0.07)' : 'transparent',
                }}>
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-[11px]" style={{ color: on ? G : 'rgba(255,255,255,0.25)' }}>
                    {KIND_MARK[c.kind]}
                  </span>
                  <span className="text-[13.5px]" style={{ color: on ? '#fff' : 'rgba(255,255,255,0.65)' }}>{c.label}</span>
                  <span className="ml-auto text-[10.5px] font-mono text-white/20">{c.layer}</span>
                </div>
              </button>
            )
          })}
        </div>

        {/* detail */}
        <div className="rounded-lg border border-white/[0.09] bg-black/40 p-5" key={sel.id}>
          <div className="flex items-baseline gap-2.5 mb-1">
            <span className="font-mono text-[12px]" style={{ color: G }}>{KIND_MARK[sel.kind]}</span>
            <h4 className="text-[19px] text-white font-medium">{sel.label}</h4>
          </div>
          <div className="text-[11px] font-mono text-white/25 mb-4">{sel.kind} · {sel.layer} layer</div>
          <p className="text-[14px] leading-[1.65] text-white/60 mb-4">{sel.desc}</p>
          {sel.detail && (
            <ul className="space-y-2 mb-5">
              {sel.detail.map(d => (
                <li key={d} className="flex gap-2.5 text-[13px] leading-[1.6] text-white/45">
                  <span style={{ color: G }} className="mt-[2px]">—</span><span>{d}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-1.5 pt-4 border-t border-white/[0.07]">
            {sel.tech.map(t => (
              <span key={t} className="text-[11.5px] font-mono px-2.5 py-1 rounded-md border border-white/[0.1] text-white/45">{t}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
