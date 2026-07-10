"""y− code plane, Level 2 — link conversation turns to REAL code symbols via GitNexus.

When an answer uses a code chunk, its identifiers are resolved against the
GitNexus structural graph (tree-sitter index). Hits become `references_symbol`
edges to stable symbol IDs, and follow-ups ("who calls it?") answer from the
code graph — zero retrieval, zero hallucination surface.

Config: TG_CODE_REPO env var names the indexed GitNexus repo (default demo_repo).
Degrades silently if gitnexus CLI or the repo index is missing.
"""
import os
import re
import json
import subprocess

CODE_REPO = os.getenv("TG_CODE_REPO", "demo_repo")
_IDENT_RE = re.compile(r"\bdef\s+(\w+)|\bclass\s+(\w+)|\b(\w+)\s*\(")
_cache = {}


def _cypher(query: str):
    try:
        out = subprocess.run(
            ["gitnexus", "cypher", query, "--repo", CODE_REPO],
            capture_output=True, text=True, timeout=30, shell=True).stdout
        m = re.search(r'\{.*\}', out, re.DOTALL)
        return json.loads(m.group(0))["markdown"] if m else None
    except Exception:
        return None


def extract_identifiers(code_text: str) -> list:
    """Function/class names defined or called in a code block."""
    names = set()
    for m in _IDENT_RE.finditer(code_text):
        name = next(g for g in m.groups() if g)
        if len(name) > 3 and not name.startswith("_"):
            names.add(name)
    return sorted(names)[:8]


def resolve_symbol(identifier: str):
    """identifier -> {'symbol': 'Function:path:name', 'file': path} or None."""
    if identifier in _cache:
        return _cache[identifier]
    md = _cypher(f"MATCH (f:Function {{name:'{identifier}'}}) RETURN f.name, f.filePath")
    result = None
    if md:
        rows = [r for r in md.splitlines() if r.startswith("|") and identifier in r]
        if rows:
            cells = [c.strip() for c in rows[0].split("|") if c.strip()]
            if len(cells) >= 2:
                result = {"symbol": f"Function:{cells[1]}:{cells[0]}", "file": cells[1]}
    _cache[identifier] = result
    return result


def callers_of(identifier: str) -> list:
    """Structural follow-up: who calls this function? (zero LLM)"""
    md = _cypher(f"MATCH (a)-[:CodeRelation {{type:'CALLS'}}]->"
                 f"(f:Function {{name:'{identifier}'}}) RETURN a.name, a.filePath")
    out = []
    for r in (md or "").splitlines():
        cells = [c.strip() for c in r.split("|") if c.strip()]
        if len(cells) == 2 and cells[0] not in ("a.name", "---"):
            out.append({"name": cells[0], "file": cells[1]})
    return [c for c in out if not set(c["name"]) <= set("-")]
