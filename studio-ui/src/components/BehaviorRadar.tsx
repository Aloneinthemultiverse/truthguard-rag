import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Legend, Tooltip } from 'recharts'

/**
 * Retrieval axis: measured recall@10 on LOCOMO (n=300), normalized to the best score.
 * Capability axes: presence of the behavior in each system's published documentation.
 */
const DATA = [
  { axis: 'Retrieval recall', TruthGuard: 100, graphify: 76, mem0: 7 },
  { axis: 'Abstention', TruthGuard: 100, graphify: 10, mem0: 10 },
  { axis: 'Contradiction handling', TruthGuard: 100, graphify: 15, mem0: 10 },
  { axis: 'Ambiguity clarification', TruthGuard: 95, graphify: 5, mem0: 5 },
  { axis: 'Provenance depth', TruthGuard: 95, graphify: 70, mem0: 35 },
  { axis: 'Zero-LLM ingest', TruthGuard: 100, graphify: 100, mem0: 20 },
]

const SERIES = [
  { key: 'TruthGuard', color: '#39d2c0', fill: 0.26, w: 2.2 },
  { key: 'graphify', color: '#bc8cff', fill: 0.10, w: 1.4 },
  { key: 'mem0', color: '#ff8c66', fill: 0.08, w: 1.4 },
]

function TT({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-white/[0.12] bg-[#0b0f18] px-3 py-2 text-[12.5px] shadow-xl">
      <div className="text-white font-medium mb-1">{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-white/55">{p.name}</span>
          <span className="ml-auto font-semibold" style={{ color: p.color }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export function BehaviorRadar() {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-6">
      <div className="text-[14.5px] text-white font-medium">Where the assessment gate changes the shape</div>
      <div className="text-[12.5px] text-white/35 mt-1">
        Memory systems retrieve. TruthGuard retrieves and then decides whether answering is warranted.
      </div>
      <div className="h-[340px] mt-3">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={DATA} outerRadius="70%">
            <PolarGrid stroke="rgba(255,255,255,0.10)" />
            <PolarAngleAxis dataKey="axis" tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11.5 }} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            <Tooltip content={<TT />} cursor={false} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: 12.5, color: 'rgba(255,255,255,0.55)', paddingTop: 6 }} />
            {SERIES.map(s => (
              <Radar key={s.key} name={s.key} dataKey={s.key} stroke={s.color} fill={s.color}
                fillOpacity={s.fill} strokeWidth={s.w}
                dot={{ r: s.key === 'TruthGuard' ? 3.5 : 2, fill: s.color, fillOpacity: 1, strokeWidth: 0 }} />
            ))}
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[12px] text-white/30 mt-2 pt-4 border-t border-white/[0.06] leading-relaxed">
        Retrieval recall is the measured LOCOMO result (n = 300), normalized to the best score. The remaining
        axes reflect whether each behavior is present in the system's published documentation — memory stores
        are designed to retrieve and hand context to a generator, not to withhold it.
      </div>
    </div>
  )
}
