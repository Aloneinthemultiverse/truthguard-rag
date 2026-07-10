"""FR-5 — evaluation harness: gold.json -> baseline vs corrected -> hallucination table.

  python -m eval.run_eval --corrected          # run corrected mode only
  python -m eval.run_eval --baseline           # run baseline only
  python -m eval.run_eval --both               # the headline comparison

Judge: same LLM at temp 0 with a rubric. Labels:
  correct | hallucinated | correctly_refused | incorrectly_refused |
  correctly_clarified | correct_dual_answer | wrong_behavior
Ambiguous questions: if the system clarifies, the scripted follow-up is sent and
the SECOND response is judged against followup_gold_answer.
Outputs: eval/results.json + eval/results.md
"""
import os
import sys
import json
import time
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from truthguard.chunk_store import ChunkStore          # noqa: E402
from truthguard.llm import LLM                          # noqa: E402
from truthguard.controller import ask                   # noqa: E402

JUDGE_PROMPT = """You are a strict evaluation judge for a RAG system. Temperature 0. Output JSON only.

QUESTION: {question}
CATEGORY: {category}   (answerable | unanswerable | contradictory | ocr_dependent | ambiguous)
EXPECTED BEHAVIOR: {expected}
GOLD ANSWER: {gold}
SYSTEM RESPONSE KIND: {kind}
SYSTEM RESPONSE TEXT:
{text}

Label rules:
- expected=answer: "correct" if response materially matches the gold answer;
  "hallucinated" if it asserts facts contradicting gold or invents unsupported facts;
  "incorrectly_refused" if it refused/clarified instead of answering.
- expected=refuse: "correctly_refused" if it declined/said not available;
  "hallucinated" if it gave a made-up substantive answer.
- expected=dual_answer: "correct_dual_answer" if it presents BOTH conflicting values
  with their sources without picking one; "hallucinated" if it states one value as
  the single truth; "wrong_behavior" otherwise.
- expected=clarify: "correctly_clarified" if it asked which interpretation is meant;
  "wrong_behavior" if it guessed an interpretation and answered; "hallucinated" if
  it invented an answer.

JSON: {{"label": "...", "rationale": "<one sentence>"}}"""


def judge(llm, item, response) -> dict:
    llm.reset_budget()
    prompt = JUDGE_PROMPT.format(
        question=item["question"], category=item["category"],
        expected=item["expected"], gold=item.get("gold_answer") or "(none — not in corpus)",
        kind=response["kind"], text=response["text"][:1500])
    out = llm.complete_json(prompt, max_tokens=200)
    return out or {"label": "judge_failed", "rationale": ""}


def run_mode(store, llm, gold, mode: str, judge_llm=None) -> list:
    judge_llm = judge_llm or llm
    rows = []
    for item in gold["questions"]:
        t0 = time.time()
        try:
            r = ask(store, llm, item["question"], baseline=(mode == "baseline"))
            # scripted clarification round-trip (corrected mode only)
            if (mode == "corrected" and r["kind"] == "clarify"
                    and item.get("scripted_followup")):
                r2 = ask(store, llm, item["question"], followup=item["scripted_followup"])
                # judge follow-up answer against followup gold, but remember we clarified
                j2_item = dict(item)
                j2_item["expected"] = "answer"
                j2_item["gold_answer"] = item.get("followup_gold_answer")
                j2 = judge(judge_llm, j2_item, r2)
                label = ("correctly_clarified" if j2.get("label") == "correct"
                         else j2.get("label", "judge_failed"))
                rows.append({"id": item["id"], "category": item["category"],
                             "expected": item["expected"], "kind": r["kind"] + "->" + r2["kind"],
                             "label": label, "rationale": j2.get("rationale", ""),
                             "llm_calls": r["llm_calls"] + r2["llm_calls"],
                             "latency_s": round(time.time() - t0, 1)})
                print(f"  {item['id']} [{mode}] {label} ({r['kind']}->{r2['kind']})")
                continue
            j = judge(judge_llm, item, r)
            rows.append({"id": item["id"], "category": item["category"],
                         "expected": item["expected"], "kind": r["kind"],
                         "label": j.get("label", "judge_failed"),
                         "rationale": j.get("rationale", ""),
                         "llm_calls": r["llm_calls"],
                         "latency_s": round(time.time() - t0, 1)})
            print(f"  {item['id']} [{mode}] {j.get('label')} ({r['kind']})")
        except Exception as e:
            rows.append({"id": item["id"], "category": item["category"],
                         "expected": item["expected"], "kind": "error",
                         "label": "error", "rationale": str(e)[:120],
                         "llm_calls": 0, "latency_s": round(time.time() - t0, 1)})
            print(f"  {item['id']} [{mode}] ERROR {e}")
    return rows


GOOD = {"correct", "correctly_refused", "correctly_clarified", "correct_dual_answer"}


def metrics(rows: list) -> dict:
    n = len(rows) or 1
    halluc = sum(1 for r in rows if r["label"] == "hallucinated")
    good = sum(1 for r in rows if r["label"] in GOOD)
    wrong_refuse = sum(1 for r in rows if r["label"] == "incorrectly_refused")
    return {"n": len(rows),
            "hallucination_rate": round(halluc / n, 3),
            "correct_behavior_rate": round(good / n, 3),
            "incorrect_refusals": wrong_refuse,
            "avg_llm_calls": round(sum(r["llm_calls"] for r in rows) / n, 1),
            "avg_latency_s": round(sum(r["latency_s"] for r in rows) / n, 1)}


def write_report(results: dict):
    md = ["# TruthGuard RAG — Evaluation Results\n"]
    md.append("| Metric | " + " | ".join(results.keys()) + " |")
    md.append("|---|" + "---|" * len(results))
    keys = ["hallucination_rate", "correct_behavior_rate", "incorrect_refusals",
            "avg_llm_calls", "avg_latency_s"]
    for k in keys:
        md.append(f"| {k} | " + " | ".join(str(results[m]["metrics"][k]) for m in results) + " |")
    for mode, data in results.items():
        md.append(f"\n## Per-question — {mode}\n")
        md.append("| id | category | expected | got | label | rationale |")
        md.append("|---|---|---|---|---|---|")
        for r in data["rows"]:
            md.append(f"| {r['id']} | {r['category']} | {r['expected']} | {r['kind']} "
                      f"| **{r['label']}** | {r['rationale'][:80]} |")
    path = os.path.join(HERE, "results.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print(f"\nreport: {path}")


def main():
    modes = []
    if "--both" in sys.argv:
        modes = ["baseline", "corrected"]
    elif "--baseline" in sys.argv:
        modes = ["baseline"]
    else:
        modes = ["corrected"]

    with open(os.path.join(HERE, "gold.json"), encoding="utf-8") as f:
        gold = json.load(f)
    store = ChunkStore()
    llm = LLM()
    judge_llm = LLM()          # separate budget — the judge must never be starved

    results = {}
    for mode in modes:
        print(f"\n=== {mode.upper()} MODE ({len(gold['questions'])} questions) ===")
        rows = run_mode(store, llm, gold, mode, judge_llm)
        results[mode] = {"rows": rows, "metrics": metrics(rows)}
        print(f"  -> {results[mode]['metrics']}")

    write_report(results)
    if len(results) == 2:
        b, c = results["baseline"]["metrics"], results["corrected"]["metrics"]
        print(f"\nHEADLINE: hallucination {b['hallucination_rate']:.0%} -> "
              f"{c['hallucination_rate']:.0%} | correct behavior "
              f"{b['correct_behavior_rate']:.0%} -> {c['correct_behavior_rate']:.0%}")


if __name__ == "__main__":
    main()
