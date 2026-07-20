import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { BorderBeam } from '@/components/magicui/border-beam'
import { NumberTicker } from '@/components/magicui/number-ticker'
import { AnimatedShinyText } from '@/components/magicui/animated-shiny-text'

const API = 'http://127.0.0.1:7788'
const GRAPH = 'http://127.0.0.1:7787/FULL_3plane_clean.html'

type Trace = { step: string }
type Msg = {
  role: 'q' | 'a'; text?: string; kind?: string; trace?: Trace[]
  confidence?: number | null; band?: string; citations?: string[]
  dual?: { object?: string; value?: string; source?: string }[]; loading?: boolean
}

const EXAMPLES = [
  'what is the travel reimbursement limit?',
  'is the travel limit $300 or $500?',
  'what is the meal allowance?',
]

function Chip({ t, i }: { t: string; i: number }) {
  const warn = /clash|contradic|insufficient|refus|unavail/.test(t)
  const bad = /error/.test(t)
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: i * 0.07 }}
      className={`text-[11px] font-medium px-2.5 py-[3px] rounded-full border ${
        bad ? 'bg-[#2e1414] text-[#ff6b6b] border-[#4a1c1c]'
        : warn ? 'bg-[#2e2410] text-amber border-[#4a3a12]'
        : 'bg-[#0f2b2a] text-teal border-[#1c4a45]'}`}>{t}</motion.span>
  )
}

function Ring({ v }: { v: number }) {
  const pct = Math.round(v * 100)
  const color = v >= 0.75 ? '#39d2c0' : v >= 0.4 ? '#e3b341' : '#ff6b6b'
  return (
    <div className="relative w-10 h-10 shrink-0 rounded-full grid place-items-center"
      style={{ background: `conic-gradient(${color} ${pct}%, #182338 0)` }}>
      <div className="absolute inset-1 rounded-full bg-panel" />
      <span className="relative text-[11px] font-semibold">{pct}</span>
    </div>
  )
}

export default function App() {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [q, setQ] = useState('')
  const [stats, setStats] = useState({ nodes: 0, turns: 0 })
  const [greeted, setGreeted] = useState(true)
  const pending = useRef<string | null>(null)
  const scroller = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const poll = async () => {
      try { const s = await (await fetch(API + '/stats')).json(); setStats({ nodes: s.nodes, turns: s.turns }) } catch {}
    }
    poll(); const id = setInterval(poll, 6000); return () => clearInterval(id)
  }, [])
  useEffect(() => { scroller.current?.scrollTo({ top: 9e9, behavior: 'smooth' }) }, [msgs])

  async function ask(text: string) {
    text = text.trim(); if (!text) return
    if (greeted) setGreeted(false)
    setQ('')
    setMsgs(m => [...m, { role: 'q', text }, { role: 'a', loading: true }])
    try {
      const body: any = pending.current ? { question: pending.current, followup: text } : { question: text }
      pending.current = null
      const r = await (await fetch(API + '/ask', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })).json()
      if (r.kind === 'clarify') pending.current = text
      setMsgs(m => { const c = [...m]; c[c.length - 1] = { role: 'a', ...r }; return c })
    } catch {
      setMsgs(m => { const c = [...m]; c[c.length - 1] = { role: 'a', text: 'API offline — run: uvicorn truthguard.api:app --port 7788', kind: 'error', trace: [{ step: 'error' }] }; return c })
    }
  }

  async function onDrop(e: React.DragEvent) {
    e.preventDefault(); const f = e.dataTransfer.files[0]; if (!f) return
    const fd = new FormData(); fd.append('file', f)
    setMsgs(m => [...m, { role: 'a', text: `ingesting ${f.name}…`, trace: [{ step: 'ingest' }], kind: 'ingest' }])
    try {
      const r = await (await fetch(API + '/ingest/document', { method: 'POST', body: fd })).json()
      setMsgs(m => { const c = [...m]; c[c.length - 1] = { role: 'a', text: `✓ ${r.file} — ${r.total_chunks} chunks (${r.engine})`, trace: [{ step: 'ingest' }], kind: 'ingested' }; return c })
    } catch {}
  }

  return (
    <div className="h-full flex flex-col">
      {/* header */}
      <header className="flex items-center gap-3.5 px-5 py-3 border-b border-line bg-[#0a0f1dcc] backdrop-blur-xl z-10">
        <div className="w-[30px] h-[30px] rounded-[9px] relative shrink-0"
          style={{ background: 'conic-gradient(from 210deg,#39d2c0,#bc8cff,#ff8c66,#39d2c0)', boxShadow: '0 0 22px #39d2c055' }}>
          <div className="absolute inset-[6px] rounded-[5px] bg-[#0b1120]" />
        </div>
        <div>
          <div className="text-[15px] font-semibold">TruthGuard Studio</div>
          <div className="text-[11px] text-mut">self-correcting RAG · 3-plane context memory</div>
        </div>
        <div className="ml-auto flex gap-2 items-center">
          <span className="flex items-center gap-1.5 text-xs text-mut bg-[#0d1426] border border-line px-3 py-[5px] rounded-full">
            <span className="w-[7px] h-[7px] rounded-full bg-[#41d18a] animate-pulse" style={{ boxShadow: '0 0 8px #41d18a' }} />live
          </span>
          <span className="text-xs text-mut bg-[#0d1426] border border-line px-3 py-[5px] rounded-full">
            <b className="text-teal font-semibold"><NumberTicker value={stats.nodes} /></b> nodes · <b className="text-teal font-semibold">{stats.turns}</b> turns
          </span>
        </div>
      </header>

      <main className="flex-1 grid grid-cols-[58px_1.25fr_1fr] min-h-0">
        {/* nav */}
        <nav className="flex flex-col items-center gap-1.5 py-3.5 border-r border-line bg-[#0a0f1d]">
          {['◆', '◈', '⌘', '▤'].map((c, i) => (
            <div key={i} className={`w-[38px] h-[38px] rounded-[11px] grid place-items-center cursor-pointer transition text-[18px] ${
              i === 0 ? 'text-teal bg-[#0f2b2a]' : 'text-[#5b6b8c] hover:text-white hover:bg-[#131f36]'}`}
              onClick={() => i === 2 && window.open('/architecture.html', '_blank')}>{c}</div>
          ))}
        </nav>

        {/* chat */}
        <div className="flex flex-col min-w-0 border-r border-line">
          <div ref={scroller} className="flex-1 overflow-y-auto px-6 pt-6 pb-2 flex flex-col gap-4">
            {greeted ? (
              <div className="m-auto text-center max-w-[360px] text-mut text-[13px] leading-relaxed">
                <div className="text-white text-[15px] font-semibold mb-1.5">Ask your documents, code, or past chats</div>
                Every answer shows its reasoning trace, confidence, and sources — and refuses or dual-answers instead of guessing.
                <div className="mt-3 flex flex-wrap gap-2 justify-center">
                  {EXAMPLES.map(e => (
                    <span key={e} onClick={() => ask(e)}
                      className="text-xs text-teal bg-[#0f2b2a] border border-[#1c4a45] px-3 py-1.5 rounded-full cursor-pointer hover:bg-[#143a37]">{e}</span>
                  ))}
                </div>
              </div>
            ) : msgs.map((m, i) => (
              <AnimatePresence key={i}>
                {m.role === 'q' ? (
                  <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    className="self-end max-w-[78%] px-4 py-2.5 rounded-[16px_16px_4px_16px] text-sm leading-relaxed border border-[#28395c]"
                    style={{ background: 'linear-gradient(135deg,#213255,#182740)' }}>{m.text}</motion.div>
                ) : (
                  <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    className="self-start max-w-[92%] relative px-4 py-3.5 rounded-[16px_16px_16px_4px] text-sm leading-relaxed bg-panel border border-line overflow-hidden">
                    {(m.kind === 'clarify' || m.kind === 'dual_answer') && <BorderBeam duration={5} />}
                    {m.loading ? (
                      <AnimatedShinyText className="text-[13px]">retrieve → assess → verify…</AnimatedShinyText>
                    ) : (<>
                      <div className="flex gap-1.5 flex-wrap mb-3">
                        {(m.trace || []).map((t, j) => <Chip key={j} t={t.step} i={j} />)}
                        {m.kind && <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: (m.trace?.length || 0) * 0.07 }}
                          className="text-[11px] font-medium px-2.5 py-[3px] rounded-full bg-[#221a3d] text-purple border border-[#3a2d5c]">{m.kind}</motion.span>}
                      </div>
                      {m.dual && m.dual.length >= 2 ? (
                        <div className="grid grid-cols-2 gap-2.5">
                          {m.dual.slice(0, 2).map((d, j) => (
                            <div key={j} className="border border-[#28395c] rounded-xl px-3 py-2.5 bg-[#0c1424]">
                              <div className="text-base font-semibold">{d.object || d.value}</div>
                              <div className="text-[11px] text-mut mt-1">{d.source}</div>
                            </div>
                          ))}
                        </div>
                      ) : <div className="whitespace-pre-wrap">{m.text}</div>}
                      {m.confidence != null && (
                        <div className="flex items-center gap-2.5 mt-3">
                          <Ring v={m.confidence} />
                          <div className="text-xs text-mut">confidence · <b className="text-white">{m.band}</b></div>
                        </div>
                      )}
                      {m.citations && m.citations.length > 0 && (
                        <div className="mt-2.5 flex gap-1.5 flex-wrap">
                          {m.citations.map((c, j) => <span key={j} className="text-[11px] text-[#5ea1ff] bg-[#0d1a30] border border-[#1a3050] px-2.5 py-1 rounded-lg">{c}</span>)}
                        </div>
                      )}
                    </>)}
                  </motion.div>
                )}
              </AnimatePresence>
            ))}
          </div>

          <div className="px-6">
            <div onDragOver={e => e.preventDefault()} onDrop={onDrop}
              className="border-[1.5px] border-dashed border-[#28395c] rounded-xl p-2.5 text-center text-[12.5px] text-[#5b6b8c] mb-3 transition hover:border-teal hover:text-teal">
              drop a PDF · DOCX · MD to ingest — the graph grows live
            </div>
          </div>
          <div className="flex gap-2.5 px-6 pb-5">
            <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask(q)}
              placeholder="Ask anything…"
              className="flex-1 bg-panel border border-[#28395c] rounded-[13px] text-white px-4 py-3 text-sm outline-none focus:border-teal transition" />
            <button onClick={() => ask(q)}
              className="rounded-[13px] text-[#052018] font-semibold px-5 text-sm transition hover:brightness-110 active:scale-95"
              style={{ background: 'linear-gradient(135deg,#39d2c0,#2ba894)' }}>Ask</button>
          </div>
        </div>

        {/* graph */}
        <div className="flex flex-col min-w-0">
          <div className="flex gap-1 px-4 py-2.5 border-b border-line items-center">
            <span className="text-xs text-white bg-[#131f36] px-3 py-1.5 rounded-lg">3D graph</span>
            <span className="ml-auto text-xs text-teal font-semibold"><NumberTicker value={stats.nodes} /> nodes</span>
          </div>
          <iframe src={GRAPH} className="flex-1 w-full border-0 bg-[#05070f]" />
        </div>
      </main>
    </div>
  )
}
