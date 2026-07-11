"""DG's FULL mechanism applied to the chat plane (x) and code plane (y−).

Referring to decisiongraph/* directly:
  graph.py  detect_communities   -> Louvain + small-community folding (VERBATIM)
  graph.py  summarize_communities-> one LLM sentence per community (VERBATIM)
  decisions.py _NODE_DEFAULTS     -> confidence / access_count / decay / is_active
  decisions.py _autolink (gbrain#5)-> shares_community typed edges, zero LLM
  decisions.py compile_topic      -> compiled truth per community + immutable timeline
  decisions.py decay_confidence   -> unaccessed nodes lose confidence, lazy daily

x plane : turns -> similarity edges -> Louvain -> summaries -> compiled truth,
          turns get DG lifecycle attrs, autolinked via shares_community.
y− plane: GitNexus symbols + CALLS edges -> Louvain -> LLM summaries per code
          community (GitNexus gives structure; DG's recipe gives it meaning).

Run:  python -m truthguard.dg_planes
"""
import os
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import numpy as np
import networkx as nx

from . import config
from .context_graph import ContextGraph

# DG's decision-node lifecycle defaults (decisions.py _NODE_DEFAULTS, verbatim keys)
DG_NODE_DEFAULTS = {
    "confidence": 1.0, "access_count": 0, "last_accessed": "",
    "is_active": True, "superseded_by": "", "outcome": "unknown",
}


def _migrate_turns(cg: ContextGraph) -> int:
    """DG's load-time migration shim: backfill lifecycle attrs on spine nodes."""
    n = 0
    for node, d in cg.g.nodes(data=True):
        if d.get("plane") == "spine":
            for k, v in DG_NODE_DEFAULTS.items():
                if k not in d:
                    d[k] = v
                    n += 1
    return n


# ── x plane: DG recipe end-to-end ────────────────────────────────────────────
def build_x_dg(cg: ContextGraph, client, embed_model, sim_edge: float = 0.45) -> dict:
    from decisiongraph.graph import detect_communities, summarize_communities

    turns = [(n, d) for n, d in cg.g.nodes(data=True) if d.get("plane") == "spine"]
    if len(turns) < 3:
        return {"error": "too few turns"}
    _migrate_turns(cg)

    # 1) similarity graph over turn questions (DG's graph substrate)
    vecs = embed_model.encode([d["question"] for _, d in turns],
                              normalize_embeddings=True)
    sims = np.asarray(vecs) @ np.asarray(vecs).T
    G = nx.MultiDiGraph()
    for i, (n1, _) in enumerate(turns):
        G.add_node(n1)
        for j in range(i + 1, len(turns)):
            if sims[i, j] >= sim_edge:
                G.add_edge(n1, turns[j][0], relation="similar")

    # 2) Louvain + folding — decisiongraph.graph.detect_communities VERBATIM
    communities = detect_communities(G, min_size=2)
    # 3) LLM summaries — but summarize node QUESTIONS, so map ids->questions first
    qmap = dict((n, d["question"][:80]) for n, d in turns)
    named = {cid: [qmap[n] for n in nodes] for cid, nodes in communities.items()}
    summaries = summarize_communities(named, client)   # VERBATIM

    # wipe old x communities, write new ones
    cg.g.remove_nodes_from([n for n, d in cg.g.nodes(data=True)
                            if d.get("plane") == "x_community"])
    member_edges = 0
    for cid, nodes in communities.items():
        cnode = f"xcomm:{cid}"
        cg.g.add_node(cnode, plane="x_community", source=f"topic {cid}",
                      summary=summaries[cid]["summary"].strip())
        for n in nodes:
            cg.g.add_edge(n, cnode, relation="member_of")
            member_edges += 1

    # 4) autolink turns sharing a community — decisions._autolink (gbrain #5)
    auto = 0
    for cid, nodes in communities.items():
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                if not cg.g.has_edge(a, b) and not cg.g.has_edge(b, a):
                    cg.g.add_edge(a, b, relation="shares_community",
                                  communities=[cid])
                    auto += 1

    # 5) compiled truth + immutable timeline — decisions.compile_topic recipe
    compiled = 0
    for cid, nodes in communities.items():
        cnode = f"xcomm:{cid}"
        timeline = sorted(nodes, key=lambda x: int(x[1:]))
        evidence = "\n".join(
            f"- [{cg.g.nodes[n].get('kind')}] {cg.g.nodes[n]['question'][:90]}"
            + (f" -> {cg.g.nodes[n].get('text','')[:80]}" if cg.g.nodes[n].get('text') else "")
            for n in timeline[-15:])
        resp = client.messages.create(
            model=config.LLM_MODEL, max_tokens=2000,
            messages=[{"role": "user", "content":
                "You maintain the 'current best understanding' of a conversation topic.\n"
                f"TOPIC: {summaries[cid]['summary']}\n\nTURN EVIDENCE (oldest->newest):\n"
                f"{evidence}\n\nWrite the COMPILED TRUTH: 2-4 sentences on what was "
                "asked/decided on this topic overall. Plain prose, no preamble."}])
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        cg.g.nodes[cnode]["compiled_truth"] = text
        cg.g.nodes[cnode]["timeline"] = timeline
        cg.g.nodes[cnode]["compiled_at"] = datetime.now().isoformat()
        compiled += 1
    cg.save()
    return {"turns": len(turns), "communities": len(communities),
            "member_edges": member_edges, "autolink_edges": auto,
            "compiled_truths": compiled}


# ── y− plane: DG recipe on the GitNexus call graph ──────────────────────────
def build_yminus_dg(cg: ContextGraph, client) -> dict:
    from decisiongraph.graph import detect_communities, summarize_communities
    from .code_link import _cypher

    md = _cypher("MATCH (a)-[r:CodeRelation]->(b) "
                 "WHERE r.type IN ['CALLS','IMPORTS','DEFINES'] "
                 "RETURN a.name, r.type, b.name LIMIT 500")
    G = nx.MultiDiGraph()
    for row in (md or "").splitlines():
        cells = [c.strip() for c in row.split("|") if c.strip()]
        if len(cells) == 3 and cells[0] not in ("a.name",) and not set(cells[0]) <= set("-"):
            G.add_edge(cells[0], cells[2], relation=cells[1].lower())
    if G.number_of_nodes() < 3:
        return {"error": "code graph too small (link a bigger repo)",
                "nodes": G.number_of_nodes()}

    communities = detect_communities(G, min_size=2)          # VERBATIM
    summaries = summarize_communities(communities, client)   # VERBATIM

    cg.g.remove_nodes_from([n for n, d in cg.g.nodes(data=True)
                            if d.get("plane") == "code_community"])
    m = 0
    for cid, nodes in communities.items():
        cnode = f"y-comm:{cid}"
        cg.g.add_node(cnode, plane="code_community", source="code community",
                      summary=summaries[cid]["summary"].strip(),
                      members=nodes[:20])
        for sn, sd in cg.g.nodes(data=True):
            if sd.get("plane") == "code_symbol" and any(x in sn for x in nodes):
                cg.g.add_edge(sn, cnode, relation="member_of")
                m += 1
    cg.save()
    return {"code_nodes": G.number_of_nodes(), "communities": len(communities),
            "member_edges": m}


def main():
    import anthropic
    from sentence_transformers import SentenceTransformer
    client = anthropic.Anthropic(base_url=config.LLM_BASE_URL,
                                 api_key=config.LLM_API_KEY)
    embed = SentenceTransformer(config.EMBED_MODEL)
    cg = ContextGraph()
    print("x  plane (DG full recipe):", build_x_dg(cg, client, embed))
    print("y- plane (DG on GitNexus):", build_yminus_dg(cg, client))
    print("\ncompiled truths per topic:")
    for n, d in cg.g.nodes(data=True):
        if d.get("plane") == "x_community" and d.get("compiled_truth"):
            print(f"\n[{n}] {d['summary'][:60]}")
            print(f"   TRUTH: {d['compiled_truth'][:180]}")


if __name__ == "__main__":
    main()
