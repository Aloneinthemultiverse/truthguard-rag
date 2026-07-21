import { useState } from 'react'

const G = '#3ddc97'

const TOOLS = [
  ['ask', 'question, followup?, baseline?', 'Runs the full self-correcting pipeline. Returns the verdict, confidence band, citations and the reasoning trace. Records the turn into the graph.'],
  ['get_context', 'question', 'The router call. Returns one ready-to-inject context block — document passages, code bodies, entities, compiled topic truths and past turns — bounded by a token budget.'],
  ['recall', 'question', 'Searches PAST conversation turns using DecisionMemory.query: similarity × confidence over active memories, with the documents and code each turn grounded on.'],
  ['ingest_project', 'repo_path, chat_path?', 'Absorbs a whole project in one call — the entire codebase, every document in the repo, and optionally a chat transcript, all cross-linked.'],
  ['ingest_document', 'path', 'Adds a PDF, DOCX, MD or TXT to the corpus. Scans run through the OCR ladder. Rebuilds the index and re-wires existing turns to the new document.'],
  ['ingest_chat', 'path', 'Imports a chat transcript — a Claude session .jsonl or any plain user:/assistant: text — as its own conversation chain, auto-linked to entities, docs and code.'],
  ['link_code_repo', 'path', 'Indexes a git repository as the code plane: structural graph plus AST function bodies across 22+ languages.'],
  ['query_code', 'symbol | cypher', 'Structural traversal of the code graph, zero LLM: a symbol\'s definition, its callers and its callees.'],
  ['graph_query', 'command, name, target?', 'Traverses the project graph: context, impact, find, edit_plan, path, report — every edge tagged EXTRACTED or INFERRED.'],
  ['rebuild_communities', '—', "Re-runs DecisionGraph's community recipe on all three planes: Louvain detection, summaries, compiled truth."],
  ['graph_stats', '—', 'Current node and edge counts per plane, turn count, community count.'],
  ['live_view_url', '—', 'URL of the auto-refreshing 3D graph view — keep it open and it grows as you chat.'],
]

const CLIENTS = [
  { id: 'claude', name: 'Claude Code',
    steps: ['claude mcp add truthguard -- python -m truthguard.mcp_server',
      'run it from the dg-core folder, or set cwd in ~/.claude.json',
      'restart Claude Code — the tools appear automatically'] },
  { id: 'opencode', name: 'OpenCode',
    steps: ['open ~/.config/opencode/opencode.json',
      'add an entry under "mcp": { "truthguard": { "type": "local", "command": ["python","-m","truthguard.mcp_server"], "enabled": true } }',
      'set PYTHONPATH and TG_STORAGE_DIR in "environment" so it works from any folder',
      'restart OpenCode'] },
  { id: 'antigravity', name: 'Antigravity',
    steps: ['add TruthGuard as a local stdio MCP server in the client settings',
      'command: python -m truthguard.mcp_server',
      'point the working directory at dg-core'] },
  { id: 'other', name: 'Any MCP client',
    steps: ['TruthGuard is a plain stdio MCP server — no client-specific code',
      'command: python -m truthguard.mcp_server',
      'works with Cherry Studio, Codex, Cursor, Gemini CLI and anything else speaking MCP',
      'the same graph is shared by every client that connects'] },
]

export function MCPTools() {
  const [sel, setSel] = useState(0)
  const [open, setOpen] = useState<string | null>('get_context')

  return (
    <div className="space-y-5">
      {/* tools */}
      <div className="rounded-xl border border-white/[0.09] bg-white/[0.02] p-5">
        <div className="flex items-baseline gap-2 mb-4">
          <span className="text-[13px] text-white/45">Twelve tools, one server</span>
          <span className="ml-auto font-mono text-[11px] text-white/25">stdio · MCP</span>
        </div>
        <div className="space-y-1.5">
          {TOOLS.map(([name, args, desc]) => {
            const on = open === name
            return (
              <div key={name} onClick={() => setOpen(on ? null : name)}
                className="rounded-lg border px-4 py-3 cursor-pointer transition-all duration-200"
                style={{ borderColor: on ? G : 'rgba(255,255,255,0.08)',
                  background: on ? 'rgba(61,220,151,0.06)' : 'transparent' }}>
                <div className="flex items-baseline gap-3 flex-wrap">
                  <span className="font-mono text-[13.5px]" style={{ color: on ? G : '#fff' }}>{name}</span>
                  <span className="font-mono text-[11.5px] text-white/25">({args})</span>
                  <span className="ml-auto text-white/20 text-[13px]">{on ? '−' : '+'}</span>
                </div>
                {on && <p className="text-[13px] leading-[1.6] text-white/55 mt-2.5 pr-6">{desc}</p>}
              </div>
            )
          })}
        </div>
      </div>

      {/* connect */}
      <div className="rounded-xl border border-white/[0.09] bg-white/[0.02] p-5">
        <div className="text-[13px] text-white/45 mb-4">Connect it to your client</div>
        <div className="flex flex-wrap gap-2 mb-6">
          {CLIENTS.map((c, i) => (
            <button key={c.id} onClick={() => setSel(i)}
              className="text-[12.5px] px-3.5 py-1.5 rounded-lg border transition"
              style={i === sel ? { background: G, borderColor: G, color: '#000', fontWeight: 500 }
                : { borderColor: 'rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.55)' }}>{c.name}</button>
          ))}
        </div>
        <ol className="space-y-3">
          {CLIENTS[sel].steps.map((s, i) => (
            <li key={i} className="flex gap-3.5">
              <span className="font-mono text-[11px] mt-[3px] shrink-0" style={{ color: G }}>{String(i + 1).padStart(2, '0')}</span>
              <span className={`text-[13.5px] leading-[1.6] ${s.includes('{') || s.startsWith('claude mcp') || s.startsWith('command:')
                ? 'font-mono text-[12.5px] text-white/70 bg-black/40 border border-white/[0.07] rounded-md px-3 py-2 break-all'
                : 'text-white/55'}`}>{s}</span>
            </li>
          ))}
        </ol>
        <div className="mt-6 pt-4 border-t border-white/[0.07] text-[12.5px] text-white/35 leading-relaxed">
          Every client talks to the same graph on disk. A conversation in one tool is recallable from another —
          that is the point of the router.
        </div>
      </div>
    </div>
  )
}

export const MCP_CLIENTS = ['Claude Code', 'OpenCode', 'Antigravity', 'Cherry Studio', 'Cursor', 'Codex', 'Gemini CLI']
