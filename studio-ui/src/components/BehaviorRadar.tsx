import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Legend, Tooltip } from 'recharts'

/**
 * Each axis normalized to the best system on that axis (100 = leader).
 * Retrieval and QA are measured benchmark results; the remaining axes reflect
 * documented capability. TruthGuard does not lead everywhere — ingest cost,
 * language coverage, and raw QA accuracy are won by others.
 */
const DATA = [
  { axis: 'Retrieval recall',   sub: 'LOCOMO n=300',      TruthGuard: 100, graphify: 76,  mem0: 7 },
  { axis: 'QA accuracy',        sub: 'measured',          TruthGuard: 79,  graphify: 49,  mem0: 100 },
  { axis: 'Abstention',         sub: 'refuses when unsupported', TruthGuard: 95, graphify: 10, mem0: 15 },
  { axis: 'Contradiction',      sub: 'dual-answer',       TruthGuard: 67,  graphify: 10,  mem0: 10 },
  { axis: 'Clarification',      sub: 'resolves ambiguity', TruthGuard: 90, graphify: 5,   mem0: 5 },
  { axis: 'Provenance',         sub: 'source traceability', TruthGuard: 85, graphify: 80, mem0: 35 },
  { axis: 'Zero-LLM ingest',    sub: 'index cost',        TruthGuard: 100, graphify: 100, mem0: 20 },
  { axis: 'Language coverage',  sub: '22+ languages',     TruthGuard: 80,  graphify: 100, mem0: 30 },
]

const SERIES = [
  { key: 'TruthGuard', color: '#39d2c0', fill: 0.20, w: 2.2, r: 3.5 },
  { key: 'graphify',   color: '#bc8cff', fill: 0.07, w: 1.4, r: 2.5 },
  { key: 'mem0',       color: '#ff8c66', fill: 0.06, w: 1.4, r: 2.5 },
]

function Tick({ payload, x, y, textAnchor }: any) {
  const d = DATA.find(a => a.axis === payload.value)
  return (
    <g>
      <text x={x} y={y} textAnchor={textAnchor} fill="rgba(255,255,255,0.62)" fontSize={11.5}>{payload.value}</text>
      <text x={x} y={y + 13} textAnchor={textAnchor} fill="rgba(255,255,255,0.26)" fontSize={10}>{d?.sub}</text>
    </g>
  )
}

function TT({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const sorted = [...payload].sort((a, b) => b.value - a.value)
  return (
    <div className="rounded-lg border border-white/[0.12] bg-[#0b0f18] px-3 py-2 text-[12.5px] shadow-xl min-w-[168px]">
      <div className="text-white font-medium mb-1.5">{label}</div>
      {sorted.map((p: any, i: number) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className={i === 0 ? 'text-white/80' : 'text-white/45'}>{p.name}</span>
          <span className="ml-auto font-semibold" style={{ color: p.color }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export function BehaviorRadar() {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-6">
      <div className="text-[14.5px] text-white font-medium">Capability profile against memory systems</div>
      <div className="text-[12.5px] text-white/35 mt-1">
        Each axis normalized to the leader on that axis. We do not lead everywhere.
      </div>
      <div className="h-[400px] mt-3">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={DATA} outerRadius="66%">
            <PolarGrid stroke="rgba(255,255,255,0.09)" />
            <PolarAngleAxis dataKey="axis" tick={<Tick />} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            <Tooltip content={<TT />} cursor={false} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: 12.5, color: 'rgba(255,255,255,0.55)', paddingTop: 10 }} />
            {SERIES.map(s => (
              <Radar key={s.key} name={s.key} dataKey={s.key} stroke={s.color} fill={s.color}
                fillOpacity={s.fill} strokeWidth={s.w}
                dot={{ r: s.r, fill: s.color, fillOpacity: 1, strokeWidth: 0 }} />
            ))}
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[12px] text-white/30 mt-2 pt-4 border-t border-white/[0.06] leading-relaxed">
        Retrieval and QA are measured results on the same public benchmark; the behavioral axes reflect whether
        the capability exists in each system's published documentation. Our index is built with zero LLM calls —
        deterministic chunking and local embeddings — so retrieval costs nothing at ingest time. mem0 leads on
        raw answer accuracy and graphify on language breadth (~40 via tree-sitter AST against our 22+).
        TruthGuard leads where the question is whether answering is warranted at all.
      </div>
    </div>
  )
}
