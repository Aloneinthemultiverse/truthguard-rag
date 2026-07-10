"""FR-1.3/1.4 — structure-aware chunking with code detection and provenance.

Rules:
- split on markdown headings first, then pack to ~CHUNK_SIZE chars with overlap
- code blocks are ATOMIC: never split, never merged into prose chunks
- code detection: md fences | monospace fonts (native PDF) | symbol density + keywords
- every chunk carries {source_file, page, extraction, ocr_conf, content_type, language}
"""
import re
import hashlib

from . import config

_CODE_KEYWORDS = re.compile(
    r"\b(def |class |import |return |function |const |let |var |for\s*\(|while\s*\(|"
    r"if\s*\(|=>|\{|\}|raise |except |lambda )")
_FENCE_RE = re.compile(r"^```(\w*)\s*$")


def _symbol_density(line: str) -> float:
    if not line.strip():
        return 0.0
    symbols = sum(1 for c in line if c in "{}()[];=<>+-*/_#:")
    return symbols / len(line)


def looks_like_code(block: str) -> bool:
    lines = [l for l in block.splitlines() if l.strip()]
    if not lines:
        return False
    kw_hits = sum(1 for l in lines if _CODE_KEYWORDS.search(l))
    dens = sum(_symbol_density(l) for l in lines) / len(lines)
    indented = sum(1 for l in lines if l.startswith(("    ", "\t"))) / len(lines)
    return (kw_hits / len(lines) > 0.25) or (dens > 0.12 and indented > 0.3)


def _guess_language(block: str) -> str:
    if re.search(r"\bdef |import |self\.|None\b", block):
        return "python"
    if re.search(r"\bfunction |const |=>|console\.", block):
        return "javascript"
    if re.search(r"\bpublic |private |void |System\.", block):
        return "java"
    return "unknown"


def _chunk_id(source: str, page, seq: int) -> str:
    return hashlib.sha1(f"{source}|{page}|{seq}".encode()).hexdigest()[:12]


def _mono_line_keys(line_fonts: dict) -> set:
    """Line y-positions whose chars are predominantly Courier/Mono (PDF code)."""
    keys = set()
    for y, fonts in (line_fonts or {}).items():
        if any("courier" in f.lower() or "mono" in f.lower() for f in fonts):
            keys.add(y)
    return keys


def split_code_blocks(text: str, line_fonts: dict = None) -> list:
    """Split raw text into [(kind, block)] where kind in {prose, code}.
    Uses md fences first; falls back to run-detection via looks_like_code."""
    segments = []
    cur, cur_kind, in_fence = [], "prose", False
    for line in text.splitlines():
        m = _FENCE_RE.match(line)
        if m:
            if in_fence:                       # closing fence
                segments.append(("code", "\n".join(cur)))
                cur, cur_kind, in_fence = [], "prose", False
            else:                              # opening fence
                if cur:
                    segments.append((cur_kind, "\n".join(cur)))
                cur, cur_kind, in_fence = [], "code", True
            continue
        cur.append(line)
    if cur:
        segments.append(("code" if in_fence else cur_kind, "\n".join(cur)))

    # second pass: inside prose segments, detect unfenced code runs
    out = []
    for kind, block in segments:
        if kind == "code" or not block.strip():
            if block.strip():
                out.append((kind, block))
            continue
        lines = block.splitlines()
        run, run_is_code = [], False
        for line in lines:
            is_code = bool(_CODE_KEYWORDS.search(line)) and _symbol_density(line) > 0.06
            if is_code == run_is_code:
                run.append(line)
            else:
                if run:
                    blk = "\n".join(run)
                    out.append(("code" if run_is_code and looks_like_code(blk) else "prose", blk))
                run, run_is_code = [line], is_code
        if run:
            blk = "\n".join(run)
            out.append(("code" if run_is_code and looks_like_code(blk) else "prose", blk))

    # merge adjacent same-kind blocks
    merged = []
    for kind, block in out:
        if merged and merged[-1][0] == kind:
            merged[-1] = (kind, merged[-1][1] + "\n" + block)
        else:
            merged.append((kind, block))
    return merged


def chunk_page(page_rec: dict, source_file: str, seq_start: int = 0) -> list:
    """Chunk one extracted page record into provenance-tagged chunk dicts."""
    chunks = []
    seq = seq_start
    base = {
        "source_file": source_file,
        "page": page_rec["page"],
        "extraction": page_rec["extraction"],
        "ocr_conf": page_rec.get("ocr_conf"),
        "ocr_engine": page_rec.get("ocr_engine"),
    }
    for kind, block in split_code_blocks(page_rec["text"], page_rec.get("line_fonts")):
        if kind == "code":
            chunks.append({**base, "id": _chunk_id(source_file, page_rec["page"], seq),
                           "seq": seq, "content_type": "code",
                           "language": _guess_language(block), "text": block})
            seq += 1
            continue
        # prose: split on headings, pack to size with overlap
        sections = re.split(r"(?m)(?=^#{1,3} )", block)
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue
            start = 0
            while start < len(sec):
                piece = sec[start:start + config.CHUNK_SIZE]
                chunks.append({**base, "id": _chunk_id(source_file, page_rec["page"], seq),
                               "seq": seq, "content_type": "prose",
                               "language": None, "text": piece})
                seq += 1
                if start + config.CHUNK_SIZE >= len(sec):
                    break
                start += config.CHUNK_SIZE - config.CHUNK_OVERLAP
    return chunks
