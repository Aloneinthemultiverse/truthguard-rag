"""HEAD-TO-HEAD: TruthGuard vs the actual graphify binary, identical harness.

Fairness (their own rules):
  - Same conversations, same questions, same sample seed.
  - Same reader LLM and same judge LLM for both systems (their designated
    "clean comparison" axis: a shared reader+judge over each system's hits).
  - graphify retrieves with its real pipeline: `update` (deterministic build)
    + `query` (BFS subgraph, 2000-token budget). TruthGuard retrieves its
    top-10 turns (comparable context size).
  - Evidence metric: gold dia_id marker present in the retrieved context.

Run:  python -m eval.head2head [--n 150]
"""
import os
import sys
import json
import random
import subprocess
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from locomo_bench import load_convs, turns_of      # noqa: E402

WORK = os.path.join(HERE, "h2h_work")


def build_conv_md(conv, cdir):
    """One .md per session; every line carries its [dia_id] marker."""
    os.makedirs(cdir, exist_ok=True)
    c = conv["conversation"]
    for k in sorted(c):
        if k.startswith("session") and isinstance(c[k], list):
            date = c.get(k + "_date_time", "")
            lines = [f"# {k} — {date}", ""]
            for t in c[k]:
                txt = t.get("text") or ""
                if t.get("blip_caption"):
                    txt += f" [shared photo: {t['blip_caption']}]"
                lines.append(f"- [{t['dia_id']}] {t['speaker']}: {txt}")
            with open(os.path.join(cdir, f"{k}.md"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))


def graphify_build(cdir):
    gpath = os.path.join(cdir, "graphify-out", "graph.json")
    # keep an existing SEMANTIC graph (built via `extract --backend ...`);
    # only fall back to the deterministic build when nothing richer exists
    if os.path.exists(gpath):
        try:
            g = json.load(open(gpath, encoding="utf-8"))
            if len(g.get("nodes", [])) > 100:
                return gpath
        except Exception:
            pass
    subprocess.run([sys.executable, "-m", "graphify", "update", cdir,
                    "--no-cluster"], capture_output=True, text=True,
                   timeout=600, cwd=cdir)
    return gpath


def graphify_query(question, graph_path, cdir):
    r = subprocess.run([sys.executable, "-m", "graphify", "query", question,
                        "--graph", graph_path, "--budget", "2000"],
                       capture_output=True, text=True, timeout=300, cwd=cdir)
    return (r.stdout or "")[:12000]


def main():
    n_target = 150
    if "--n" in sys.argv:
        n_target = int(sys.argv[sys.argv.index("--n") + 1])
    from sentence_transformers import SentenceTransformer
    from truthguard.llm import LLM
    em = SentenceTransformer("all-MiniLM-L6-v2")
    reader, judge = LLM(), LLM()

    def answer(ctx, q):
        reader.reset_budget()
        return reader.complete(
            f"Context:\n{ctx}\n\nQuestion: {q}\nAnswer concisely from the "
            f"context only.", max_tokens=100)

    def grade(q, gold, ans):
        judge.reset_budget()
        v = judge.complete(
            f"Question: {q}\nGold answer: {gold}\nModel answer: {ans}\n"
            "Grade: reply exactly CORRECT, PARTIAL, or WRONG.",
            max_tokens=10).strip().upper()
        return 1.0 if "CORRECT" in v else (0.5 if "PARTIAL" in v else 0.0)

    rng = random.Random(42)
    convs = load_convs()
    per_conv = max(1, n_target // len(convs))
    res = {"truthguard": {"ev": 0, "qa": []}, "graphify": {"ev": 0, "qa": []}}
    n = 0
    for ci, conv in enumerate(convs):
        cdir = os.path.join(WORK, f"conv{ci}")
        build_conv_md(conv, cdir)
        gpath = graphify_build(cdir)
        has_graph = os.path.exists(gpath)
        print(f"conv{ci}: graphify graph built = {has_graph}", flush=True)

        turns = turns_of(conv)
        texts = [f"[{t['dia_id']}] {t['speaker']} ({t['date']}): {t['text']}"
                 for t in turns]
        vecs = em.encode(texts, normalize_embeddings=True, batch_size=64,
                         show_progress_bar=False)
        qa = [q for q in conv["qa"] if q.get("evidence") and q.get("answer")]
        for q in rng.sample(qa, min(per_conv, len(qa))):
            ev = q["evidence"]
            if isinstance(ev, str):
                try:
                    ev = eval(ev)
                except Exception:
                    ev = [ev]
            # --- TruthGuard retrieval: top-10 turns
            qv = em.encode([q["question"]], normalize_embeddings=True)[0]
            top = np.argsort(np.asarray(vecs) @ qv)[::-1][:10]
            tg_ctx = "\n".join(texts[i] for i in top)
            # --- graphify retrieval: BFS subgraph
            gf_ctx = graphify_query(q["question"], gpath, cdir) if has_graph else ""
            for name, ctx in (("truthguard", tg_ctx), ("graphify", gf_ctx)):
                res[name]["ev"] += any(f"[{e}]" in ctx for e in ev)
                try:
                    res[name]["qa"].append(
                        grade(q["question"], q["answer"], answer(ctx, q["question"])))
                except Exception as e:
                    print(f"  [skip {name}] {e}", flush=True)
            n += 1
            if n % 10 == 0:
                line = f"  {n} done"
                for s in res:
                    qs = res[s]["qa"]
                    line += (f" | {s}: ev {res[s]['ev']/n:.2f}"
                             + (f" qa {sum(qs)/len(qs):.2f}" if qs else ""))
                print(line, flush=True)

    print(f"\n=== HEAD-TO-HEAD (n={n}, same reader+judge for both) ===")
    for s in res:
        qs = res[s]["qa"]
        print(f"{s:11s} evidence-in-context: {res[s]['ev']/n:.3f}   "
              f"QA accuracy: {sum(qs)/len(qs):.3f} (n={len(qs)})" if qs else s)
    json.dump({s: {"evidence": res[s]["ev"] / n,
                   "qa": (sum(res[s]["qa"]) / len(res[s]["qa"])) if res[s]["qa"] else None}
               for s in res},
              open(os.path.join(HERE, "h2h_results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
