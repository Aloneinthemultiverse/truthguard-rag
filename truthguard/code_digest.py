"""Codebase digest — materialize actual code text for retrieval (y- content).

The context graph's y- plane stores symbols + structure (GitNexus); this module
stores the BODIES: every top-level function/class in the repo, AST-extracted
with its real source text, embedded for semantic search. recall() surfaces
these as code_passages, exactly like doc_passages from the chunk store.

Build:  python -m truthguard.code_digest [repo_root ...]
Files:  storage/truthguard/code_digest.json + code_digest_vecs.npy
"""
import os
import ast
import json
import sys
import warnings

warnings.filterwarnings("ignore")

import numpy as np

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "storage", ".tmp"}


def _extract_symbols(path: str) -> list:
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
    except (SyntaxError, OSError):
        return []
    lines = src.splitlines()
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            end = getattr(node, "end_lineno", node.lineno + 30)
            body = "\n".join(lines[node.lineno - 1:end])
            doc = ast.get_docstring(node) or ""
            out.append({"symbol": node.name,
                        "kind": type(node).__name__.replace("Def", "").lower(),
                        "file": os.path.relpath(path, ROOT).replace("\\", "/"),
                        "lineno": node.lineno,
                        "doc": doc[:200],
                        "text": body[:2500]})
    return out


_JS_DEF = __import__("re").compile(
    r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s+(\w+)|class\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>)",
    __import__("re").M)


def _extract_js(path: str) -> list:
    """Regex-based JS/TS extractor: functions, classes, arrow consts with
    brace-matched bodies (graphify-style multi-language coverage)."""
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    lines = src.splitlines()
    out = []
    for m in _JS_DEF.finditer(src):
        name = m.group(1) or m.group(2) or m.group(3)
        if not name:
            continue
        start = src[:m.start()].count("\n")
        depth, end = 0, start
        for i in range(start, min(start + 120, len(lines))):
            depth += lines[i].count("{") - lines[i].count("}")
            if depth <= 0 and i > start and "{" in "".join(lines[start:i + 1]):
                end = i
                break
        else:
            end = min(start + 40, len(lines) - 1)
        body = "\n".join(lines[start:end + 1])
        out.append({"symbol": name,
                    "kind": "class" if m.group(2) else "function",
                    "file": os.path.relpath(path, ROOT).replace("\\", "/"),
                    "lineno": start + 1, "doc": "", "text": body[:2500]})
    return out


_RATIONALE = __import__("re").compile(
    r"(?:#|//)\s*(NOTE|WHY|TODO|FIXME|HACK)\b:?\s*(.+)")


def _extract_rationale(path: str) -> list:
    """graphify-style rationale nodes: NOTE/WHY/TODO comments become
    first-class retrievable entries linked to their file+line."""
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    out = []
    for i, line in enumerate(src.splitlines(), 1):
        m = _RATIONALE.search(line)
        if m and len(m.group(2).strip()) > 8:
            out.append({"symbol": f"{m.group(1)}@{os.path.basename(path)}:{i}",
                        "kind": "rationale",
                        "file": os.path.relpath(path, ROOT).replace("\\", "/"),
                        "lineno": i, "doc": "",
                        "text": f"{m.group(1)}: {m.group(2).strip()[:300]}"})
    return out


JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs")

# ── universal multi-language extractor (graphify-style coverage, regex-based) ──
import re as _re

# ext -> (function regexes, class regexes, block style)
_LANG = {
    ".java":   ([r"(?:public|private|protected|static|final|\s)+[\w<>\[\],\s]+\s+(\w+)\s*\([^;{]*\)\s*(?:throws [\w,\s]+)?\{"],
                [r"(?:class|interface|enum|record)\s+(\w+)"], "brace"),
    ".kt":     ([r"fun\s+(?:<[^>]+>\s*)?(\w+)\s*\("], [r"(?:class|interface|object|enum class)\s+(\w+)"], "brace"),
    ".swift":  ([r"func\s+(\w+)\s*[(<]"], [r"(?:class|struct|enum|protocol|extension)\s+(\w+)"], "brace"),
    ".go":     ([r"func\s+(?:\([^)]+\)\s*)?(\w+)\s*\("], [r"type\s+(\w+)\s+(?:struct|interface)"], "brace"),
    ".rs":     ([r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)"], [r"(?:pub\s+)?(?:struct|enum|trait|impl)\s+(\w+)"], "brace"),
    ".c":      ([r"^[\w\*\s]+?\b(\w+)\s*\([^;)]*\)\s*\{"], [r"(?:struct|enum|union)\s+(\w+)\s*\{"], "brace"),
    ".h":      ([r"^[\w\*\s]+?\b(\w+)\s*\([^;)]*\)\s*\{"], [r"(?:struct|enum|union|class)\s+(\w+)"], "brace"),
    ".cpp":    ([r"^[\w:\*&<>\s]+?\b([\w:]+)\s*\([^;)]*\)\s*(?:const\s*)?\{"], [r"(?:class|struct|enum)\s+(\w+)"], "brace"),
    ".cs":     ([r"(?:public|private|protected|internal|static|async|override|\s)+[\w<>\[\],\s]+\s+(\w+)\s*\([^;{]*\)\s*\{"],
                [r"(?:class|interface|struct|enum|record)\s+(\w+)"], "brace"),
    ".php":    ([r"function\s+(\w+)\s*\("], [r"(?:class|interface|trait)\s+(\w+)"], "brace"),
    ".scala":  ([r"def\s+(\w+)"], [r"(?:class|object|trait|case class)\s+(\w+)"], "brace"),
    ".groovy": ([r"def\s+(\w+)\s*\(", r"(?:void|String|int|boolean)\s+(\w+)\s*\("], [r"class\s+(\w+)"], "brace"),
    ".dart":   ([r"[\w<>\[\]?]+\s+(\w+)\s*\([^;{]*\)\s*(?:async\s*)?\{"], [r"(?:class|mixin|enum)\s+(\w+)"], "brace"),
    ".rb":     ([r"def\s+(?:self\.)?(\w+[?!]?)"], [r"(?:class|module)\s+(\w+)"], "end"),
    ".lua":    ([r"(?:local\s+)?function\s+([\w.:]+)"], [], "end"),
    ".ex":     ([r"defp?\s+(\w+[?!]?)"], [r"defmodule\s+([\w.]+)"], "end"),
    ".exs":    ([r"defp?\s+(\w+[?!]?)"], [r"defmodule\s+([\w.]+)"], "end"),
    ".pl":     ([r"sub\s+(\w+)"], [], "brace"),
    ".r":      ([r"(\w[\w.]*)\s*(?:<-|=)\s*function\s*\("], [], "brace"),
    ".R":      ([r"(\w[\w.]*)\s*(?:<-|=)\s*function\s*\("], [], "brace"),
    ".sh":     ([r"(?:function\s+)?(\w+)\s*\(\)\s*\{"], [], "brace"),
    ".vue":    ([r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()"], [], "brace"),
    ".svelte": ([r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()"], [], "brace"),
}


def _extract_generic(path: str, ext: str) -> list:
    fn_pats, cls_pats, style = _LANG[ext]
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    lines = src.splitlines()
    out, seen = [], set()
    for pat, kind in [(p, "function") for p in fn_pats] + \
                     [(p, "class") for p in cls_pats]:
        for m in _re.finditer(pat, src, _re.M):
            name = next((x for x in m.groups() if x), None)
            if not name or name in ("if", "for", "while", "switch", "return",
                                    "catch", "new", "else") or (name, kind) in seen:
                continue
            seen.add((name, kind))
            start = src[:m.start()].count("\n")
            if style == "end":
                end = start
                for i in range(start + 1, min(start + 100, len(lines))):
                    if _re.match(r"\s*end\b", lines[i]):
                        end = i
                        break
                else:
                    end = min(start + 30, len(lines) - 1)
            else:
                depth, end = 0, start
                for i in range(start, min(start + 120, len(lines))):
                    depth += lines[i].count("{") - lines[i].count("}")
                    if depth <= 0 and i > start and "{" in "".join(lines[start:i + 1]):
                        end = i
                        break
                else:
                    end = min(start + 40, len(lines) - 1)
            out.append({"symbol": name, "kind": kind,
                        "file": os.path.relpath(path, ROOT).replace("\\", "/"),
                        "lineno": start + 1, "doc": "",
                        "text": "\n".join(lines[start:end + 1])[:2500]})
    return out


def _file_hash(path: str) -> str:
    """Content hash — the stale check. A file whose hash is unchanged since the
    last build has not been touched, so its symbols and (expensive) embeddings
    are reused verbatim instead of being recomputed."""
    import hashlib
    try:
        with open(path, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()
    except OSError:
        return ""


def _extract_file(fp: str, fn: str) -> list:
    """All symbols for one file, tagged with its content hash so staleness can be
    judged next build. Returns [] for unsupported extensions."""
    syms = []
    if fn.endswith(".py"):
        syms = _extract_symbols(fp) + _extract_rationale(fp)
    elif fn.endswith(JS_EXTS) and not fn.endswith((".min.js", ".d.ts")):
        syms = _extract_js(fp) + _extract_rationale(fp)
    else:
        ext = os.path.splitext(fn)[1]
        if ext in _LANG:
            syms = _extract_generic(fp, ext) + _extract_rationale(fp)
    if syms:
        h = _file_hash(fp)
        for s in syms:
            s["fhash"] = h
    return syms


def _walk_source(roots: list):
    """Yield (full_path, filename) for every source file under the roots."""
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                           and d not in (".claude", "worktrees")]
            for fn in filenames:
                yield os.path.join(dirpath, fn), fn


def build(repo_roots: list = None, incremental: bool = False) -> dict:
    """Build the code digest.

    incremental=True reuses cached symbols and embeddings for files whose
    content hash is unchanged, re-parsing and re-embedding only the files that
    changed, were added, or were deleted. Embedding dominates build cost, so
    skipping unchanged files turns a full rebuild into a per-edit update.
    """
    roots = repo_roots or [ROOT]
    jp = os.path.join(config.STORAGE_DIR, "code_digest.json")
    vp = os.path.join(config.STORAGE_DIR, "code_digest_vecs.npy")

    # Prior state, keyed by file, so an unchanged file's work can be reused.
    old_by_file: dict = {}
    if incremental and os.path.exists(jp) and os.path.exists(vp):
        old_syms = json.load(open(jp, encoding="utf-8"))
        old_vecs = np.load(vp)
        for idx, s in enumerate(old_syms):
            old_by_file.setdefault(s["file"], []).append((s, old_vecs[idx]))

    symbols: list = []
    reuse_vecs: list = []          # aligned 1:1 with the symbols they belong to
    to_embed: list = []            # (position_in_symbols, text) for fresh symbols
    reparsed = reused = 0

    for fp, fn in _walk_source(roots):
        rel = os.path.relpath(fp, ROOT).replace("\\", "/")
        cached = old_by_file.get(rel)
        cur_hash = _file_hash(fp) if cached else None
        # Reuse only when the file was seen before AND its content is identical.
        if cached and cached[0][0].get("fhash") == cur_hash:
            reused += 1
            for s, v in cached:
                symbols.append(s)
                reuse_vecs.append(v)
        else:
            fresh = _extract_file(fp, fn)
            if fresh:
                reparsed += 1
            for s in fresh:
                to_embed.append((len(symbols), f"{s['symbol']} {s['doc']} {s['text'][:600]}"))
                symbols.append(s)
                reuse_vecs.append(None)      # placeholder, filled after embedding

    # Embed only the fresh symbols — the whole point of the incremental path.
    if to_embed:
        from sentence_transformers import SentenceTransformer
        em = SentenceTransformer(config.EMBED_MODEL)
        fresh_vecs = em.encode([t for _, t in to_embed], normalize_embeddings=True,
                               batch_size=64, show_progress_bar=False)
        for (pos, _), v in zip(to_embed, fresh_vecs):
            reuse_vecs[pos] = np.asarray(v, dtype=np.float32)

    vecs = np.asarray(reuse_vecs, dtype=np.float32) if reuse_vecs \
        else np.zeros((0, 384), dtype=np.float32)

    os.makedirs(config.STORAGE_DIR, exist_ok=True)
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(symbols, f)
    np.save(vp, vecs)

    global _CACHE
    _CACHE = None                  # force search() to reload the new digest

    dropped = len([k for k in old_by_file if k not in
                   {os.path.relpath(fp, ROOT).replace("\\", "/") for fp, _ in _walk_source(roots)}]) \
        if incremental else 0
    return {"symbols": len(symbols), "files": len({s["file"] for s in symbols}),
            "reparsed_files": reparsed, "reused_files": reused,
            "embedded_symbols": len(to_embed), "dropped_files": dropped,
            "incremental": incremental}


_CACHE = None


def search(qvec, k: int = 4, min_sim: float = 0.30) -> list:
    """Return actual code bodies matching an (already-normalized) query vector."""
    global _CACHE
    jp = os.path.join(config.STORAGE_DIR, "code_digest.json")
    vp = os.path.join(config.STORAGE_DIR, "code_digest_vecs.npy")
    if not (os.path.exists(jp) and os.path.exists(vp)):
        return []
    if _CACHE is None:
        _CACHE = (json.load(open(jp, encoding="utf-8")), np.load(vp))
    symbols, vecs = _CACHE
    sims = vecs @ qvec
    hits, seen = [], set()
    for i in np.argsort(sims)[::-1]:
        if sims[i] < min_sim or len(hits) >= k:
            break
        s = symbols[int(i)]
        key = (s["symbol"], s["file"])
        if key in seen:
            continue
        seen.add(key)
        hits.append({**s, "similarity": round(float(sims[i]), 3)})
    return hits


if __name__ == "__main__":
    roots = sys.argv[1:] or None
    print(build(roots))
