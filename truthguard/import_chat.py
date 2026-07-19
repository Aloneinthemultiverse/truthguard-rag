"""Import a Claude Code session transcript (JSONL) into the 3-plane graph.

Each user message becomes a spine turn (kind="chat"), chained with `follows`.
Assistant reply preview stored on the node. Zero LLM.

Run:  python -m truthguard.import_chat [path-to-session.jsonl]
      (default: largest .jsonl in the project's Claude session folder)
"""
import os
import sys
import json
import glob
import warnings

warnings.filterwarnings("ignore")

from .context_graph import ContextGraph

SESS_DIR = os.path.expanduser(
    "~/.claude/projects/C--Users-Sujit-Narrayan-M-Downloads-decisiongraph")


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text")
    return ""


def parse_session(path: str, max_turns: int = 300) -> list:
    """Yield (user_text, assistant_preview) pairs from a session JSONL."""
    pairs, pending_user = [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = rec.get("type")
            msg = rec.get("message") or {}
            if t == "user" and not rec.get("isMeta"):
                txt = _text_of(msg.get("content")).strip()
                # skip tool results / system-ish payloads
                if txt and not txt.startswith("<") and len(txt) > 2:
                    pending_user = txt
            elif t == "assistant" and pending_user:
                txt = _text_of(msg.get("content")).strip()
                if txt:
                    pairs.append((pending_user, txt))
                    pending_user = None
            if len(pairs) >= max_turns:
                break
    return pairs


def parse_plain(path: str, max_turns: int = 300) -> list:
    """Parse a generic transcript: lines starting with 'user:'/'assistant:'
    (any case; also 'human:'/'ai:'). Multi-line messages supported."""
    pairs, role, buf, pending_user = [], None, [], None
    aliases = {"user": "user", "human": "user",
               "assistant": "assistant", "ai": "assistant", "bot": "assistant"}

    def flush():
        nonlocal pending_user
        text = "\n".join(buf).strip()
        if not text or role is None:
            return
        if role == "user":
            pending_user = text
        elif pending_user:
            pairs.append((pending_user, text))
            pending_user = None

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            head = line.split(":", 1)[0].strip().lower()
            if head in aliases and ":" in line:
                flush()
                role, buf = aliases[head], [line.split(":", 1)[1]]
            else:
                buf.append(line.rstrip("\n"))
            if len(pairs) >= max_turns:
                break
    flush()
    return pairs


def import_chat(path: str = None) -> dict:
    if path is None:
        cands = sorted(glob.glob(os.path.join(SESS_DIR, "*.jsonl")),
                       key=os.path.getsize, reverse=True)
        if not cands:
            return {"error": f"no session jsonl found in {SESS_DIR}"}
        path = cands[0]
    pairs = parse_session(path) if path.endswith(".jsonl") else parse_plain(path)
    cg = ContextGraph()
    cg._last_spine = None            # NEW CHAIN: don't append to another session
    session = os.path.splitext(os.path.basename(path))[0]
    added = 0
    for user_text, assistant_text in pairs:
        resp = {"kind": "chat", "text": assistant_text[:300],
                "confidence": None, "band": None}
        cg.record_turn(user_text[:200], resp, [], session=session)
        added += 1
    # cross-wire the new turns to entities / doc chunks / code (reference points)
    linked = {}
    try:
        from sentence_transformers import SentenceTransformer
        from . import config
        from .planes import retro_link_spine
        em = SentenceTransformer(config.EMBED_MODEL)
        linked = retro_link_spine(cg, em)
        from .planes import run_supersede
        linked["supersede"] = run_supersede(cg, em)
    except Exception as e:
        linked = {"error": str(e)}
    # refresh live view data if the exporter is available
    try:
        from .mcp_server import _export_live_data
        _export_live_data()
    except Exception:
        pass
    return {"session": os.path.basename(path), "pairs_found": len(pairs),
            "turns_added": added, "total_turns": cg.g.graph.get("n_turns", 0),
            "cross_links": linked}


if __name__ == "__main__":
    print(import_chat(sys.argv[1] if len(sys.argv) > 1 else None))
