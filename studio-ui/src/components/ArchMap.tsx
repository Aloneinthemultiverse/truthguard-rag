import { useState } from 'react'
import { COMPONENTS } from './ComponentExplorer'

const G = '#3ddc97'
const W = 1180, H = 560

type Pos = { x: number; y: number; w?: number }
const POS: Record<string, Pos> = {
  corpus:     { x: 60,  y: 120 },
  cli:        { x: 60,  y: 330 },
  ingest:     { x: 235, y: 120 },
  mistral:    { x: 235, y: 40 },
  embed:      { x: 235, y: 200 },
  turbovec:   { x: 420, y: 60 },
  bm25:       { x: 420, y: 140 },
  meta:       { x: 420, y: 220 },
  figures:    { x: 420, y: 300 },
  retrieve:   { x: 600, y: 180 },
  assess:     { x: 780, y: 180 },
  qkg:        { x: 780, y: 90 },
  controller: { x: 600, y: 330 },
  llm:        { x: 780, y: 420 },
  scg:        { x: 960, y: 300 },
  audit:      { x: 960, y: 380 },
  codegraph:  { x: 960, y: 220 },
  recall:     { x: 780, y: 300 },
  mcp:        { x: 60,  y: 430 },
  multimodal: { x: 235, y: 280 },
}

type Edge = [string, string, string?]
const EDGES: Edge[] = [
  ['corpus', 'ingest', 'documents'],
  ['ingest', 'mistral', 'escalate'],
  ['ingest', 'embed'],
  ['embed', 'turbovec'],
  ['ingest', 'bm25'],
  ['ingest', 'meta'],
  ['ingest', 'figures'],
  ['multimodal', 'embed'],
  ['cli', 'controller', 'ask'],
  ['mcp', 'controller'],
  ['mcp', 'recall'],
  ['mcp', 'ingest'],
  ['controller', 'retrieve', '1 retrieve'],
  ['turbovec', 'retrieve'],
  ['bm25', 'retrieve'],
  ['meta', 'retrieve'],
  ['retrieve', 'assess', '2 assess'],
  ['assess', 'qkg', 'triples'],
  ['assess', 'llm', 'extract'],
  ['assess', 'controller', '3 verdict'],
  ['controller', 'llm', '4 generate'],
  ['controller', 'scg', 'record turn'],
  ['scg', 'audit'],
  ['scg', 'codegraph'],
  ['recall', 'scg', 'past turns'],
  ['recall', 'controller'],
]

const NEI: Record<string, Set<string>> = {}
EDGES.forEach(([a, b]) => {
  ;(NEI[a] ??= new Set()).add(b)
  ;(NEI[b] ??= new Set()).add(a)
})

const BY_ID = Object.fromEntries(COMPONENTS.map(c => [c.id, c]))
const NW = 132, NH = 40

function curve(a: Pos, b: Pos) {
  const x1 = a.x + NW, y1 = a.y + NH / 2, x2 = b.x, y2 = b.y + NH / 2
  if (b.x <= a.x) {          // backward edge — route below
    const my = Math.max(y1, y2) + 58
    return `M${x1 - NW / 2},${a.y + NH} C${x1 - NW / 2},${my} ${x2 + NW / 2},${my} ${x2 + NW / 2},${b.y + NH}`
  }
  const mx = (x1 + x2) / 2
  return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`
}

export function ArchMap() {
  const [sel, setSel] = useState<string | null>('assess')
  const [hover, setHover] = useState<string | null>(null)
  const focus = hover ?? sel
  const near = focus ? NEI[focus] ?? new Set() : null
  const detail = sel ? BY_ID[sel] : null

  const isDim = (id: string) => focus ? !(id === focus || near!.has(id)) : false
  const edgeOn = (a: string, b: string) => focus ? (a === focus || b === focus) : false

  return (
    <div className="rounded-xl border border-white/[0.09] bg-white/[0.02] p-5">
      <div className="text-[12.5px] text-white/40 mb-3">
        Hover to trace connections · click to inspect
        {focus && <span className="ml-2 font-mono" style={{ color: G }}>{BY_ID[focus]?.label}</span>}
      </div>

      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[860px]" style={{ height: 'auto' }}>
          <defs>
            <marker id="ah" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
              <path d="M0,0 L7,3.5 L0,7 z" fill="rgba(255,255,255,0.28)" />
            </marker>
            <marker id="ahOn" markerWidth="8" markerHeight="8" refX="6.5" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill={G} />
            </marker>
            <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="3.2" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="glowSoft" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="2" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* layer bands */}
          {[['ingest', 150], ['store', 330], ['gate', 510], ['memory', 690]].map(() => null)}

          {/* edges */}
          {EDGES.map(([a, b, label], i) => {
            const pa = POS[a], pb = POS[b]
            if (!pa || !pb) return null
            const on = edgeOn(a, b)
            const dim = focus && !on
            return (
              <g key={i} opacity={dim ? 0.16 : 1}>
                <path d={curve(pa, pb)} fill="none"
                  stroke={on ? G : 'rgba(255,255,255,0.3)'} strokeWidth={on ? 2.4 : 1.1}
                  filter={on ? 'url(#glow)' : undefined}
                  markerEnd={on ? 'url(#ahOn)' : 'url(#ah)'} />
                {on && (
                  <circle r="3.4" fill="#fff" filter="url(#glow)">
                    <animateMotion dur="1.6s" repeatCount="indefinite" path={curve(pa, pb)} />
                  </circle>
                )}
                {label && on && (
                  <text x={(pa.x + NW + pb.x) / 2} y={(pa.y + pb.y) / 2 + NH / 2 - 7}
                    textAnchor="middle" fontSize="11" fontWeight="600" fill={G} fontFamily="ui-monospace,monospace">{label}</text>
                )}
              </g>
            )
          })}

          {/* nodes */}
          {COMPONENTS.map(c => {
            const p = POS[c.id]; if (!p) return null
            const on = focus === c.id
            const adj = focus && near!.has(c.id)
            const dim = isDim(c.id)
            return (
              <g key={c.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.3 : 1}
                onMouseEnter={() => setHover(c.id)} onMouseLeave={() => setHover(null)}
                onClick={() => setSel(c.id)} style={{ cursor: 'pointer' }}>
                <rect x={-8} y={-8} width={NW + 16} height={NH + 16} fill="transparent" />
                <rect width={NW} height={NH} rx={c.kind === 'database' ? 5 : 9}
                  fill={on ? 'rgba(61,220,151,0.3)' : adj ? 'rgba(61,220,151,0.12)' : 'rgba(255,255,255,0.04)'}
                  stroke={on ? G : adj ? G : 'rgba(255,255,255,0.22)'}
                  strokeWidth={on ? 2.2 : adj ? 1.5 : 1}
                  filter={on ? 'url(#glow)' : adj ? 'url(#glowSoft)' : undefined}
                  strokeDasharray={c.kind === 'client' ? '4 3' : undefined}
                  style={{ transition: 'all .18s ease' }} />
                <text x={10} y={16} fontSize="10" fill={on ? G : 'rgba(255,255,255,0.3)'}
                  fontFamily="ui-monospace,monospace">
                  {c.kind === 'database' ? '▪' : c.kind === 'client' ? '◇' : '▸'} {c.layer.toLowerCase()}
                </text>
                <text x={10} y={31} fontSize="12" fontWeight={on ? 600 : 400}
                  fill={on ? '#fff' : adj ? '#fff' : 'rgba(255,255,255,0.8)'}>
                  {c.label.length > 20 ? c.label.slice(0, 19) + '…' : c.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* detail strip */}
      {detail && (
        <div className="mt-4 rounded-lg border border-white/[0.09] bg-black/40 p-4" key={detail.id}>
          <div className="flex items-baseline gap-2.5 flex-wrap">
            <h4 className="text-[16px] text-white font-medium">{detail.label}</h4>
            <span className="text-[11px] font-mono text-white/25">{detail.kind} · {detail.layer}</span>
            <span className="ml-auto text-[11px] font-mono" style={{ color: G }}>
              {(NEI[detail.id]?.size ?? 0)} connections
            </span>
          </div>
          <p className="text-[13.5px] leading-[1.6] text-white/55 mt-2">{detail.desc}</p>
          {detail.detail && (
            <ul className="mt-3 space-y-1.5">
              {detail.detail.map(d => (
                <li key={d} className="flex gap-2 text-[12.5px] leading-[1.55] text-white/40">
                  <span style={{ color: G }}>—</span><span>{d}</span></li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-1.5 mt-3.5 pt-3 border-t border-white/[0.07]">
            {detail.tech.map(t => (
              <span key={t} className="text-[11px] font-mono px-2 py-0.5 rounded border border-white/[0.1] text-white/40">{t}</span>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-5 mt-3 text-[11px] font-mono text-white/25">
        <span>▸ service</span><span>▪ store</span><span>◇ client</span>
      </div>
    </div>
  )
}
