"""TruthGuard Studio API — FastAPI wrapper over the same functions the MCP
tools call. Zero new logic; the UI and MCP can't drift apart.

Run:  uvicorn truthguard.api:app --port 7788
Docs: http://127.0.0.1:7788/docs
"""
import os
import json
import shutil
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("TG_STORAGE_DIR", os.path.join(_ROOT, "storage", "truthguard"))
os.environ.setdefault("TG_CORPUS_DIR", os.path.join(_ROOT, "corpus"))

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(title="TruthGuard Studio API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

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


def _export():
    try:
        from .full3d import export_full
        export_full()
    except Exception:
        pass


class AskBody(BaseModel):
    question: str
    followup: str | None = None
    baseline: bool = False


@app.post("/ask")
def ask(body: AskBody):
    from .controller import ask as _ask
    try:
        r = _ask(_store(), _llm(), body.question,
                 baseline=body.baseline, followup=body.followup)
    except Exception as e:
        msg = ("LLM provider is rate-limited right now (a benchmark may be "
               "running on the same key). Try again in a minute."
               if "429" in str(e) else f"{type(e).__name__}: {e}")
        return {"kind": "error", "text": msg, "confidence": None,
                "band": None, "citations": [], "trace": [{"step": "llm_unavailable"}]}
    _export()
    return r


class QueryBody(BaseModel):
    question: str


@app.post("/recall")
def recall(body: QueryBody):
    from .recall import recall as _recall
    return _recall(body.question)


@app.post("/get_context")
def get_context(body: QueryBody):
    from .recall import get_context as _gc
    return {"context": _gc(body.question)}


class GraphQueryBody(BaseModel):
    command: str          # context | impact | find | edit_plan | path | report
    name: str = ""
    target: str = ""


@app.post("/graph_query")
def graph_query(body: GraphQueryBody):
    from . import graph_query as gq
    if body.command == "report":
        return gq.report()
    if body.command == "path":
        return gq.path(body.name, body.target)
    fn = {"context": gq.context, "impact": gq.impact,
          "find": gq.find, "edit_plan": gq.edit_plan}.get(body.command)
    return fn(body.name) if fn else {"error": f"unknown command {body.command}"}


@app.post("/ingest/document")
async def ingest_document(file: UploadFile = File(...)):
    os.makedirs(config.CORPUS_DIR, exist_ok=True)
    dst = os.path.join(config.CORPUS_DIR, os.path.basename(file.filename))
    with open(dst, "wb") as f:
        shutil.copyfileobj(file.file, f)
    from .pipeline import ingest_corpus
    from .chunk_store import build_index
    chunks, report = ingest_corpus()
    engine = build_index()
    _state["store"] = None
    _export()
    return {"file": file.filename, "total_chunks": report["total_chunks"],
            "engine": engine}


class PathBody(BaseModel):
    path: str
    chat_path: str | None = None


@app.post("/ingest/project")
def ingest_project(body: PathBody):
    from .ingest_all import ingest_project as _ip
    r = _ip(body.path, body.chat_path)
    _state["store"] = None
    return r


@app.post("/ingest/chat")
def ingest_chat(body: PathBody):
    from .import_chat import import_chat
    return import_chat(body.path)


@app.get("/graph3d")
def graph3d():
    p = os.path.join(ROOT, "graph3d_data.json")
    return FileResponse(p) if os.path.exists(p) else JSONResponse(
        {"nodes": [], "links": []})


@app.get("/stats")
def stats():
    from .context_graph import ContextGraph
    from collections import Counter
    g = ContextGraph().g
    return {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(),
            "turns": g.graph.get("n_turns", 0),
            "planes": dict(Counter(d.get("plane") for _, d in g.nodes(data=True)))}


@app.get("/benchmarks")
def benchmarks():
    out = {}
    ev = os.path.join(ROOT, "eval")
    for name in ("locomo_results", "longmemeval_results", "h2h_results"):
        p = os.path.join(ev, name + ".json")
        if os.path.exists(p):
            out[name] = json.load(open(p, encoding="utf-8"))
    slices = []
    for f in sorted(os.listdir(ev)):
        if f.startswith("longmemeval_slice_"):
            slices.append(json.load(open(os.path.join(ev, f), encoding="utf-8")))
    if slices:
        qn = sum(s["qa_n"] for s in slices)
        out["longmemeval_slices"] = {
            "slices_done": len(slices),
            "recall@10": sum(s["recall@10"] * s["recall_n"] for s in slices)
                         / max(sum(s["recall_n"] for s in slices), 1),
            "qa": (sum(s["qa_sum"] for s in slices) / qn) if qn else None,
            "qa_n": qn}
    return out


@app.get("/")
def studio():
    return FileResponse(os.path.join(ROOT, "studio.html"))


@app.get("/architecture.html")
def architecture():
    return FileResponse(os.path.join(ROOT, "architecture.html"))


@app.get("/about.html")
def about():
    return FileResponse(os.path.join(ROOT, "about.html"))
