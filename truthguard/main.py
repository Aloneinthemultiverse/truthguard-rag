"""TruthGuard CLI.

  python -m truthguard.main ingest [corpus_dir]     # ingest + build index
  python -m truthguard.main ask "question"          # corrected mode (default)
  python -m truthguard.main ask "question" --baseline
  python -m truthguard.main ask "question" --followup "clarification"
  python -m truthguard.main stats
"""
import sys
import json
import warnings

warnings.filterwarnings("ignore")


def _print_response(r: dict):
    print(f"\n[{r['kind'].upper()}]"
          + (f"  confidence={r['confidence']} ({r['band']})" if r.get("confidence") is not None else ""))
    print(r["text"])
    if r.get("citations"):
        print("\nSources: " + " | ".join(r["citations"]))
    for f in r.get("figures") or []:
        print(f"[image reference] {f['figure']} -> {f['image_path']}")
    print("\ntrace: " + " -> ".join(
        s["step"] + (f"({s.get('verdict', s.get('new_query', ''))})"
                     if s.get("verdict") or s.get("new_query") else "")
        for s in r["trace"]))
    print(f"llm_calls: {r['llm_calls']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]

    if cmd == "ingest":
        from .pipeline import ingest_corpus
        from .chunk_store import build_index
        corpus = sys.argv[2] if len(sys.argv) > 2 else None
        chunks, report = ingest_corpus(corpus)
        print(f"ingested: {report['total_chunks']} chunks, pages={report['pages']}, "
              f"tier2={report['tier2_pages']}, deduped={report['deduped']}")
        for s in report["skipped"]:
            print(f"  SKIPPED {s['file']}: {s['reason']}")
        engine = build_index()
        print(f"index: {engine}")
        return

    if cmd == "stats":
        from .chunk_store import ChunkStore
        s = ChunkStore()
        by_type, by_ext = {}, {}
        for c in s.chunks:
            by_type[c["content_type"]] = by_type.get(c["content_type"], 0) + 1
            by_ext[c["extraction"]] = by_ext.get(c["extraction"], 0) + 1
        print(json.dumps({"chunks": len(s.chunks), "by_content_type": by_type,
                          "by_extraction": by_ext,
                          "files": sorted({c['source_file'] for c in s.chunks})}, indent=1))
        return

    if cmd == "ask":
        question = sys.argv[2]
        baseline = "--baseline" in sys.argv
        followup = None
        if "--followup" in sys.argv:
            followup = sys.argv[sys.argv.index("--followup") + 1]
        from .chunk_store import ChunkStore
        from .llm import LLM
        from .controller import ask
        store = ChunkStore()
        llm = LLM()
        r = ask(store, llm, question, baseline=baseline, followup=followup)
        _print_response(r)
        return

    print(f"unknown command: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
