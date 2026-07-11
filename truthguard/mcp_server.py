"""TruthGuard MCP server — chat with the memory and WATCH THE GRAPH GROW.

Tools:
  ask(question, followup?, baseline?)  -> self-corrected answer (records a turn)
  ingest_document(path)                -> add a file to the corpus + reindex
  link_code_repo(path)                 -> gitnexus-index a repo as the y- plane
  rebuild_communities()                -> re-run DG community recipe on all planes
  graph_stats()                        -> nodes/edges/planes/turns
  live_view_url()                      -> URL of the auto-refreshing 3D view

Every mutating call re-exports graph3d_data.json; a tiny HTTP server serves
graph3d_live.html which polls it — the 3D view updates in place while you chat.

Connect (Claude Code):
  claude mcp add truthguard -- python -m truthguard.mcp_server
  (cwd must be the dg-core folder; or use absolute paths in .claude.json)
"""
import os
import sys
import json
import shutil
import asyncio
import threading
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.getenv("TG_LIVE_PORT", "7787"))

app = Server("truthguard")
_state = {"store": None, "llm": None}


def _store():
    if _state["store"] is None:
        from .chunk_store import ChunkStore
        _state["store"] = ChunkStore()
    return _state["store"]


def _llm():
    if _state["llm"] is None:
        from .llm import LLM
        _state["llm"] = LLM()
    return _state["llm"]


def _export_live_data():
    """Dump the 3-plane graph as JSON for the live 3D view."""
    try:
        from .viz3d import PLANE_Z, PLANE_COLOR, KIND, LINK_COLOR
        from .context_graph import ContextGraph
        from collections import Counter
        g = ContextGraph().g
        cites = Counter(v for u, v, e in g.edges(data=True)
                        if e.get("relation") == "grounds")
        nodes, links = [], []
        for n, d in g.nodes(data=True):
            p = d.get("plane", "spine")
            color = PLANE_COLOR.get(p) or KIND.get(d.get("kind"), "#bc8cff")
            if p == "knowledge" and cites.get(n, 0) >= 20:
                color = "#ff4d4d"
            label = (d.get("question") or d.get("summary") or d.get("source") or n)[:60]
            size = 8 if "community" in p else (6 if p == "spine" else 4)
            nodes.append({"id": n, "name": f"[{p}] {label}", "color": color,
                          "val": size, "fz": PLANE_Z.get(p, 0)})
        for u, v, e in g.edges(data=True):
            r = e.get("relation", "")
            links.append({"source": u, "target": v, "name": r,
                          "color": LINK_COLOR.get(r, "#555"),
                          "w": 2 if r in ("references_symbol", "calls") else 1})
        with open(os.path.join(ROOT, "graph3d_data.json"), "w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "links": links}, f)
    except Exception:
        pass


def _start_live_server():
    import http.server, functools
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=ROOT)
    handler.log_message = lambda *a, **k: None

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=ROOT, **k)
        def log_message(self, *a):
            pass

    def run():
        try:
            http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Quiet).serve_forever()
        except OSError:
            pass  # already running from a previous session
    threading.Thread(target=run, daemon=True).start()


TOOLS = [
    types.Tool(name="ask",
        description="Ask the TruthGuard self-correcting RAG a question. Detects "
                    "contradictions (dual-answers), ambiguity (clarifies), and missing "
                    "info (refuses with gap analysis). Records the turn into the 3-plane "
                    "context graph — the live 3D view grows with every call.",
        inputSchema={"type": "object", "properties": {
            "question": {"type": "string"},
            "followup": {"type": "string", "description": "answer to a prior clarify"},
            "baseline": {"type": "boolean", "description": "bypass the correction layer (ablation)"}},
            "required": ["question"]}),
    types.Tool(name="ingest_document",
        description="Add a document (PDF/DOCX/MD/TXT — scans OK, OCR runs) to the corpus "
                    "and rebuild the index. The knowledge plane grows.",
        inputSchema={"type": "object", "properties": {
            "path": {"type": "string", "description": "absolute path to the file"}},
            "required": ["path"]}),
    types.Tool(name="link_code_repo",
        description="Index a git repository with GitNexus as the y- code plane. Code "
                    "questions then answer structurally (callers, symbols) with zero LLM.",
        inputSchema={"type": "object", "properties": {
            "path": {"type": "string", "description": "absolute path to the repo"}},
            "required": ["path"]}),
    types.Tool(name="rebuild_communities",
        description="Re-run DecisionGraph's community recipe on all three planes "
                    "(topic communities on turns, semantic communities on knowledge).",
        inputSchema={"type": "object", "properties": {}}),
    types.Tool(name="graph_stats",
        description="Current 3-plane graph statistics: nodes/edges per plane, turns, communities.",
        inputSchema={"type": "object", "properties": {}}),
    types.Tool(name="recall",
        description="Search PAST conversation turns (DG DecisionMemory.query recipe): "
                    "embeds the question, finds similar old turns + their topic "
                    "communities, returns each with the documents/code it grounded on. "
                    "Use before answering anything that might have been discussed before.",
        inputSchema={"type": "object", "properties": {
            "question": {"type": "string"}}, "required": ["question"]}),
    types.Tool(name="live_view_url",
        description="URL of the live auto-refreshing 3D graph view (open in a browser and keep it open while chatting).",
        inputSchema={"type": "object", "properties": {}}),
]


@app.list_tools()
async def list_tools():
    return TOOLS


def _fmt_response(r: dict) -> str:
    out = [f"[{r['kind'].upper()}]"
           + (f" confidence={r['confidence']} ({r['band']})" if r.get("confidence") is not None else "")]
    out.append(r["text"])
    if r.get("citations"):
        out.append("Sources: " + " | ".join(r["citations"]))
    for f in r.get("figures") or []:
        out.append(f"[image] {f['figure']} -> {f['image_path']}")
    out.append("trace: " + " -> ".join(s["step"] for s in r["trace"]))
    out.append(f"(graph grew — refresh feeling not needed, live view updates itself)")
    return "\n".join(out)


@app.call_tool()
async def call_tool(name: str, args: dict):
    try:
        if name == "ask":
            from .controller import ask as _ask
            r = _ask(_store(), _llm(), args["question"],
                     baseline=bool(args.get("baseline")),
                     followup=args.get("followup"))
            _export_live_data()
            return [types.TextContent(type="text", text=_fmt_response(r))]

        if name == "ingest_document":
            src = args["path"]
            if not os.path.isfile(src):
                return [types.TextContent(type="text", text=f"file not found: {src}")]
            dst = os.path.join(config.CORPUS_DIR, os.path.basename(src))
            os.makedirs(config.CORPUS_DIR, exist_ok=True)
            shutil.copy2(src, dst)
            from .pipeline import ingest_corpus
            from .chunk_store import build_index
            chunks, report = ingest_corpus()
            engine = build_index()
            _state["store"] = None      # reload with new chunks
            _export_live_data()
            return [types.TextContent(type="text", text=
                f"ingested {os.path.basename(src)} — corpus now {report['total_chunks']} chunks "
                f"(pages: {report['pages']}), index: {engine}. Ask about it!")]

        if name == "link_code_repo":
            import subprocess
            path = args["path"]
            res = subprocess.run(["gitnexus", "analyze", path],
                                 capture_output=True, text=True, timeout=600, shell=True)
            from . import code_link
            code_link.CODE_REPO = os.path.basename(os.path.normpath(path))
            code_link._cache.clear()
            _export_live_data()
            tail = (res.stdout or res.stderr).strip().splitlines()[-2:]
            return [types.TextContent(type="text", text=
                f"repo indexed as y- plane: {code_link.CODE_REPO}\n" + "\n".join(tail)
                + "\nAsk 'who calls X?' for zero-LLM structural answers.")]

        if name == "rebuild_communities":
            import anthropic
            from sentence_transformers import SentenceTransformer
            from .context_graph import ContextGraph
            from .planes import build_x, build_y_minus
            cg = ContextGraph()
            cg.g.remove_nodes_from([n for n, d in cg.g.nodes(data=True)
                                    if d.get("plane") == "x_community"])
            client = anthropic.Anthropic(base_url=config.LLM_BASE_URL,
                                         api_key=config.LLM_API_KEY)
            embed = SentenceTransformer(config.EMBED_MODEL)
            rx = build_x(cg, client, embed)
            ry = build_y_minus(cg)
            _export_live_data()
            return [types.TextContent(type="text", text=
                f"communities rebuilt — x: {rx}, y-: {ry}. Live view updated.")]

        if name == "graph_stats":
            from .context_graph import ContextGraph
            from collections import Counter
            g = ContextGraph().g
            planes = Counter(d.get("plane") for _, d in g.nodes(data=True))
            rels = Counter(e.get("relation") for _, _, e in g.edges(data=True))
            return [types.TextContent(type="text", text=json.dumps(
                {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(),
                 "turns": g.graph.get("n_turns", 0),
                 "planes": dict(planes), "edge_types": dict(rels)}, indent=1))]

        if name == "recall":
            from .recall import recall, format_recall
            return [types.TextContent(type="text",
                    text=format_recall(recall(args["question"])))]

        if name == "live_view_url":
            _export_live_data()
            return [types.TextContent(type="text", text=
                f"http://127.0.0.1:{PORT}/graph3d_live.html — open it and keep it open; "
                f"it polls every 4s and grows as you chat (camera position is preserved).")]

        return [types.TextContent(type="text", text=f"unknown tool: {name}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"error: {type(e).__name__}: {e}")]


async def main():
    _start_live_server()
    _export_live_data()
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
