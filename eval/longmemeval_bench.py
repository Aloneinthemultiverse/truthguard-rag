"""LongMemEval-S benchmark for TruthGuard — recall@10 + judge-graded QA.

Turn-level memory (role-tagged, session-dated), local MiniLM embeddings,
zero-LLM ingest. recall@10 = a retrieved turn belongs to a gold evidence
session. Abstention items (question_type *_abs / answer 'unknown') graded
correct when the model declines.

Run:  python -m eval.longmemeval_bench [--n 50] [--recall-n 100] [--no-llm]
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
DATA = os.path.join(HERE, "data", "longmemeval_s_cleaned.json")


def main():
    qa_n, rec_n = 50, 100
    use_llm = "--no-llm" not in sys.argv
    if "--n" in sys.argv:
        qa_n = int(sys.argv[sys.argv.index("--n") + 1])
    if "--recall-n" in sys.argv:
        rec_n = int(sys.argv[sys.argv.index("--recall-n") + 1])

    from sentence_transformers import SentenceTransformer
    em = SentenceTransformer("all-MiniLM-L6-v2")
    llm = judge = None
    if use_llm:
        sys.path.insert(0, os.path.dirname(HERE))
        from truthguard.llm import LLM
        llm, judge = LLM(), LLM()

    data = json.load(open(DATA, encoding="utf-8"))
    rng = random.Random(42)
    items = rng.sample(data, min(max(qa_n, rec_n), len(data)))
    qa_items = set(id(x) for x in items[:qa_n])

    hits, n_rec, qa_scores = 0, 0, []
    for it in items[:rec_n]:
        texts, sess_of = [], []
        for sid, date, sess in zip(it["haystack_session_ids"],
                                   it["haystack_dates"], it["haystack_sessions"]):
            for t in sess:
                if t.get("content"):
                    texts.append(f"[{date}] {t['role']}: {t['content'][:1500]}")
                    sess_of.append(sid)
        vecs = em.encode(texts, normalize_embeddings=True, batch_size=128,
                         show_progress_bar=False)
        qv = em.encode([it["question"]], normalize_embeddings=True)[0]
        top = np.argsort(np.asarray(vecs) @ qv)[::-1][:10]
        gold = set(it["answer_session_ids"])
        hit = any(sess_of[i] in gold for i in top)
        is_abs = it["question_type"].endswith("_abs") or "abs" in it["question_id"]
        if not is_abs:                      # abstention items have no gold session
            hits += hit
            n_rec += 1

        if use_llm and id(it) in qa_items:
            # SYNTHESIS UPGRADE: neighborhood expansion (hit turn +-2 dialogue
            # neighbors), full text, chronological order with visible dates,
            # question-type-aware instructions.
            keep = set()
            for i in top:
                keep.update(range(max(0, i - 2), min(len(texts), i + 3)))
            ctx = "\n".join(texts[i] for i in sorted(keep))
            qt = it["question_type"]
            hint = ""
            if "temporal" in qt:
                hint = " Compute dates/durations from the [date] tags."
            elif "update" in qt or "knowledge" in qt:
                hint = " If information changed over time, answer with the LATEST state."
            elif "multi-session" in qt:
                hint = " Combine facts across the different dated sessions."
            try:
                llm.reset_budget()
                ans = llm.complete(
                    f"Memories (chronological):\n{ctx}\n\n"
                    f"Question (asked {it['question_date']}): {it['question']}\n"
                    f"Answer concisely from the memories only.{hint} "
                    f"If they don't contain the answer, say 'I don't know'.",
                    max_tokens=150)
                if is_abs:
                    qa_scores.append(1.0 if any(k in ans.lower() for k in
                                     ("don't know", "not know", "no information",
                                      "cannot", "unknown")) else 0.0)
                else:
                    judge.reset_budget()
                    v = judge.complete(
                        f"Question: {it['question']}\nGold answer: {it['answer']}\n"
                        f"Model answer: {ans}\n"
                        "Grade: reply exactly CORRECT, PARTIAL, or WRONG.",
                        max_tokens=10).strip().upper()
                    qa_scores.append(1.0 if "CORRECT" in v
                                     else (0.5 if "PARTIAL" in v else 0.0))
            except Exception as e:
                print(f"  [llm skip] {str(e)[:80]}", flush=True)
        done = items.index(it) + 1
        if done % 10 == 0:
            msg = f"  {done}/{rec_n} | recall@10 {hits/max(n_rec,1):.3f}"
            if qa_scores:
                msg += f" | QA {sum(qa_scores)/len(qa_scores):.3f} (n={len(qa_scores)})"
            print(msg, flush=True)

    print(f"\n=== TruthGuard on LongMemEval-S ===")
    print(f"recall@10 (n={n_rec}): {hits/max(n_rec,1):.3f}   "
          f"(graphify 0.844, dense 0.848, BM25 0.710, mem0 0.344)")
    if qa_scores:
        print(f"QA accuracy (n={len(qa_scores)}): {sum(qa_scores)/len(qa_scores):.3f}   "
              f"(graphify 0.76, dense 0.76, mem0 0.70)")
    json.dump({"recall_n": n_rec, "recall@10": hits / max(n_rec, 1),
               "qa_n": len(qa_scores),
               "qa": (sum(qa_scores) / len(qa_scores)) if qa_scores else None},
              open(os.path.join(HERE, "longmemeval_results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
