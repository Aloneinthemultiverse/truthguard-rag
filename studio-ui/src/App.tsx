import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { NumberTicker } from '@/components/magicui/number-ticker'
import { AnimatedShinyText } from '@/components/magicui/animated-shiny-text'
import { apiFetch, graphUrl, HAS_GRAPH, API } from '@/lib/api'

const G = '#3ddc97'


type Msg = { role: 'q' | 'a'; text?: string; kind?: string; trace?: { step: string }[]
  confidence?: number | null; band?: string; citations?: string[]; loading?: boolean }

const EXAMPLES = ['what is the travel reimbursement limit?', 'is the travel limit $300 or $500?', 'what is the meal allowance?']

function Chip({ t, i }: { t: string; i: number }) {
  const warn = /clash|contradic|insufficient|refus|unavail|error/.test(t)
  return (
    <motion.span initial={{ opacity: 0, scale: .85 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * .07 }}
      className="text-[11px] font-medium px-2.5 py-[3px] rounded-full border"
      style={warn ? { background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.75)', borderColor: 'rgba(255,255,255,0.2)' }
        : { background: 'rgba(61,220,151,0.1)', color: G, borderColor: 'rgba(61,220,151,0.3)' }}>{t}</motion.span>
  )
}

function Settings({ onClose }: { onClose: () => void }) {
  const [cfg, setCfg] = useState<any>(null)
  const [f, setF] = useState<any>({})
  const [saved, setSaved] = useState('')
  useEffect(() => { apiFetch('/config').then(r => r.json()).then(setCfg).catch(() => {}) }, [])
  const save = async () => {
    setSaved('saving…')
    try {
      const r = await (await apiFetch('/config', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(f) })).json()
      setSaved(r.ok ? `saved — ${r.updated.join(', ')}` : r.error)
      apiFetch('/config').then(x => x.json()).then(setCfg)
      setF({})
    } catch { setSaved('failed — is the API running?') }
  }
  // Known endpoints, so switching providers is one click instead of recalling a URL.
  const PRESETS: [string, string, string][] = [
    ['Ollama (local)', 'http://127.0.0.1:11434/v1', 'openai'],
    ['NVIDIA NIM', 'https://integrate.api.nvidia.com/v1', 'openai'],
    ['OpenAI', 'https://api.openai.com/v1', 'openai'],
    ['Anthropic', 'https://api.anthropic.com', 'anthropic'],
  ]
  const [models, setModels] = useState<string[]>([])
  const [loadingModels, setLoadingModels] = useState(false)

  // Ask the provider what it serves. Uses whatever is typed in the form so a new
  // endpoint can be probed before its key is saved.
  const loadModels = async () => {
    setLoadingModels(true)
    try {
      const p = new URLSearchParams()
      if (f.llm_base_url) p.set('base_url', f.llm_base_url)
      if (f.llm_api_key) p.set('api_key', f.llm_api_key)
      const r = await (await apiFetch(`/models?${p}`)).json()
      setModels(r.models || [])
      if (!r.models?.length) setSaved(r.error ? `no models: ${r.error}` : 'provider returned no models')
    } catch { setSaved('could not reach the provider') }
    setLoadingModels(false)
  }

  const Field = ({ k, label, ph, cur }: any) => (
    <label className="block mb-4">
      <div className="flex items-baseline gap-2 mb-1.5">
        <span className="text-[13px] text-white/70">{label}</span>
        {cur && <span className="font-mono text-[11px] text-white/25">current: {cur}</span>}
      </div>
      <input type={k.includes('key') ? 'password' : 'text'} placeholder={ph}
        value={f[k] ?? ''} onChange={e => setF({ ...f, [k]: e.target.value })}
        className="w-full bg-black/50 border border-white/[0.12] rounded-lg px-3.5 py-2.5 text-[13px]
          text-white outline-none focus:border-[#3ddc97] transition font-mono" />
    </label>
  )
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="absolute inset-0 z-50 bg-black/70 backdrop-blur-sm grid place-items-center p-6" onClick={onClose}>
      <motion.div initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }} onClick={e => e.stopPropagation()}
        className="w-full max-w-[520px] rounded-2xl border border-white/[0.12] bg-[#0a0d10] p-7">
        <div className="flex items-baseline mb-1">
          <h3 className="font-serif-display text-[26px] text-white">Providers</h3>
          <button onClick={onClose} className="ml-auto text-white/30 hover:text-white text-[20px] leading-none">×</button>
        </div>
        <p className="text-[13px] text-white/40 mb-6 leading-relaxed">
          Keys are written to <span className="font-mono text-white/60">.env</span> on this machine and never leave it.
          Leave a field blank to keep its current value.
        </p>
        <div className="flex gap-2 mb-5">
          {[['llm_ready', 'LLM'], ['ocr_ready', 'Mistral OCR']].map(([k, l]) => (
            <span key={k} className="text-[11.5px] px-2.5 py-1 rounded-md border font-mono"
              style={cfg?.[k] ? { color: G, borderColor: 'rgba(61,220,151,0.35)', background: 'rgba(61,220,151,0.08)' }
                : { color: 'rgba(255,255,255,0.3)', borderColor: 'rgba(255,255,255,0.12)' }}>
              {l} {cfg?.[k] ? 'connected' : 'not set'}
            </span>
          ))}
        </div>
        <div className="text-[12.5px] text-white/45 mb-2">Quick setup</div>
        <div className="flex flex-wrap gap-2 mb-5">
          {PRESETS.map(([name, url, prov]) => (
            <button key={name} onClick={() => { setF({ ...f, llm_base_url: url, llm_provider: prov }); setModels([]) }}
              className="text-[12px] px-3 py-1.5 rounded-lg border transition"
              style={f.llm_base_url === url
                ? { background: G, borderColor: G, color: '#000', fontWeight: 500 }
                : { borderColor: 'rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.55)' }}>{name}</button>
          ))}
        </div>

        <Field k="llm_api_key" label="LLM API key" ph="nvapi-… / sk-… (any value for Ollama)" cur={cfg?.llm_api_key} />
        <Field k="llm_base_url" label="LLM base URL" ph="http://127.0.0.1:11434/v1" cur={cfg?.llm_base_url} />

        {/* model: list what the provider actually serves rather than making the
            user type an exact id — a wrong id is a 404 with no clue why */}
        <label className="block mb-4">
          <div className="flex items-baseline gap-2 mb-1.5">
            <span className="text-[13px] text-white/70">Model</span>
            {cfg?.llm_model && <span className="font-mono text-[11px] text-white/25">current: {cfg.llm_model}</span>}
            <button onClick={loadModels} disabled={loadingModels}
              className="ml-auto text-[11.5px] px-2 py-0.5 rounded border border-white/[0.15] text-white/55 hover:text-white transition">
              {loadingModels ? 'checking…' : models.length ? 'refresh' : 'fetch models'}
            </button>
          </div>
          {models.length > 0 ? (
            <select value={f.llm_model ?? ''} onChange={e => setF({ ...f, llm_model: e.target.value })}
              className="w-full bg-black/50 border border-white/[0.12] rounded-lg px-3.5 py-2.5 text-[13px]
                text-white outline-none focus:border-[#3ddc97] transition font-mono">
              <option value="">— pick a model ({models.length} available) —</option>
              {models.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          ) : (
            <input type="text" placeholder="qwen2.5:3b-instruct" value={f.llm_model ?? ''}
              onChange={e => setF({ ...f, llm_model: e.target.value })}
              className="w-full bg-black/50 border border-white/[0.12] rounded-lg px-3.5 py-2.5 text-[13px]
                text-white outline-none focus:border-[#3ddc97] transition font-mono" />
          )}
        </label>

        <Field k="llm_provider" label="Provider" ph="openai | anthropic" cur={cfg?.llm_provider} />
        <div className="h-px bg-white/[0.08] my-5" />
        <Field k="mistral_ocr_api_key" label="Mistral OCR key (optional)" ph="for tier-2 OCR escalation" cur={cfg?.mistral_ocr_api_key} />
        <div className="flex items-center gap-3 mt-6">
          <button onClick={save} className="px-5 py-2.5 rounded-lg text-[14px] font-medium text-black"
            style={{ background: G }}>Save</button>
          <span className="text-[12.5px]" style={{ color: saved.startsWith('saved') ? G : 'rgba(255,255,255,0.4)' }}>{saved}</span>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default function App() {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [q, setQ] = useState('')
  const [stats, setStats] = useState({ nodes: 0, turns: 0 })
  const [ready, setReady] = useState<boolean | null>(null)
  const [showSet, setShowSet] = useState(false)
  // The graph is its own page rather than a side panel — at half width the
  // 3-plane layout is unreadable, and the chat column was cramped too.
  const [view, setView] = useState<'chat' | 'graph'>('chat')
  const [greeted, setGreeted] = useState(true)
  const pending = useRef<string | null>(null)
  const scroller = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const poll = async () => {
      try {
        const s = await (await apiFetch('/stats')).json(); setStats({ nodes: s.nodes, turns: s.turns })
        const c = await (await apiFetch('/config')).json(); setReady(c.llm_ready)
      } catch { setReady(false) }
    }
    poll(); const id = setInterval(poll, 8000); return () => clearInterval(id)
  }, [showSet])
  useEffect(() => { scroller.current?.scrollTo({ top: 9e9, behavior: 'smooth' }) }, [msgs])

  async function ask(text: string) {
    text = text.trim(); if (!text) return
    if (greeted) setGreeted(false)
    setQ('')
    setMsgs(m => [...m, { role: 'q', text }, { role: 'a', loading: true }])
    try {
      const body: any = pending.current ? { question: pending.current, followup: text } : { question: text }
      pending.current = null
      // Kick off the job, then poll. An answer takes minutes, and one HTTP
      // request held open that long dies with the tunnel; short polls don't.
      const { job_id } = await (await apiFetch('/ask_async', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json()
      let r: any = null
      for (let i = 0; i < 300 && !r; i++) {                 // ~10 min ceiling
        await new Promise(res => setTimeout(res, 2000))
        try {
          const j = await (await apiFetch(`/ask_job/${job_id}`)).json()
          if (j.status === 'done' || j.status === 'error') r = j.result
        } catch { /* a dropped poll is fine — the next one retries */ }
      }
      if (!r) throw new Error('timed out waiting for the answer')
      if (r.kind === 'clarify') pending.current = text
      setMsgs(m => { const c = [...m]; c[c.length - 1] = { role: 'a', ...r }; return c })
    } catch {
      setMsgs(m => { const c = [...m]; c[c.length - 1] = { role: 'a', kind: 'error',
        text: 'API not reachable — run: uvicorn truthguard.api:app --port 7788', trace: [{ step: 'offline' }] }; return c })
    }
  }

  async function onDrop(e: React.DragEvent) {
    e.preventDefault(); const f = e.dataTransfer.files[0]; if (!f) return
    const fd = new FormData(); fd.append('file', f)
    setMsgs(m => [...m, { role: 'a', text: `ingesting ${f.name}…`, trace: [{ step: 'ingest' }] }])
    try {
      const r = await (await apiFetch('/ingest/document', { method: 'POST', body: fd })).json()
      setMsgs(m => { const c = [...m]; c[c.length - 1] = { role: 'a', kind: 'ingested',
        text: `${r.file} — ${r.total_chunks} chunks (${r.engine})`, trace: [{ step: 'ingest' }] }; return c })
    } catch {}
  }

  return (
    <div className="h-full flex flex-col bg-[#050505] text-white/85 relative">
      <AnimatePresence>{showSet && <Settings onClose={() => setShowSet(false)} />}</AnimatePresence>

      <header className="flex items-center gap-3.5 px-5 py-3 border-b border-white/[0.07] bg-black/60 backdrop-blur-xl z-10">
        <div className="w-[26px] h-[26px] rounded-lg relative shrink-0" style={{ background: G }}>
          <div className="absolute inset-[5px] rounded-[3px] bg-[#050505]" />
        </div>
        <div>
          <div className="text-[15px] font-semibold text-white">TruthGuard Studio</div>
          <div className="text-[11px] text-white/35">self-correcting RAG · 3-plane context memory</div>
        </div>
        <div className="ml-5 flex gap-1 p-1 rounded-xl border border-white/[0.09] bg-white/[0.02]">
          {(['chat', 'graph'] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              className="text-[12.5px] px-3.5 py-1.5 rounded-lg transition"
              style={view === v ? { background: G, color: '#000', fontWeight: 500 }
                : { color: 'rgba(255,255,255,0.5)' }}>
              {v === 'chat' ? 'Chat' : '3D graph'}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2.5 text-[12.5px]">
          <a href="/about" className="text-white/40 hover:text-white transition px-2">About</a>
          <a href="/architecture" className="text-white/40 hover:text-white transition px-2">Architecture</a>
          <span className="px-3 py-[5px] rounded-full border font-mono text-[11.5px]"
            style={ready ? { color: G, borderColor: 'rgba(61,220,151,0.3)', background: 'rgba(61,220,151,0.07)' }
              : { color: 'rgba(255,255,255,0.4)', borderColor: 'rgba(255,255,255,0.14)' }}>
            {ready === null ? '…' : ready ? 'llm connected' : 'no llm key'}
          </span>
          <span className="text-white/35 text-[12px] font-mono">
            <NumberTicker value={stats.nodes} /> nodes · {stats.turns} turns
          </span>
          <button onClick={() => setShowSet(true)}
            className="w-8 h-8 rounded-lg border border-white/[0.12] text-white/50 hover:text-white hover:border-white/30 transition">⚙</button>
        </div>
      </header>

      <main className="flex-1 min-h-0 flex flex-col" style={{ display: view === 'chat' ? 'flex' : 'none' }}>
        <div className="flex flex-col min-w-0 flex-1 mx-auto w-full max-w-[900px]">
          <div ref={scroller} className="flex-1 overflow-y-auto px-6 pt-6 pb-2 flex flex-col gap-4">
            {greeted ? (
              <div className="m-auto text-center max-w-[380px]">
                <div className="font-serif-display text-[30px] text-white mb-3">Ask your corpus</div>
                <p className="text-[13.5px] text-white/40 leading-relaxed mb-5">
                  Every answer shows its reasoning trace, confidence and sources — and refuses or dual-answers
                  rather than guessing.
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {EXAMPLES.map(e => (
                    <span key={e} onClick={() => ask(e)}
                      className="text-[12px] px-3 py-1.5 rounded-full cursor-pointer transition border"
                      style={{ color: G, borderColor: 'rgba(61,220,151,0.3)', background: 'rgba(61,220,151,0.07)' }}>{e}</span>
                  ))}
                </div>
                {ready === false && (
                  <button onClick={() => setShowSet(true)}
                    className="mt-6 text-[12.5px] text-white/50 underline underline-offset-4 hover:text-white">
                    no LLM key set — add one
                  </button>
                )}
              </div>
            ) : msgs.map((m, i) => m.role === 'q' ? (
              <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className="self-end max-w-[78%] px-4 py-2.5 rounded-[14px_14px_4px_14px] text-[14px] leading-relaxed
                  border border-white/[0.12] bg-white/[0.05]">{m.text}</motion.div>
            ) : (
              <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className="self-start max-w-[92%] px-4 py-3.5 rounded-[14px_14px_14px_4px] text-[14px] leading-relaxed
                  border border-white/[0.09] bg-white/[0.02]">
                {m.loading ? <AnimatedShinyText className="text-[13px]">retrieve → assess → verify…</AnimatedShinyText> : (<>
                  <div className="flex gap-1.5 flex-wrap mb-3">
                    {(m.trace || []).map((t, j) => <Chip key={j} t={t.step} i={j} />)}
                    {m.kind && <Chip t={m.kind} i={(m.trace?.length || 0)} />}
                  </div>
                  <div className="whitespace-pre-wrap text-white/80">{m.text}</div>
                  {m.confidence != null && (
                    <div className="flex items-center gap-3 mt-3.5">
                      <div className="relative w-9 h-9 grid place-items-center rounded-full"
                        style={{ background: `conic-gradient(${G} ${Math.round(m.confidence * 100)}%, rgba(255,255,255,0.08) 0)` }}>
                        <div className="absolute inset-[3px] rounded-full bg-[#0a0d10]" />
                        <span className="relative text-[11px] font-semibold">{Math.round(m.confidence * 100)}</span>
                      </div>
                      <span className="text-[12.5px] text-white/40">confidence · <b className="text-white/80">{m.band}</b></span>
                    </div>
                  )}
                  {m.citations?.length ? (
                    <div className="mt-3 flex gap-1.5 flex-wrap">
                      {m.citations.map((c, j) => (
                        <span key={j} className="text-[11px] font-mono px-2.5 py-1 rounded-md border border-white/[0.1] text-white/45">{c}</span>
                      ))}
                    </div>
                  ) : null}
                </>)}
              </motion.div>
            ))}
          </div>

          <div className="px-6">
            <div onDragOver={e => e.preventDefault()} onDrop={onDrop}
              className="border border-dashed border-white/[0.14] rounded-xl p-2.5 text-center text-[12.5px]
                text-white/30 mb-3 transition hover:border-[#3ddc97] hover:text-[#3ddc97]">
              drop a PDF · DOCX · MD to ingest — the graph grows live
            </div>
          </div>
          <div className="flex gap-2.5 px-6 pb-5">
            <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask(q)}
              placeholder="Ask anything…"
              className="flex-1 bg-white/[0.03] border border-white/[0.12] rounded-xl text-white px-4 py-3
                text-[14px] outline-none focus:border-[#3ddc97] transition" />
            <button onClick={() => ask(q)} className="rounded-xl text-black font-medium px-5 text-[14px]
              transition hover:brightness-110 active:scale-95" style={{ background: G }}>Ask</button>
          </div>
        </div>

      </main>

      {/* Graph page. Kept mounted and hidden rather than unmounted, so switching
          tabs does not reload the iframe and lose the camera position. */}
      <main className="flex-1 min-h-0 flex-col" style={{ display: view === 'graph' ? 'flex' : 'none' }}>
        <div className="flex items-center gap-2.5 px-5 py-2.5 border-b border-white/[0.07]">
          <span className="text-[13px] text-white/70">3-plane context graph</span>
          <span className="text-[11.5px] text-white/30">
            documents above · conversation in the middle · code below — drag to rotate
          </span>
          <span className="ml-auto font-mono text-[11.5px]" style={{ color: G }}>
            {stats.nodes.toLocaleString()} nodes · live
          </span>
        </div>
        {HAS_GRAPH
          ? <iframe src={graphUrl()} className="flex-1 w-full border-0 bg-black" title="3-plane context graph" />
          : <div className="flex-1 grid place-items-center text-white/25 text-[13px] text-center px-8">
              No backend connected.<br />
              <span className="text-[11.5px] text-white/15">open Studio with ?api=&lt;url&gt;&amp;token=&lt;token&gt;</span>
            </div>}
      </main>
    </div>
  )
}
