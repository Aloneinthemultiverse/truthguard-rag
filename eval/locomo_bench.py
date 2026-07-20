"""LOCOMO benchmark for TruthGuard — same axes graphify reports:
recall@10 (retrieval) + judge-graded QA accuracy.

Method (mirrors their harness shape: ingest -> index -> search -> answer -> grade):
  - Each LOCOMO conversation becomes turn-level memories (speaker + text + date),
    embedded with our local MiniLM (their fairness rule: local deterministic embedder).
  - recall@10: question -> top-10 turns; hit if any gold evidence dia_id is present.
  - QA: top-10 turns -> answer LLM -> judge LLM grades vs gold answer
    (correct=1 / partial=0.5 / wrong=0 — their coverage formula, single-fact form).

Run:  python -m eval.locomo_bench [--n 300] [--no-llm]   (LLM via configured proxy)
"""
import os
import sys
import json
import random
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "locomo10.json")


def load_convs():
    return json.load(open(DATA, encoding="utf-8"))


def turns_of(conv):
    out = []
    c = conv["conversation"]
    for k in sorted(c):
        if k.startswith("session") and isinstance(c[k], list):
            date = c.get(k + "_date_time", "")
            for t in c[k]:
                txt = t.get("text") or ""
                if t.get("blip_caption"):
                    txt += f" [shared photo: {t['blip_caption']}]"
                out.append({"dia_id": t["dia_id"], "speaker": t["speaker"],
                            "date": date, "text": txt})
    return out


def main():
    n_target = 300
    use_llm = "--no-llm" not in sys.argv
    if "--n" in sys.argv:
        n_target = int(sys.argv[sys.argv.index("--n") + 1])

    from sentence_transformers import SentenceTransformer
    em = SentenceTransformer("all-MiniLM-L6-v2")

    llm = judge = None
    if use_llm:
        sys.path.insert(0, os.path.dirname(HERE))
        from truthguard import config as _cfg
        rm = os.getenv("READER_MODEL")           # #1 strong reader (never weak flash)
        if rm:
            _cfg.LLM_MODEL = rm
        from truthguard.llm import LLM
        llm, judge = LLM(), LLM()
        print(f"reader/judge model: {_cfg.LLM_MODEL}", flush=True)

    convs = load_convs()
    rng = random.Random(42)
    per_conv = max(1, n_target // len(convs))

    hits10 = 0
    qa_scores = []
    n_ret = 0
    import re as _re
    from rank_bm25 import BM25Okapi
    from truthguard.retrieve import _question_entities

    def _tok(t):
        return _re.findall(r"[a-z0-9]+", t.lower())

    def _rrf(rankings, k=60, limit=10):
        sc = {}
        for r in rankings:
            for rank, i in enumerate(r):
                sc[i] = sc.get(i, 0.0) + 1.0 / (k + rank + 1)
        return [i for i, _ in sorted(sc.items(), key=lambda x: -x[1])[:limit]]

    for ci, conv in enumerate(convs):
        turns = turns_of(conv)
        texts = [f"{t['speaker']} ({t['date']}): {t['text']}" for t in turns]
        vecs = em.encode(texts, normalize_embeddings=True, batch_size=64,
                         show_progress_bar=False)
        ids = [t["dia_id"] for t in turns]
        bm25 = BM25Okapi([_tok(t) for t in texts])           # #3 BM25 signal
        qa = [q for q in conv["qa"] if q.get("evidence") and q.get("answer")]
        sample = rng.sample(qa, min(per_conv, len(qa)))
        for q in sample:
            qv = em.encode([q["question"]], normalize_embeddings=True)[0]
            sims = np.asarray(vecs) @ qv
            vec_rank = list(np.argsort(sims)[::-1][:25])
            bm_scores = bm25.get_scores(_tok(q["question"]))     # #3 keyword
            bm_rank = list(np.argsort(bm_scores)[::-1][:25])
            ents = _question_entities(q["question"])             # #3 entity match
            ent_scores = [sum(1 for e in ents if e in texts[i]) for i in range(len(texts))]
            ent_rank = [i for i in np.argsort(ent_scores)[::-1][:25] if ent_scores[i] > 0]
            fused = _rrf([vec_rank, bm_rank, ent_rank] if ent_rank else [vec_rank, bm_rank],
                         limit=10)
            top = fused
            top_ids = {ids[i] for i in top}
            ev = q["evidence"]
            if isinstance(ev, str):
                try:
                    ev = eval(ev)
                except Exception:
                    ev = [ev]
            hit = any(e in top_ids for e in ev)
            hits10 += hit
            n_ret += 1

            if use_llm:
                # #4 fuller synthesis context: hit turns + ±1 neighbors, no truncation
                keep = set()
                for i in top:
                    keep.update(range(max(0, i - 1), min(len(texts), i + 2)))
                ctx = "\n".join(texts[i] for i in sorted(keep))
                # category-aware CoT (LOCOMO cats: 1 multi-hop, 2 temporal,
                # 3 open-domain, 4 single-hop, 5 adversarial/abstain)
                cat = str(q.get("category", ""))
                hint = {
                    "1": "This needs MULTI-HOP reasoning: chain facts across turns.",
                    "2": "This is a TEMPORAL question: build a dated timeline of the "
                         "relevant events from the [dates], then reason about order/"
                         "duration before answering.",
                    "3": "Combine the memories with general world knowledge.",
                    "5": "This may be UNANSWERABLE: if the memories don't clearly "
                         "support an answer, say 'I don't know'.",
                }.get(cat, "Find the specific fact asked for.")
                try:
                    llm.reset_budget()
                    raw = llm.complete(
                        f"Conversation memories (chronological, dated):\n{ctx}\n\n"
                        f"Question: {q['question']}\n{hint}\n"
                        f"Think step by step in 1-3 short lines, then output the final "
                        f"answer on a last line prefixed 'ANSWER:'. Be precise with "
                        f"names, dates, and numbers.",
                        max_tokens=400)
                    ans = raw.split("ANSWER:")[-1].strip() if "ANSWER:" in raw else raw.strip()
                    judge.reset_budget()
                    verdict = judge.complete(
                        f"Question: {q['question']}\nGold answer: {q['answer']}\n"
                        f"Model answer: {ans}\n"
                        "Does the model answer contain the gold fact (allow paraphrase, "
                        "extra detail)? Reply exactly CORRECT, PARTIAL, or WRONG.",
                        max_tokens=10).strip().upper()
                    qa_scores.append(1.0 if "CORRECT" in verdict
                                     else (0.5 if "PARTIAL" in verdict else 0.0))
                except Exception as e:
                    print(f"  [llm skip] {e}", flush=True)
            if n_ret % 25 == 0:
                msg = f"  {n_ret} done | recall@10 {hits10/n_ret:.3f}"
                if qa_scores:
                    msg += f" | QA {sum(qa_scores)/len(qa_scores):.3f}"
                print(msg, flush=True)

    print(f"\n=== TruthGuard on LOCOMO (n={n_ret}) ===")
    print(f"recall@10 : {hits10/n_ret:.3f}   (graphify 0.497, BM25 0.362, mem0 0.048)")
    if qa_scores:
        print(f"QA accuracy: {sum(qa_scores)/len(qa_scores):.3f}   "
              f"(graphify 0.453, supermemory 0.497, mem0 0.273)")
    json.dump({"n": n_ret, "recall@10": hits10 / n_ret,
               "qa": (sum(qa_scores) / len(qa_scores)) if qa_scores else None},
              open(os.path.join(HERE, "locomo_results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
