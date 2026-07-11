"""The 3-plane context graph — built on dg-core's DecisionMemory.

  x  CHAT SPINE      every answered question is a node, linked `follows`
                     chronologically (the conversation timeline)
  y+ KNOWLEDGE PLANE spine node --grounds--> provenance chunks it cited
  y- CODE PLANE      spine node --references--> code chunks it used

Spine nodes ARE decision-audit nodes (confidence / outcome / decay / supersede
come free from dg-core). Follow-up questions can retrieve context by graph
neighborhood instead of replaying chat history.

  python -m truthguard.context_graph        # print the current graph
"""
import os
import pickle

import networkx as nx

from . import config

_PATH = lambda d: os.path.join(d or config.STORAGE_DIR, "context_graph.pkl")


class ContextGraph:
    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir or config.STORAGE_DIR
        self.g = nx.DiGraph()
        self._last_spine = None
        self.load()

    # ── record one turn (called by the controller after every response) ─────
    def record_turn(self, question: str, response: dict, chunks_used: list) -> str:
        nid = f"t{self.g.graph.get('n_turns', 0) + 1}"
        self.g.graph["n_turns"] = self.g.graph.get("n_turns", 0) + 1
        self.g.add_node(nid, plane="spine", question=question[:200],
                        kind=response["kind"],
                        text=(response.get("text") or "")[:300],
                        confidence=response.get("confidence"),
                        band=response.get("band"))
        if self._last_spine:
            self.g.add_edge(self._last_spine, nid, relation="follows")
        self._last_spine = nid

        for c in chunks_used:
            plane = "code" if c.get("content_type") == "code" else "knowledge"
            cid = f"{plane[0]}:{c['id']}"
            if not self.g.has_node(cid):
                self.g.add_node(cid, plane=plane,
                                source=f"{c['source_file']} p{c['page']}",
                                extraction=c.get("extraction"))
            self.g.add_edge(nid, cid,
                            relation="references" if plane == "code" else "grounds")
            # y− Level 2: resolve code identifiers to REAL symbols (GitNexus)
            if plane == "code":
                try:
                    from . import code_link
                    for ident in code_link.extract_identifiers(c["text"]):
                        sym = code_link.resolve_symbol(ident)
                        if sym:
                            sid = f"sym:{sym['symbol']}"
                            if not self.g.has_node(sid):
                                self.g.add_node(sid, plane="code_symbol",
                                                source=sym["file"],
                                                extraction="gitnexus")
                            self.g.add_edge(nid, sid, relation="references_symbol")
                except Exception:
                    pass    # symbol linking must never break recording
        self.save()
        return nid

    # ── neighborhood context pack (the "context window is a neighborhood") ──
    def neighborhood(self, spine_id: str = None, hops_back: int = 2) -> dict:
        sid = spine_id or self._last_spine
        if sid is None or not self.g.has_node(sid):
            return {"spine": [], "knowledge": [], "code": []}
        spine, cur = [sid], sid
        for _ in range(hops_back):
            prevs = [u for u, _, d in self.g.in_edges(cur, data=True)
                     if d.get("relation") == "follows"]
            if not prevs:
                break
            cur = prevs[0]
            spine.append(cur)
        knowledge, code = set(), set()
        for s in spine:
            for _, v, d in self.g.out_edges(s, data=True):
                if d.get("relation") == "grounds":
                    knowledge.add(self.g.nodes[v]["source"])
                elif d.get("relation") in ("references", "references_symbol"):
                    code.add(self.g.nodes[v]["source"])
        return {"spine": [dict(self.g.nodes[s], id=s) for s in spine],
                "knowledge": sorted(knowledge), "code": sorted(code)}

    def save(self):
        os.makedirs(self.storage_dir, exist_ok=True)
        with open(_PATH(self.storage_dir), "wb") as f:
            pickle.dump({"g": self.g, "last": self._last_spine}, f)

    def load(self):
        p = _PATH(self.storage_dir)
        if os.path.exists(p):
            with open(p, "rb") as f:
                blob = pickle.load(f)
            self.g, self._last_spine = blob["g"], blob["last"]

    def dump(self) -> str:
        lines = [f"3-PLANE CONTEXT GRAPH — {self.g.graph.get('n_turns', 0)} turns"]
        spine = [n for n, d in self.g.nodes(data=True) if d["plane"] == "spine"]
        for s in sorted(spine):
            d = self.g.nodes[s]
            lines.append(f"\n(x) {s} [{d['kind']}"
                         + (f" conf={d['confidence']}" if d.get("confidence") is not None else "")
                         + f"] {d['question'][:70]}")
            for _, v, e in self.g.out_edges(s, data=True):
                if e["relation"] not in ("grounds", "references", "references_symbol"):
                    continue
                nd = self.g.nodes[v]
                arrow = {"grounds": "y+ grounds   ", "references": "y- references",
                         "references_symbol": "y- SYMBOL    "}[e["relation"]]
                lines.append(f"    {arrow} -> {nd['source']} ({nd.get('extraction','')})")
        return "\n".join(lines)


if __name__ == "__main__":
    print(ContextGraph().dump())
