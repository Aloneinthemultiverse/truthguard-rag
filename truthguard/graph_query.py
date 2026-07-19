"""Structural queries on OUR 3-plane context graph (not GitNexus's index).

Everything traverses storage/truthguard/context_graph.pkl — the same graph the
3D view shows. Because all planes live in one graph, context/impact cross
planes: a function's impact includes the chat turns and doc entities wired to
it, not just other code.

  context(name)  -> the node + every in/out edge grouped by relation, per plane
  impact(name)   -> BFS blast radius across planes (code + docs + chat)
  find(text)     -> locate nodes by name/label on any plane
"""
import os
import json
import warnings

warnings.filterwarnings("ignore")

from . import config
from .context_graph import ContextGraph


def _label(g, n):
    d = g.nodes[n]
    return (d.get("label") or d.get("question") or d.get("summary")
            or d.get("source") or str(n))


def find(text: str, limit: int = 10) -> list:
    """Locate nodes on any plane by exact then substring label match."""
    g = ContextGraph().g
    t = text.strip().lower()
    exact, partial = [], []
    for n, d in g.nodes(data=True):
        lab = _label(g, n)
        low = lab.lower()
        item = {"node": n, "plane": d.get("plane", "chat"), "label": lab[:90]}
        if low == t or n.lower().endswith(":" + t) or low.endswith(t):
            exact.append(item)
        elif t in low:
            partial.append(item)
    return (exact + partial)[:limit]


def context(name: str) -> dict:
    """360° view of a node in OUR graph: edges grouped by relation, both
    directions, neighbors labeled with their plane. Code nodes get their
    actual source body from the code digest."""
    g = ContextGraph().g
    hits = find(name, limit=1)
    if not hits:
        return {"status": "not_found", "query": name}
    n = hits[0]["node"]
    d = g.nodes[n]
    out = {"status": "found", "node": n, "plane": d.get("plane"),
           "label": _label(g, n)[:120], "incoming": {}, "outgoing": {}}
    for u, _, e in g.in_edges(n, data=True):
        rel = e.get("relation", "related")
        out["incoming"].setdefault(rel, []).append(
            {"node": u, "plane": g.nodes[u].get("plane"), "label": _label(g, u)[:80]})
    for _, v, e in g.out_edges(n, data=True):
        rel = e.get("relation", "related")
        out["outgoing"].setdefault(rel, []).append(
            {"node": v, "plane": g.nodes[v].get("plane"), "label": _label(g, v)[:80]})
    for rels in (out["incoming"], out["outgoing"]):
        for k in rels:
            rels[k] = rels[k][:10]
    # attach real source if it's a code symbol
    p = os.path.join(config.STORAGE_DIR, "code_digest.json")
    if d.get("plane") in ("code", "code_symbol") and os.path.exists(p):
        base = _label(g, n).split("(")[0].strip()
        for s in json.load(open(p, encoding="utf-8")):
            if s["symbol"] == base:
                out["definition"] = {"file": s["file"], "lineno": s["lineno"],
                                     "text": s["text"][:1200]}
                break
    return out


_IMPACT_RELS = {"calls", "imports", "defines", "has_method", "references",
                "references_symbol", "grounds", "edited", "member_of"}


def impact(name: str, depth: int = 2) -> dict:
    """Cross-plane blast radius: BFS over dependency edges in BOTH directions.
    Shows which code, doc entities, and chat turns are wired to this node."""
    g = ContextGraph().g
    hits = find(name, limit=1)
    if not hits:
        return {"status": "not_found", "query": name}
    start = hits[0]["node"]
    seen, frontier = {start}, [start]
    layers = []
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for u, _, e in g.in_edges(n, data=True):
                if e.get("relation") in _IMPACT_RELS and u not in seen:
                    seen.add(u); nxt.append(u)
            for _, v, e in g.out_edges(n, data=True):
                if e.get("relation") in _IMPACT_RELS and v not in seen:
                    seen.add(v); nxt.append(v)
        layers.append(nxt)
        frontier = nxt
    by_plane = {}
    for n in seen - {start}:
        p = g.nodes[n].get("plane", "chat")
        by_plane.setdefault(p, []).append(_label(g, n)[:70])
    return {"status": "found", "node": start, "impacted": len(seen) - 1,
            "risk": "HIGH" if len(seen) > 40 else ("MEDIUM" if len(seen) > 12 else "LOW"),
            "by_plane": {k: {"count": len(v), "examples": v[:8]}
                         for k, v in sorted(by_plane.items())}}


_INFERRED_RELS = {"shares_community", "supersedes", "references", "references_symbol"}


def _prov(e: dict) -> str:
    return e.get("provenance") or (
        "INFERRED" if ("sim" in e or e.get("relation") in _INFERRED_RELS)
        else "EXTRACTED")


def path(a: str, b: str, max_hops: int = 12) -> dict:
    """Shortest path between ANY two concepts across all planes — each hop
    labeled with its relation and provenance (EXTRACTED vs INFERRED)."""
    import networkx as nx
    g = ContextGraph().g
    ha, hb = find(a, limit=1), find(b, limit=1)
    if not ha or not hb:
        return {"status": "not_found", "missing": a if not ha else b}
    na, nb = ha[0]["node"], hb[0]["node"]
    try:
        p = nx.shortest_path(g.to_undirected(as_view=True), na, nb)
    except nx.NetworkXNoPath:
        return {"status": "no_path", "from": na, "to": nb}
    if len(p) - 1 > max_hops:
        return {"status": "too_far", "hops": len(p) - 1}
    hops = []
    for u, v in zip(p, p[1:]):
        e = g.get_edge_data(u, v) or g.get_edge_data(v, u) or {}
        hops.append({"from": _label(g, u)[:60], "to": _label(g, v)[:60],
                     "from_plane": g.nodes[u].get("plane"),
                     "to_plane": g.nodes[v].get("plane"),
                     "relation": e.get("relation", "?"),
                     "provenance": _prov(e)})
    return {"status": "found", "hops": len(hops), "path": hops}


def report() -> dict:
    """GRAPH_REPORT: god nodes per plane, surprising cross-plane links,
    suggested questions — the graphify-style highlights of OUR graph."""
    g = ContextGraph().g
    deg = dict(g.degree())
    by_plane = {}
    for n, d in g.nodes(data=True):
        by_plane.setdefault(d.get("plane", "chat"), []).append(n)
    god = {}
    for p, ns in by_plane.items():
        top = sorted(ns, key=lambda n: -deg.get(n, 0))[:5]
        god[p] = [{"label": _label(g, n)[:60], "degree": deg.get(n, 0)}
                  for n in top if deg.get(n, 0) > 2]
    # surprises: strong INFERRED links that cross planes
    surprises = []
    for u, v, e in g.edges(data=True):
        pu, pv = g.nodes[u].get("plane"), g.nodes[v].get("plane")
        if pu != pv and e.get("sim", 0) >= 0.6 and _prov(e) == "INFERRED":
            surprises.append({"from": f"[{pu}] {_label(g, u)[:50]}",
                              "to": f"[{pv}] {_label(g, v)[:50]}",
                              "relation": e.get("relation"), "sim": e.get("sim")})
    surprises.sort(key=lambda s: -s["sim"])
    questions = []
    for p, tops in god.items():
        if tops:
            questions.append(f"What is '{tops[0]['label']}' and what depends on it?")
    rep = {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(),
           "god_nodes": god, "surprising_links": surprises[:10],
           "suggested_questions": questions[:6]}
    # also render a markdown report file
    try:
        lines = [f"# Graph Report — {rep['nodes']} nodes / {rep['edges']} edges", ""]
        for p, tops in god.items():
            if tops:
                lines.append(f"## God nodes — {p}")
                lines += [f"- **{t['label']}** ({t['degree']} connections)" for t in tops]
        if surprises:
            lines.append("## Surprising connections")
            lines += [f"- {s['from']} ↔ {s['to']} ({s['relation']}, sim {s['sim']})"
                      for s in surprises[:10]]
        lines.append("## Ask the graph")
        lines += [f"- {q}" for q in questions]
        with open(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "GRAPH_REPORT.md"),
                "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError:
        pass
    return rep


def edit_plan(name: str) -> dict:
    """Pre-edit checklist for a symbol: blast radius + exactly what to check
    so original functionality survives the change."""
    c = context(name)
    if c.get("status") != "found":
        return c
    imp = impact(name, depth=2)
    g = ContextGraph().g
    n = c["node"]
    callers = c["incoming"].get("calls", [])
    callees = c["outgoing"].get("calls", [])
    docs, chats = [], []
    for u, _, e in list(g.in_edges(n, data=True)) + list(g.out_edges(n, data=True)):
        other = u if u != n else _
        p = g.nodes[other].get("plane")
        if p in ("entity", "knowledge", "doc_community"):
            docs.append(_label(g, other)[:70])
        elif p == "spine":
            chats.append(_label(g, other)[:70])
    plan = {
        "symbol": c["label"], "node": n,
        "impact_radius": {"total": imp["impacted"], "risk": imp["risk"],
                          "by_plane": imp["by_plane"]},
        "must_not_break": {
            "callers (keep signature/return contract or update these)":
                [f"{x['label']}" for x in callers],
            "callees (behavior you depend on)":
                [f"{x['label']}" for x in callees],
        },
        "also_review": {
            "docs/entities that describe this behavior (update if semantics change)":
                sorted(set(docs))[:8],
            "past chat decisions about it (check you're not reversing one)":
                sorted(set(chats))[:5],
        },
        "definition": c.get("definition"),
        "checklist": [
            "1. Keep the signature and return shape, or update every caller listed",
            "2. Re-read the callees — don't change assumptions about what they return",
            "3. If semantics change, update the listed docs/entities (and re-ingest)",
            "4. Run the eval after: python -m eval.run_eval",
        ],
    }
    return plan


def fmt(r: dict) -> str:
    return json.dumps(r, indent=1, ensure_ascii=False)
