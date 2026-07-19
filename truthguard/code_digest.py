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


def build(repo_roots: list = None) -> dict:
    roots = repo_roots or [ROOT]
    symbols = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                           and d not in (".claude", "worktrees")]
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                if fn.endswith(".py"):
                    symbols.extend(_extract_symbols(fp))
                    symbols.extend(_extract_rationale(fp))
                elif fn.endswith(JS_EXTS) and not fn.endswith((".min.js", ".d.ts")):
                    symbols.extend(_extract_js(fp))
                    symbols.extend(_extract_rationale(fp))
                else:
                    ext = os.path.splitext(fn)[1]
                    if ext in _LANG:
                        symbols.extend(_extract_generic(fp, ext))
                        symbols.extend(_extract_rationale(fp))
    from sentence_transformers import SentenceTransformer
    em = SentenceTransformer(config.EMBED_MODEL)
    # embed name + docstring + body so "what it does" queries match, not just names
    texts = [f"{s['symbol']} {s['doc']} {s['text'][:600]}" for s in symbols]
    vecs = em.encode(texts, normalize_embeddings=True, batch_size=64,
                     show_progress_bar=False)
    os.makedirs(config.STORAGE_DIR, exist_ok=True)
    with open(os.path.join(config.STORAGE_DIR, "code_digest.json"), "w",
              encoding="utf-8") as f:
        json.dump(symbols, f)
    np.save(os.path.join(config.STORAGE_DIR, "code_digest_vecs.npy"),
            np.asarray(vecs, dtype=np.float32))
    return {"symbols": len(symbols), "files": len({s["file"] for s in symbols})}


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
