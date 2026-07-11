"""The three planes, each built with DecisionGraph's OWN recipe, then cross-wired.

  y+  dg-core pipeline verbatim: triples -> entity resolution -> Louvain
      communities -> LLM summaries        (decisiongraph/ingest.py + graph.py)
  x   same recipe on conversation turns: embed -> cluster -> summary per
      community (DG compile_topic style)
  y-  GitNexus's own clusters (it already runs community detection on code)

Community nodes land INSIDE the context graph (plane=*_community, member_of
edges), so the cross-plane wires (grounds/references) and the community
structure live in one graph — three DecisionGraphs, connected.

Run:  python -m truthguard.planes
"""
import os
import re
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import json
import numpy as np

from . import config
from .context_graph import ContextGraph

STAT_EDGES = ("same_doc", "co_cited", "shares_ctx")   # the experiment to revert


def revert_statistical_edges(cg: ContextGraph) -> int:
    doomed = [(u, v) for u, v, d in cg.g.edges(data=True)
              if d.get("relation") in STAT_EDGES]
    cg.g.remove_edges_from(doomed)
    cg.save()
    return len(doomed)


def build_y_plus(cg: ContextGraph, client, embed_model) -> dict:
    """DG pipeline verbatim over the corpus prose chunks."""
    from decisiongraph.ingest import extract_triples_safe, build_graph
    from decisiongraph.graph import (entity_resolution, detect_communities,
                                     summarize_communities, save_graph_state)
    with open(os.path.join(config.STORAGE_DIR, "chunks.json"), encoding="utf-8") as f:
        chunks = json.load(f)
    prose = [c for c in chunks if c["content_type"] == "prose"]
    triples = []
    for c in prose:
        triples.extend(extract_triples_safe(c["text"][:1500], client))
    G = build_graph(triples)
    G, _merged = entity_resolution(G, embed_model)
    communities = detect_communities(G, min_size=2)
    summaries = summarize_communities(communities, client)
    save_graph_state(G, communities, summaries,
                     save_dir=os.path.join(config.STORAGE_DIR, "yplus"))

    # wire community nodes into the context graph
    added = 0
    know = [(n, d) for n, d in cg.g.nodes(data=True) if d.get("plane") == "knowledge"]
    for cid, info in summaries.items():
        cnode = f"y+comm:{cid}"
        cg.g.add_node(cnode, plane="y_community", source=f"community {cid}",
                      summary=info["summary"].strip(),
                      entities=info["nodes"][:12])
        ents = [e.lower() for e in info["nodes"]]
        for n, d in know:
            # a chunk belongs to a community if it mentions its entities
            # (cheap membership; the full graph lives in storage/yplus)
            pass
        added += 1
    # membership: match chunk text to community entities
    chunk_text = {f"k:{c['id']}": c["text"].lower() for c in chunks}
    m_edges = 0
    for cid, info in summaries.items():
        cnode = f"y+comm:{cid}"
        ents = [e.lower() for e in info["nodes"] if len(e) > 3]
        for n, _d in know:
            txt = chunk_text.get(n, "")
            if sum(1 for e in ents if e in txt) >= 2 and not cg.g.has_edge(n, cnode):
                cg.g.add_edge(n, cnode, relation="member_of")
                m_edges += 1
    cg.save()
    return {"triples": len(triples), "entities": G.number_of_nodes(),
            "communities": added, "member_edges": m_edges}


def build_x(cg: ContextGraph, client, embed_model) -> dict:
    """DG's decision-community recipe on conversation turns."""
    turns = [(n, d) for n, d in cg.g.nodes(data=True) if d.get("plane") == "spine"]
    if len(turns) < 2:
        return {"communities": 0}
    qs = [d["question"] for _, d in turns]
    vecs = embed_model.encode(qs, normalize_embeddings=True)
    sims = np.asarray(vecs) @ np.asarray(vecs).T
    # union-find threshold clustering (cos >= 0.55)
    parent = list(range(len(turns)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(turns)):
        for j in range(i + 1, len(turns)):
            if sims[i, j] >= 0.55:
                parent[find(i)] = find(j)
    clusters = {}
    for i in range(len(turns)):
        clusters.setdefault(find(i), []).append(i)

    n_comm, m_edges = 0, 0
    for root, idxs in clusters.items():
        if len(idxs) < 2:
            continue
        member_qs = [qs[i] for i in idxs][:8]
        from .llm import LLM
        _l = LLM()   # hardened client: big token floor + truncation retry
        summary = _l.complete(
            "These related questions form one conversation topic:\n- "
            + "\n- ".join(member_qs)
            + "\nWrite ONE sentence (max 15 words) naming the topic.",
            max_tokens=200).strip()
        cnode = f"xcomm:{n_comm}"
        cg.g.add_node(cnode, plane="x_community", source=f"topic {n_comm}",
                      summary=summary, size=len(idxs))
        for i in idxs:
            cg.g.add_edge(turns[i][0], cnode, relation="member_of")
            m_edges += 1
        n_comm += 1
    cg.save()
    return {"communities": n_comm, "member_edges": m_edges}


def build_y_minus(cg: ContextGraph) -> dict:
    """GitNexus's own community detection, imported as code communities."""
    from .code_link import _cypher
    md = _cypher("MATCH (s)-[:CodeRelation {type:'MEMBER_OF'}]->(c:Community) "
                 "RETURN s.name, c.heuristicLabel")
    n_comm, m_edges = 0, 0
    comms = {}
    for row in (md or "").splitlines():
        cells = [c.strip() for c in row.split("|") if c.strip()]
        if len(cells) == 2 and cells[0] not in ("s.name", "---") \
           and not set(cells[0]) <= set("-"):
            comms.setdefault(cells[1], []).append(cells[0])
    for label, members in comms.items():
        cnode = f"y-comm:{label}"
        cg.g.add_node(cnode, plane="code_community", source="gitnexus cluster",
                      summary=label, members=members)
        n_comm += 1
        for n, d in cg.g.nodes(data=True):
            if d.get("plane") == "code_symbol" and any(m in n for m in members):
                cg.g.add_edge(n, cnode, relation="member_of")
                m_edges += 1
    cg.save()
    return {"communities": n_comm, "member_edges": m_edges}


def main():
    import anthropic
    from sentence_transformers import SentenceTransformer
    client = anthropic.Anthropic(base_url=config.LLM_BASE_URL,
                                 api_key=config.LLM_API_KEY)
    embed = SentenceTransformer(config.EMBED_MODEL)
    cg = ContextGraph()

    print("1) reverting statistical autowire edges...")
    print(f"   removed {revert_statistical_edges(cg)} edges "
          f"({', '.join(STAT_EDGES)}); kept calls/quotes (semantic)")

    print("2) y+ — DG pipeline on corpus (triples/entities/communities/summaries)...")
    print("  ", build_y_plus(cg, client, embed))

    print("3) x — DG recipe on conversation turns...")
    print("  ", build_x(cg, client, embed))

    print("4) y- — GitNexus code communities...")
    print("  ", build_y_minus(cg))

    print("5) cross-plane wires untouched (grounds/references/references_symbol).")
    print("\n=== COMMUNITY SUMMARIES IN THE GRAPH ===")
    for n, d in cg.g.nodes(data=True):
        if "community" in str(d.get("plane", "")):
            deg = cg.g.in_degree(n)
            print(f"  [{d['plane']}] {n} ({deg} members): {d.get('summary','')[:80]}")


if __name__ == "__main__":
    main()
