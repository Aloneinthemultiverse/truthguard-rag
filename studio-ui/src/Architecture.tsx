import { useState, useEffect, useRef } from 'react'
import { BlurFade } from '@/components/magicui/blur-fade'
import { KineticGrid } from '@/components/magicui/kinetic-grid'
import { ComponentExplorer, COMPONENTS } from '@/components/ComponentExplorer'
import { ArchMap } from '@/components/ArchMap'
import { MCPTools } from '@/components/MCPTools'
import { staticGraphUrl, HAS_GRAPH } from '@/lib/api'

const G = '#3ddc97'          // the only accent

/* ─────────────── shared shells ─────────────── */
function Section({ id, eyebrow, title, lead, children }: any) {
  return (
    <section id={id} className="border-t border-white/[0.07] py-24">
      <div className="mx-auto max-w-[960px] px-8">
        <BlurFade>
          <div className="text-[11.5px] uppercase tracking-[0.18em] text-white/35 font-medium mb-4">{eyebrow}</div>
          <h2 className="font-serif-display text-[40px] leading-[1.12] text-white mb-5">{title}</h2>
          {lead && <p className="text-[16.5px] leading-[1.75] text-white/50 max-w-[720px] mb-9">{lead}</p>}
        </BlurFade>
        {children}
      </div>
    </section>
  )
}
const Panel = ({ children, className = '' }: any) => (
  <div className={`rounded-xl border border-white/[0.09] bg-white/[0.02] ${className}`}>{children}</div>
)
const Btn = ({ on, children, ...p }: any) => (
  <button {...p} className={`text-[12.5px] px-3.5 py-1.5 rounded-lg border transition ${on
    ? 'text-black font-medium' : 'text-white/55 border-white/[0.12] hover:text-white hover:border-white/25'}`}
    style={on ? { background: G, borderColor: G } : {}}>{children}</button>
)

/* ─────────────── 1. pipeline simulator ─────────────── */
const STAGES = [
  { k: 'ingest', t: 'Ingest', d: 'OCR ladder → chunks with provenance', out: '137 chunks · file · page · native/ocr%' },
  { k: 'retrieve', t: 'Retrieve', d: 'vectors + BM25 + entity → RRF → rerank', out: '10 candidates, scored' },
  { k: 'assess', t: 'Assess', d: 'sufficiency → triples → clash → verdict', out: 'CONTRADICTORY · 2 claims' },
  { k: 'respond', t: 'Respond', d: 'answer / dual / clarify / refuse', out: 'dual-answer with both sources' },
]
function PipelineSim() {
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(true)
  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => setStep(s => (s + 1) % STAGES.length), 1900)
    return () => clearInterval(id)
  }, [playing])
  return (
    <Panel className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-[13px] text-white/45">A question moving through the pipeline</span>
        <div className="ml-auto flex gap-2">
          <Btn on={playing} onClick={() => setPlaying(p => !p)}>{playing ? 'pause' : 'play'}</Btn>
          <Btn onClick={() => { setPlaying(false); setStep(s => (s + 1) % STAGES.length) }}>step →</Btn>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-2.5 relative">
        {STAGES.map((s, i) => {
          const active = i === step, done = i < step
          return (
            <div key={s.k} onClick={() => { setPlaying(false); setStep(i) }}
              className="relative rounded-lg border p-4 cursor-pointer transition-all duration-500"
              style={{
                borderColor: active ? G : done ? 'rgba(61,220,151,0.28)' : 'rgba(255,255,255,0.09)',
                background: active ? 'rgba(61,220,151,0.08)' : 'transparent',
                transform: active ? 'translateY(-3px)' : 'none',
              }}>
              <div className="text-[10.5px] tracking-[0.12em] font-semibold"
                style={{ color: active || done ? G : 'rgba(255,255,255,0.28)' }}>0{i + 1}</div>
              <div className="text-[15px] font-medium mt-1.5 mb-1.5" style={{ color: active ? '#fff' : 'rgba(255,255,255,0.7)' }}>{s.t}</div>
              <div className="text-[12px] leading-[1.5] text-white/40">{s.d}</div>
            </div>
          )
        })}
      </div>
      <div className="mt-5 rounded-lg bg-black/50 border border-white/[0.07] px-4 py-3 font-mono text-[12.5px] flex items-center gap-3">
        <span className="text-white/30">output</span>
        <span style={{ color: G }} key={step} className="animate-[fadeIn_.4s_ease]">{STAGES[step].out}</span>
      </div>
    </Panel>
  )
}

/* ─────────────── 2. the gate — verdict explorer ─────────────── */
const SCENARIOS = [
  { id: 'clean', label: 'Fact is present, sources agree',
    checks: [['sufficiency', true], ['triples extracted', true], ['contradiction', false], ['ambiguity', false]],
    verdict: 'ANSWER', note: 'Generate with citations and a confidence band.' },
  { id: 'missing', label: 'Fact is not in the corpus',
    checks: [['sufficiency', false], ['triples extracted', false], ['contradiction', false], ['ambiguity', false]],
    verdict: 'REFUSE', note: 'Decline with gap analysis. The generator is never called.' },
  { id: 'conflict', label: 'Two editions disagree',
    checks: [['sufficiency', true], ['triples extracted', true], ['contradiction', true], ['ambiguity', false]],
    verdict: 'DUAL-ANSWER', note: 'Both values shown with provenance. No silent arbitration.' },
  { id: 'ambiguous', label: 'Question has two readings',
    checks: [['sufficiency', true], ['triples extracted', true], ['contradiction', false], ['ambiguity', true]],
    verdict: 'CLARIFY', note: 'Offer the readings, re-run with the answer.' },
]
function GateExplorer() {
  const [sel, setSel] = useState(0)
  const s = SCENARIOS[sel]
  return (
    <Panel className="p-6">
      <div className="text-[13px] text-white/45 mb-4">Pick a situation — watch which checks fire and where it routes</div>
      <div className="flex flex-wrap gap-2 mb-7">
        {SCENARIOS.map((x, i) => <Btn key={x.id} on={i === sel} onClick={() => setSel(i)}>{x.label}</Btn>)}
      </div>
      <div className="grid sm:grid-cols-[1fr_auto_1fr] gap-6 items-center">
        <div className="space-y-2">
          {s.checks.map(([name, fired]: any, i) => (
            <div key={name} className="flex items-center gap-3 rounded-lg border border-white/[0.07] px-3.5 py-2.5
              transition-all duration-500" style={{ animationDelay: `${i * 90}ms` }}>
              <span className="w-1.5 h-1.5 rounded-full transition-colors duration-500"
                style={{ background: fired ? G : 'rgba(255,255,255,0.18)', boxShadow: fired ? `0 0 10px ${G}` : 'none' }} />
              <span className="text-[13px]" style={{ color: fired ? '#fff' : 'rgba(255,255,255,0.35)' }}>{name}</span>
              <span className="ml-auto text-[11px] font-mono" style={{ color: fired ? G : 'rgba(255,255,255,0.2)' }}>
                {fired ? 'TRIGGERED' : '—'}</span>
            </div>
          ))}
        </div>
        <div className="text-white/20 text-center text-xl hidden sm:block">→</div>
        <div className="rounded-xl border p-5 transition-all duration-500"
          style={{ borderColor: G, background: 'rgba(61,220,151,0.07)' }}>
          <div className="font-serif-display text-[30px] leading-none" style={{ color: G }} key={s.verdict}>{s.verdict}</div>
          <div className="text-[13px] text-white/50 mt-3 leading-[1.6]">{s.note}</div>
        </div>
      </div>
    </Panel>
  )
}

/* ─────────────── 3. bi-temporal timeline ─────────────── */
function TemporalSim() {
  const [aEnd, setAEnd] = useState(2023)      // when the old fact stops being valid
  const bStart = 2024
  const overlaps = aEnd >= bStart
  const yr = (y: number) => ((y - 2021) / 5) * 100
  return (
    <Panel className="p-6">
      <div className="text-[13px] text-white/45 mb-1">
        Two facts, same subject and relation, different values
      </div>
      <div className="text-[12px] text-white/30 mb-6">
        Drag the end of the first fact's validity. Overlap means conflict; separation means a timeline.
      </div>
      <div className="relative h-[132px] mb-4">
        <div className="absolute inset-x-0 bottom-0 flex justify-between text-[11px] text-white/25 font-mono">
          {[2021, 2022, 2023, 2024, 2025, 2026].map(y => <span key={y}>{y}</span>)}
        </div>
        <div className="absolute inset-x-0 top-0 bottom-6">
          {[0, 20, 40, 60, 80, 100].map(p => (
            <div key={p} className="absolute top-0 bottom-0 w-px bg-white/[0.06]" style={{ left: `${p}%` }} />
          ))}
          {/* fact A */}
          <div className="absolute h-9 rounded-md flex items-center px-3 text-[12.5px] transition-all duration-300"
            style={{ top: 6, left: `${yr(2022)}%`, width: `${Math.max(4, yr(aEnd) - yr(2022))}%`,
              background: overlaps ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.08)',
              border: `1px solid ${overlaps ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.18)'}` }}>
            <span className="text-white/80 font-mono whitespace-nowrap">$300</span>
          </div>
          {/* fact B */}
          <div className="absolute h-9 rounded-md flex items-center px-3 text-[12.5px]"
            style={{ top: 52, left: `${yr(bStart)}%`, right: 0,
              background: 'rgba(61,220,151,0.12)', border: `1px solid ${G}` }}>
            <span className="font-mono whitespace-nowrap" style={{ color: G }}>$500 · current</span>
          </div>
        </div>
      </div>
      <input type="range" min={2022} max={2026} step={1} value={aEnd}
        onChange={e => setAEnd(+e.target.value)}
        className="w-full accent-[#3ddc97] mb-5" />
      <div className="rounded-lg border px-4 py-3.5 transition-all duration-300 flex items-start gap-3"
        style={{ borderColor: overlaps ? 'rgba(255,255,255,0.35)' : G,
          background: overlaps ? 'rgba(255,255,255,0.04)' : 'rgba(61,220,151,0.07)' }}>
        <span className="font-mono text-[12px] mt-0.5" style={{ color: overlaps ? '#fff' : G }}>
          {overlaps ? 'CONTRADICTION' : 'SUPERSESSION'}
        </span>
        <span className="text-[13px] text-white/50 leading-[1.6]">
          {overlaps
            ? 'The windows overlap — both claim to be true at the same time. Surface both values with sources.'
            : 'The windows are separate — $300 was true, then $500 replaced it. A timeline, not a conflict.'}
        </span>
      </div>
    </Panel>
  )
}

/* ─────────────── 4. retrieval signal fusion ─────────────── */
const DOCS = ['policy_2024 p1', 'policy_2023 p1', 'memo_118 p1', 'handbook p4', 'vendor_guide p2']
const RANKS: Record<string, number[]> = {
  vector: [0, 1, 3, 2, 4],
  bm25:   [1, 0, 2, 4, 3],
  entity: [0, 2, 1, 4, 3],
}
function FusionSim() {
  const [on, setOn] = useState<Record<string, boolean>>({ vector: true, bm25: true, entity: true })
  const active = Object.keys(on).filter(k => on[k])
  const scores = DOCS.map((_, i) => {
    let s = 0
    active.forEach(k => { const r = RANKS[k].indexOf(i); if (r >= 0) s += 1 / (60 + r + 1) })
    return s
  })
  const order = scores.map((s, i) => [s, i]).sort((a, b) => b[0] - a[0]).map(([, i]) => i)
  const max = Math.max(...scores, 1e-9)
  return (
    <Panel className="p-6">
      <div className="text-[13px] text-white/45 mb-4">Toggle the signals — the fused ranking reorders live</div>
      <div className="flex gap-2 mb-7">
        {Object.keys(on).map(k => (
          <Btn key={k} on={on[k]} onClick={() => setOn(o => ({ ...o, [k]: !o[k] }))}>
            {k === 'bm25' ? 'BM25 keywords' : k === 'vector' ? 'dense vectors' : 'entity match'}
          </Btn>
        ))}
      </div>
      <div className="space-y-2">
        {order.map((idx, pos) => (
          <div key={idx} className="grid grid-cols-[26px_150px_1fr] items-center gap-3 transition-all duration-500"
            style={{ opacity: scores[idx] > 0 ? 1 : 0.25 }}>
            <span className="font-mono text-[12px] text-white/25">{pos + 1}</span>
            <span className="text-[13px] font-mono" style={{ color: pos === 0 ? G : 'rgba(255,255,255,0.6)' }}>{DOCS[idx]}</span>
            <span className="h-[18px] rounded bg-white/[0.05] overflow-hidden">
              <span className="block h-full rounded transition-all duration-700"
                style={{ width: `${(scores[idx] / max) * 100}%`, background: pos === 0 ? G : 'rgba(255,255,255,0.16)' }} />
            </span>
          </div>
        ))}
      </div>
      <div className="text-[12px] text-white/30 mt-5 pt-4 border-t border-white/[0.06]">
        Reciprocal rank fusion: each signal contributes 1/(k + rank). No single signal decides the outcome —
        which is why turning one off degrades the ranking rather than breaking it.
      </div>
    </Panel>
  )
}

/* ─────────────── 5. planes ─────────────── */
const PLANES = [
  { k: 'y+', n: 'Documents', d: 'Provenance chunks, entities, community summaries with a compiled truth per topic.' },
  { k: 'x', n: 'Conversation', d: 'Turns as decision memory — confidence, decay, supersession, per-session threads.' },
  { k: 'y−', n: 'Code', d: 'Call/import structure and real function bodies across 22+ languages.' },
]
function PlaneStack() {
  const [hover, setHover] = useState<number | null>(null)
  return (
    <div className="grid sm:grid-cols-3 gap-3">
      {PLANES.map((p, i) => {
        const dim = hover !== null && hover !== i
        return (
          <div key={p.k} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
            className="rounded-xl border p-5 transition-all duration-300 cursor-default"
            style={{
              borderColor: hover === i ? G : 'rgba(255,255,255,0.09)',
              background: hover === i ? 'rgba(61,220,151,0.06)' : 'rgba(255,255,255,0.02)',
              opacity: dim ? 0.4 : 1, transform: hover === i ? 'translateY(-3px)' : 'none',
            }}>
            <div className="font-mono text-[12px]" style={{ color: hover === i ? G : 'rgba(255,255,255,0.35)' }}>{p.k}</div>
            <div className="text-[16px] text-white font-medium mt-1.5 mb-2">{p.n}</div>
            <div className="text-[13px] leading-[1.55] text-white/45">{p.d}</div>
          </div>
        )
      })}
    </div>
  )
}

/* ─────────────── 6. setup ─────────────── */
const SETUP: { tab: string; note: string; steps: [string, string][] }[] = [
  { tab: 'Run locally', note: 'Python 3.10+ and about 2 GB of disk for models and indexes.',
    steps: [
      ['git clone https://github.com/Aloneinthemultiverse/truthguard-rag.git\ncd truthguard-rag', 'get the code'],
      ['pip install -r requirements.txt', 'install dependencies'],
      ['cp .env.example .env', 'then set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL — any OpenAI-compatible endpoint, including a local Ollama on http://127.0.0.1:11434/v1'],
      ['python -m truthguard.make_corpus\npython -m truthguard.main ingest', 'build the seeded corpus and the index — zero LLM calls'],
      ['python -m truthguard.main ask "What is the travel reimbursement limit per trip?"', 'the dual-answer trap: 2023 says $300, 2024 says $500'],
    ] },
  { tab: 'Studio', note: 'The web interface, served from the same functions the MCP tools call.',
    steps: [
      ['uvicorn truthguard.api:app --port 7788', 'the API and Studio backend'],
      ['cd studio-ui && npm install && npm run dev', 'the UI on http://127.0.0.1:5178'],
      ['⚙ → fetch models', 'set the provider key and pick a model from what the provider actually serves'],
    ] },
  { tab: 'As MCP', note: 'A plain stdio server — every client that connects shares one graph on disk.',
    steps: [
      ['python -m truthguard.mcp_server', 'run it directly to check it starts'],
      ['claude mcp add truthguard -- python -m truthguard.mcp_server', 'Claude Code — restart and the twelve tools appear'],
      ['PYTHONPATH=/path/to/truthguard-rag\nTG_STORAGE_DIR=/path/to/truthguard-rag/storage/truthguard', 'set these in the client environment so it works from any folder'],
    ] },
  { tab: 'Expose it', note: 'Serving from a laptop. Unset TG_API_TOKEN is local mode with no auth; setting it turns on the gate.',
    steps: [
      ['TG_API_TOKEN=<random> uvicorn truthguard.api:app --port 7790', 'every request now needs the token; /config and /ingest return 403'],
      ['TG_ALLOWED_ORIGINS=https://your.site', 'CORS allowlist — other origins are refused'],
      ['TG_ALLOW_WRITE=1', 'only if you deliberately want writes back on while exposed'],
    ] },
]

function Setup() {
  const [tab, setTab] = useState(0)
  const s = SETUP[tab]
  return (
    <Panel className="p-6">
      <div className="flex flex-wrap gap-2 mb-5">
        {SETUP.map((x, i) => <Btn key={x.tab} on={i === tab} onClick={() => setTab(i)}>{x.tab}</Btn>)}
      </div>
      <div className="text-[13px] text-white/45 mb-6">{s.note}</div>
      <ol className="space-y-4">
        {s.steps.map(([cmd, why], i) => (
          <li key={i} className="flex gap-3.5">
            <span className="font-mono text-[11px] mt-2 shrink-0" style={{ color: G }}>
              {String(i + 1).padStart(2, '0')}
            </span>
            <div className="min-w-0 flex-1">
              <pre className="font-mono text-[12.5px] text-white/80 bg-black/50 border border-white/[0.08]
                rounded-md px-3.5 py-2.5 overflow-x-auto whitespace-pre">{cmd}</pre>
              <div className="text-[12.5px] text-white/40 mt-1.5 leading-[1.55]">{why}</div>
            </div>
          </li>
        ))}
      </ol>
    </Panel>
  )
}

/* ─────────────── page ─────────────── */
export default function Architecture() {
  return (
    <div className="min-h-full h-full overflow-y-auto bg-[#050505] text-white/85 relative">
      <div className="fixed inset-0 z-0 pointer-events-none">
        <KineticGrid dotColor="#5f6f66" lineColor={G} trailColor={G} spacing={34} radius={250} strength={4} />
      </div>
      <div className="relative z-10">
        <nav className="sticky top-0 z-30 border-b border-white/[0.07] bg-[#050505]/85 backdrop-blur-xl">
          <div className="mx-auto max-w-[1120px] px-8 h-[60px] flex items-center gap-3">
            <div className="w-6 h-6 rounded-md relative" style={{ background: G }}>
              <div className="absolute inset-[5px] rounded-[3px] bg-[#050505]" />
            </div>
            <b className="text-[15px] text-white font-semibold">TruthGuard</b>
            <span className="text-[13px] text-white/30">/ architecture</span>
            <div className="ml-auto flex gap-7 text-[13.5px] text-white/45">
              <a href="#pipeline" className="hover:text-white transition">Pipeline</a>
              <a href="#gate" className="hover:text-white transition">The gate</a>
              <a href="#time" className="hover:text-white transition">Time</a>
              <a href="#memory" className="hover:text-white transition">Memory</a>
              <a href="#setup" className="hover:text-white transition">Setup</a>
              <a href="#mcp" className="hover:text-white transition">MCP</a>
              <a href="/about" className="hover:text-white transition">About →</a>
            </div>
          </div>
        </nav>

        <div className="mx-auto max-w-[960px] px-8 pt-24 pb-6">
          <BlurFade inView={false}>
            <div className="text-[11.5px] uppercase tracking-[0.18em] font-medium mb-5" style={{ color: G }}>Architecture</div>
            <h1 className="font-serif-display text-[64px] leading-[1.02] text-white mb-7">
              Everything serves<br />one decision
            </h1>
            <p className="text-[18px] leading-[1.7] text-white/50 max-w-[700px]">
              Should this question be answered at all? Retrieval, fact extraction, temporal scoping and
              contradiction detection exist to answer that question before a single token is generated.
              Every component below is interactive — change the inputs and watch the system respond.
            </p>
          </BlurFade>
        </div>

        <Section id="pipeline" eyebrow="01 · Pipeline"
          title="Four stages, one gate"
          lead="Ingest normalizes messy input. Retrieval assembles candidates. The gate decides. Only then does the generator run.">
          <PipelineSim />
        </Section>

        <Section id="components" eyebrow="02 · Components"
          title={`${COMPONENTS.length} parts, one contract`}
          lead="Every service, store and client in the system. Filter by layer, select any component to see what it does, how it is built, and the specifics that matter.">
          <ArchMap />
          <div className="mt-5"><ComponentExplorer /></div>
        </Section>

        <Section id="gate" eyebrow="03 · The assessment gate"
          title="Where the answer is decided"
          lead="Four checks run cheapest-first. Their combination selects the response mode — the generator has no say in whether it should have been called.">
          <GateExplorer />
        </Section>

        <Section id="time" eyebrow="04 · Bi-temporal facts"
          title="A changed value is not a contradiction"
          lead="Every extracted fact carries a validity window. Two values for the same subject only conflict if they claim to be true at the same time — otherwise they are a history.">
          <TemporalSim />
        </Section>

        <Section id="retrieval" eyebrow="05 · Multi-signal retrieval"
          title="Three signals, no single point of failure"
          lead="Dense vectors catch meaning, BM25 catches exact terms, entity matching catches names and dates. Reciprocal rank fusion combines them.">
          <FusionSim />
        </Section>

        <Section id="memory" eyebrow="06 · Context memory"
          title="Three planes, one graph"
          lead="Documents, conversation and code are compiled into a single structure and cross-wired, so any claim traces to its source in one hop.">
          <PlaneStack />
          <BlurFade delay={0.1}>
            <div className="relative rounded-xl border border-white/[0.09] overflow-hidden h-[440px] bg-black mt-6">
              <div className="absolute inset-0 grid place-items-center text-white/20 text-[13px] text-center px-8">
                live graph — connect a backend to render it
              </div>
              {HAS_GRAPH && <iframe src={staticGraphUrl()} className="relative w-full h-full border-0 block" title="live context graph" />}
            </div>
          </BlurFade>
        </Section>

        <Section id="setup" eyebrow="07 · Setup"
          title="Running it yourself"
          lead="Clone, install, ingest, ask. The index is built with zero LLM calls, so everything up to the first question is free and offline.">
          <Setup />
        </Section>

        <Section id="mcp" eyebrow="08 · Interface"
          title="Twelve tools, any model"
          lead="The whole system is exposed as a stdio MCP server. Any client that speaks MCP — Claude Code, OpenCode, Antigravity, Cursor, Cherry Studio — connects to the same graph on disk and shares the same memory.">
          <MCPTools />
        </Section>

        <footer className="border-t border-white/[0.07] py-14 text-center text-[13px] text-white/30">
          <a href="/about" style={{ color: G }}>About</a> · <a href="/" style={{ color: G }}>Studio</a>
        </footer>
      </div>
    </div>
  )
}
