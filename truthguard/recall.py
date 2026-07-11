"""x-plane recall — DG's DecisionMemory.query recipe applied to the chat spine.

Embed the question -> cosine against every spine turn's question (and every
topic-community summary) -> top matches -> neighborhood walk (the chunks/code
each matched turn grounded on). This is how a NEW chat retrieves context from
OLD chats: O(neighborhood), not O(history).

Run:  python -m truthguard.recall "what did we decide about the travel limit?"
"""
import sys
import warnings

warnings.filterwarnings("ignore")

import numpy as np

from . import config
from .context_graph import ContextGraph

_EMBED = None


def _embedder():
    global _EMBED
    if _EMBED is None:
        from sentence_transformers import SentenceTransformer
        _EMBED = SentenceTransformer(config.EMBED_MODEL)
    return _EMBED


def recall(question: str, top_k: int = 3, storage_dir: str = None) -> dict:
    """DG recipe: similarity over past turns + communities, then neighborhood."""
    cg = ContextGraph(storage_dir)
    g = cg.g
    turns = [(n, d) for n, d in g.nodes(data=True) if d.get("plane") == "spine"]
    comms = [(n, d) for n, d in g.nodes(data=True) if d.get("plane") == "x_community"]
    if not turns:
        return {"matches": [], "communities": [], "note": "spine is empty"}

    em = _embedder()
    q = em.encode([question], normalize_embeddings=True)[0]

    # 1) beam over topic-community summaries (DG's community layer)
    comm_hits = []
    if comms:
        cvecs = em.encode([d.get("summary", "") or d.get("source", "")
                           for _, d in comms], normalize_embeddings=True)
        sims = np.asarray(cvecs) @ q
        for i in np.argsort(sims)[::-1][:2]:
            n, d = comms[i]
            comm_hits.append({"community": n, "summary": d.get("summary", ""),
                              "similarity": round(float(sims[i]), 3),
                              "n_turns": g.in_degree(n)})

    # 2) DG DecisionMemory.query, complete: lazy decay -> active only ->
    #    score = sim x confidence -> access bookkeeping on retrieval
    from datetime import datetime, timedelta
    today = datetime.now().date().isoformat()
    if g.graph.get("last_decay_run") != today:            # decay_confidence, lazy 1x/day
        cutoff = datetime.now() - timedelta(days=90)
        for n, d in turns:
            ref = d.get("last_accessed") or ""
            try:
                last = datetime.fromisoformat(ref) if ref else datetime.now()
            except ValueError:
                last = datetime.now()
            if last < cutoff and d.get("is_active", True):
                d["confidence"] = max(0.0, round(d.get("confidence", 1.0) - 0.1, 3))
                if d["confidence"] < 0.2:
                    d["is_active"] = False
        g.graph["last_decay_run"] = today

    active = [(n, d) for n, d in turns if d.get("is_active", True)]
    tvecs = em.encode([d["question"] for _, d in active], normalize_embeddings=True)
    sims = np.asarray(tvecs) @ q
    scored = sorted(
        ((float(sims[i]) * float(active[i][1].get("confidence", 1.0)), float(sims[i]), i)
         for i in range(len(active))), reverse=True)
    matches = []
    for score, sim, i in scored[:top_k]:
        if sim < 0.35:                 # DG's DECISION_SIMILARITY_THRESHOLD spirit
            continue
        n, d = active[i]
        d["access_count"] = d.get("access_count", 0) + 1   # access_decision()
        d["last_accessed"] = datetime.now().isoformat()
        nb = cg.neighborhood(spine_id=n, hops_back=1)
        matches.append({
            "turn": n,
            "similarity": round(sim, 3),
            "score": round(score, 3),
            "confidence": d.get("confidence", 1.0),
            "access_count": d["access_count"],
            "question": d["question"],
            "kind": d.get("kind"),
            "answer_preview": (d.get("text") or "")[:200],
            "grounded_on": nb["knowledge"][:5],
            "code_touched": nb["code"][:5],
        })
    cg.save()
    return {"matches": matches, "communities": comm_hits}


def format_recall(r: dict) -> str:
    if not r["matches"] and not r["communities"]:
        return "No relevant past turns found."
    out = []
    for c in r["communities"]:
        out.append(f"[topic sim={c['similarity']}] {c['summary'][:80]} ({c['n_turns']} turns)")
    for m in r["matches"]:
        out.append(f"\n[{m['turn']} sim={m['similarity']} {m['kind']}] Q: {m['question'][:90]}")
        if m["answer_preview"]:
            out.append(f"  A: {m['answer_preview'][:140]}")
        if m["grounded_on"]:
            out.append(f"  grounded on: {', '.join(m['grounded_on'])}")
        if m["code_touched"]:
            out.append(f"  code: {', '.join(m['code_touched'])}")
    return "\n".join(out)


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "what did we decide about the travel limit?"
    print(format_recall(recall(q)))
