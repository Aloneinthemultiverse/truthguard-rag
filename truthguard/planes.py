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


def wire_yplus_entities(cg: ContextGraph) -> dict:
    """Load the saved y+ DG state (entities/relations/communities) into the
    context graph so the 3D view and cross-plane recall see individual
    entities, not just community summaries. Replaces prior entity nodes."""
    from decisiongraph.graph import load_graph_state
    G, communities, summaries = load_graph_state(
        save_dir=os.path.join(config.STORAGE_DIR, "yplus"))
    cg.g.remove_nodes_from([n for n, d in cg.g.nodes(data=True)
                            if d.get("plane") in ("entity", "doc_community")])
    for n, d in G.nodes(data=True):
        cg.g.add_node(f"ent:{n}", plane="entity", label=str(n),
                      source=d.get("source", ""))
    rel_edges = 0
    for u, v, e in G.edges(data=True):
        cg.g.add_edge(f"ent:{u}", f"ent:{v}",
                      relation=e.get("relation", "related"))
        rel_edges += 1
    m_edges = 0
    for cid, info in summaries.items():
        cnode = f"y+dcomm:{cid}"
        cg.g.add_node(cnode, plane="doc_community",
                      summary=info["summary"].strip(), label=info["summary"][:60])
        for ent in info["nodes"]:
            if cg.g.has_node(f"ent:{ent}"):
                cg.g.add_edge(f"ent:{ent}", cnode, relation="member_of")
                m_edges += 1
    cg.save()
    return {"entities": G.number_of_nodes(), "relations": rel_edges,
            "communities": len(summaries), "member_edges": m_edges}


def retro_link_spine(cg: ContextGraph, embed_model, min_sim: float = 0.45) -> dict:
    """Wire every spine turn to the entity / doc chunk / code node it talks
    about (grounds -> knowledge, references -> entity, references_symbol ->
    code). Gives imported historical turns the same cross-plane reference
    points that live `ask` turns get from the controller."""
    import numpy as np
    turns = [(n, d) for n, d in cg.g.nodes(data=True) if d.get("plane") == "spine"]
    targets = {
        "references": ("entity", [(n, d) for n, d in cg.g.nodes(data=True)
                                  if d.get("plane") == "entity"]),
        "references_symbol": ("code", [(n, d) for n, d in cg.g.nodes(data=True)
                                       if d.get("plane") in ("code", "code_symbol")]),
    }
    if not turns:
        return {"linked": 0}
    qv = embed_model.encode([d["question"][:300] for _, d in turns],
                            normalize_embeddings=True)
    added = 0
    # grounds: match turn text against the chunk store's REAL chunk vectors
    try:
        from .chunk_store import ChunkStore
        store = ChunkStore()
        if store._vectors is not None:
            sims = np.asarray(qv) @ store._vectors.T
            for i, (tn, _td) in enumerate(turns):
                j = int(np.argmax(sims[i]))
                knode = f"k:{store._ids[j]}"
                if sims[i][j] >= min_sim:
                    if not cg.g.has_node(knode):
                        c = store.by_id[store._ids[j]]
                        cg.g.add_node(knode, plane="knowledge",
                                      source=f"{c['source_file']} p.{c.get('page','?')}")
                    if not cg.g.has_edge(tn, knode):
                        cg.g.add_edge(tn, knode, relation="grounds",
                                      sim=round(float(sims[i][j]), 3))
                        added += 1
    except Exception:
        pass
    for rel, (plane, nodes) in targets.items():
        if not nodes:
            continue
        texts = [(d.get("label") or d.get("summary") or d.get("source") or str(n))[:300]
                 for n, d in nodes]
        tv = embed_model.encode(texts, normalize_embeddings=True)
        sims = np.asarray(qv) @ np.asarray(tv).T          # turns x targets
        for i, (tn, _td) in enumerate(turns):
            j = int(np.argmax(sims[i]))
            if sims[i][j] >= min_sim and not cg.g.has_edge(tn, nodes[j][0]):
                cg.g.add_edge(tn, nodes[j][0], relation=rel,
                              sim=round(float(sims[i][j]), 3))
                added += 1
    cg.save()
    return {"linked": added, "turns": len(turns)}


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


def run_supersede(cg: ContextGraph, embed_model, q_sim: float = 0.80,
                  a_sim_max: float = 0.75) -> dict:
    """DG lifecycle: when a NEWER turn answers the same question differently,
    the older memory is superseded — demoted (confidence 0.3), tagged, and
    wired old <-supersedes- new. Recall then ranks the current answer first
    and marks the stale one instead of serving it as truth."""
    import numpy as np
    import re as _re

    def _nums(text):
        return {n.replace(",", "") for n in _re.findall(r"\d[\d,]*\.?\d*", text or "")}

    turns = [(n, d) for n, d in cg.g.nodes(data=True)
             if d.get("plane") == "spine" and d.get("is_active", True)
             and d.get("status") != "superseded"
             and len(d.get("question", "")) >= 25]      # skip trivial turns
    if len(turns) < 2:
        return {"superseded": 0}
    turns.sort(key=lambda x: int(x[0][1:]))
    qv = embed_model.encode([d["question"][:300] for _, d in turns],
                            normalize_embeddings=True)
    av = embed_model.encode([(d.get("text") or d["question"])[:300]
                             for _, d in turns], normalize_embeddings=True)
    qs = np.asarray(qv) @ np.asarray(qv).T
    as_ = np.asarray(av) @ np.asarray(av).T
    hit = 0
    for i in range(len(turns)):            # older
        for j in range(i + 1, len(turns)):  # newer
            old_nums = _nums(turns[i][1].get("text"))
            new_nums = _nums(turns[j][1].get("text"))
            numeric_change = bool(old_nums and new_nums and old_nums != new_nums)
            if qs[i][j] >= q_sim and (as_[i][j] < a_sim_max or numeric_change):
                old_n, old_d = turns[i]
                new_n, _ = turns[j]
                if old_d.get("status") == "superseded":
                    continue
                old_d["status"] = "superseded"
                old_d["superseded_by"] = new_n
                old_d["confidence"] = min(old_d.get("confidence") or 1.0, 0.3)
                cg.g.add_edge(new_n, old_n, relation="supersedes")
                hit += 1
    cg.save()
    return {"superseded": hit, "turns_checked": len(turns)}


def load_code_plane(cg: ContextGraph, clear: bool = False) -> dict:
    """Pull the ENTIRE code graph of the linked repo from GitNexus into the
    context graph: every Function/Class/Method/File node (involved in chat or
    not) + calls/defines/imports edges. This is the full-codebase digest."""
    from .code_link import _cypher

    def rows(md, ncols):
        out = []
        for r in (md or "").splitlines():
            cells = [c.strip() for c in r.split("|") if c.strip()]
            if len(cells) == ncols and not set(cells[0]) <= set("-") \
               and not cells[0].endswith(".name"):
                out.append(cells)
        return out

    if clear:
        cg.g.remove_nodes_from([n for n, d in cg.g.nodes(data=True)
                                if d.get("plane") in ("code", "code_file")])
    n_nodes = 0
    ids = {}
    for kind in ("Function", "Class", "Method"):
        md = _cypher(f"MATCH (f:{kind}) RETURN f.name, f.filePath")
        for name, fp in rows(md, 2):
            nid = f"code:{name}:{os.path.basename(fp)}"
            ids[name] = nid
            if not cg.g.has_node(nid):
                from .code_link import CODE_REPO
                cg.g.add_node(nid, plane="code", label=f"{name}",
                              source=fp, kind=kind.lower(), repo=CODE_REPO)
                n_nodes += 1
    md = _cypher("MATCH (f:File) RETURN f.name, f.filePath")
    for name, fp in rows(md, 2):
        nid = f"codefile:{fp}"
        ids[name] = nid
        if not cg.g.has_node(nid):
            cg.g.add_node(nid, plane="code_file", label=name, source=fp)
            n_nodes += 1
    n_edges = 0
    md = _cypher("MATCH (a)-[r:CodeRelation]->(b) RETURN a.name, r.type, b.name")
    for a, rel, b in rows(md, 3):
        if a in ids and b in ids and rel in ("CALLS", "DEFINES", "IMPORTS",
                                             "HAS_METHOD"):
            if not cg.g.has_edge(ids[a], ids[b]):
                cg.g.add_edge(ids[a], ids[b], relation=rel.lower())
                n_edges += 1
    cg.save()
    return {"code_nodes": n_nodes, "code_edges": n_edges}


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
