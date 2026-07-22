"""FR-1.6 — dynamic two-tier OCR ladder (per PAGE, cheapest first).

  1. native text layer (pdfplumber)        -> free, most pages
  2. Tier 1: local OCR (pytesseract or PaddleOCR, whichever is available)
  3. accept Tier 1 if mean_conf >= 0.85 and garbage_ratio < 0.20
  4. else escalate THIS PAGE to Tier 2 (Mistral OCR API), budget-capped

Every page returns provenance: {extraction, ocr_conf, ocr_engine, escalated_because}.
Missing engines degrade gracefully — a page that nothing can read is returned
with extraction="failed" and conf 0.0 (downstream confidence machinery hedges).
"""
import os
import re
import io

from . import config

_WORD_RE = re.compile(r"[a-zA-Z]{2,}")
_COMMON = set("the and for are with that this from have must all per not you of to in on is be as at by or it its".split())


def _garbage_ratio(text: str) -> float:
    """Fraction of alpha tokens that look like OCR mush (no vowels, weird caps)."""
    tokens = _WORD_RE.findall(text)
    if not tokens:
        return 1.0
    bad = 0
    for t in tokens:
        tl = t.lower()
        if tl in _COMMON:
            continue
        if not re.search(r"[aeiouy]", tl):          # no vowels -> mush
            bad += 1
        elif re.search(r"[a-z][A-Z]", t):           # mid-word case flips
            bad += 1
    return bad / len(tokens)


# ── page rendering (for OCR input) ──────────────────────────────────────────
def _render_page_image(pdf_path: str, page_index: int):
    """Return a PIL image of the page, or None. Tries pypdfium2 then PyMuPDF."""
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(pdf_path)
        bitmap = doc[page_index].render(scale=200 / 72)
        return bitmap.to_pil()
    except Exception:
        pass
    try:
        import fitz  # PyMuPDF
        from PIL import Image
        doc = fitz.open(pdf_path)
        pix = doc[page_index].get_pixmap(dpi=200)
        return Image.open(io.BytesIO(pix.tobytes("png")))
    except Exception:
        return None


# ── Tier 1: local OCR ────────────────────────────────────────────────────────
def _tier1_ocr(img):
    """Returns (text, mean_conf 0-1, engine) or (None, 0.0, None)."""
    # pytesseract first (lighter)
    try:
        import pytesseract, shutil, os
        if not shutil.which("tesseract"):
            for cand in (r"C:\Program Files\Tesseract-OCR\\tesseract.exe",
                         r"C:\Program Files (x86)\Tesseract-OCR\\tesseract.exe"):
                if os.path.exists(cand):
                    pytesseract.pytesseract.tesseract_cmd = cand
                    break
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        words, confs = [], []
        for w, c in zip(data["text"], data["conf"]):
            if w.strip() and float(c) >= 0:
                words.append(w)
                confs.append(float(c))
        if words:
            return " ".join(words), (sum(confs) / len(confs)) / 100.0, "tesseract"
    except Exception:
        pass
    # PaddleOCR fallback
    try:
        from paddleocr import PaddleOCR
        import numpy as np
        global _PADDLE
        if "_PADDLE" not in globals():
            _PADDLE = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = _PADDLE.ocr(np.array(img), cls=True)
        lines, confs = [], []
        for page in result or []:
            for entry in page or []:
                txt, conf = entry[1][0], float(entry[1][1])
                lines.append(txt)
                confs.append(conf)
        if lines:
            return "\n".join(lines), sum(confs) / len(confs), "paddleocr"
    except Exception:
        pass
    return None, 0.0, None


# ── Tier 2: pluggable escalation backend ─────────────────────────────────────
# Tier 1 (Tesseract) handles most scans and needs no GPU or key. Tier 2 only
# fires when tier 1 comes back unconfident or garbled. It used to be hardwired
# to Mistral's paid API; it is now a choice, so the project has no premium
# dependency and self-hosted models can be dropped in.
#
#   TG_OCR_TIER2 = none    (default) tier 1 only — no key, no GPU, no cost
#                  dots    dots.ocr behind an OpenAI-compatible server (vLLM).
#                          Needs CUDA and ~9-16 GB VRAM on whatever host serves
#                          it, not on this machine. Point TG_OCR_TIER2_URL at it.
#                  ollama  any local vision model (e.g. a gemma vision build).
#                          No GPU strictly required, but slow on CPU.
#                  mistral the original paid API, kept for compatibility.
_tier2_pages_used = 0


def _png_b64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    import base64
    return base64.b64encode(buf.getvalue()).decode()


_OCR_PROMPT = ("Transcribe every character of this document page to Markdown. "
               "Preserve tables, headings and layout order. Output only the "
               "transcription, no commentary.")


def _openai_vision_ocr(img, base_url: str, model: str, api_key: str, engine: str):
    """Shared path for any OpenAI-compatible /chat/completions vision endpoint.
    Both a vLLM-served dots.ocr and a local Ollama vision model speak this."""
    import requests
    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key or 'none'}"},
        json={"model": model, "max_tokens": 4096, "temperature": 0,
              "messages": [{"role": "user", "content": [
                  {"type": "text", "text": _OCR_PROMPT},
                  {"type": "image_url",
                   "image_url": {"url": f"data:image/png;base64,{_png_b64(img)}"}}]}]},
        timeout=config.OCR_TIER2_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    # A VLM reports no confidence, so score it below a clean native extraction
    # but above a garbled tier-1 result — it is a judgement, not a measurement.
    return (text, 0.90, engine) if text.strip() else None


def _mistral_ocr(img):
    import requests
    resp = requests.post(
        "https://api.mistral.ai/v1/ocr",
        headers={"Authorization": f"Bearer {config.MISTRAL_OCR_API_KEY}"},
        json={"model": "mistral-ocr-latest",
              "document": {"type": "image_url",
                           "image_url": f"data:image/png;base64,{_png_b64(img)}"}},
        timeout=config.OCR_TIER2_TIMEOUT,
    )
    resp.raise_for_status()
    text = "\n".join(p.get("markdown", "") for p in resp.json().get("pages", []))
    return (text, 0.95, "mistral-ocr") if text.strip() else None


def _tier2_ocr(img):
    """Escalate one page image. Returns (markdown_text, conf, engine) or None."""
    global _tier2_pages_used
    backend = (config.OCR_TIER2_BACKEND or "none").lower()
    if backend == "none" or _tier2_pages_used >= config.MAX_TIER2_PAGES:
        return None
    try:
        if backend == "dots":
            out = _openai_vision_ocr(img, config.OCR_TIER2_URL,
                                     config.OCR_TIER2_MODEL,
                                     config.OCR_TIER2_KEY, "dots.ocr")
        elif backend == "ollama":
            out = _openai_vision_ocr(img, config.OCR_TIER2_URL,
                                     config.OCR_TIER2_MODEL, "ollama", "ollama-vision")
        elif backend == "mistral":
            if not config.MISTRAL_OCR_API_KEY:
                return None
            out = _mistral_ocr(img)
        else:
            return None
    except Exception as e:
        # Never fail ingestion because escalation was unavailable — tier 1's
        # result still stands, and the page is marked with its real confidence.
        import sys
        print(f"  [ocr] tier-2 ({backend}) unavailable: {type(e).__name__}: {e}",
              file=sys.stderr)
        return None
    if out:
        _tier2_pages_used += 1
    return out


# ── the ladder ───────────────────────────────────────────────────────────────
def extract_pdf_pages(pdf_path: str) -> list:
    """Yield one dict per page:
    {page, text, extraction: native|ocr|failed, ocr_conf, ocr_engine,
     escalated_because, char_fonts (native only, for code detection)}"""
    import pdfplumber
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if len(text.strip()) > 50:
                # native path — also collect font names per line for code detection
                fonts = {}
                for ch in page.chars:
                    key = round(ch["top"])
                    fonts.setdefault(key, set()).add(ch.get("fontname", ""))
                pages.append({"page": i + 1, "text": text, "extraction": "native",
                              "ocr_conf": None, "ocr_engine": None,
                              "escalated_because": None, "line_fonts": fonts})
                continue

            # OCR needed
            img = _render_page_image(pdf_path, i)
            if img is None:
                pages.append({"page": i + 1, "text": "", "extraction": "failed",
                              "ocr_conf": 0.0, "ocr_engine": None,
                              "escalated_because": "no_renderer", "line_fonts": None})
                continue

            t1_text, t1_conf, t1_engine = _tier1_ocr(img)
            reason = None
            if t1_text is None:
                reason = "tier1_unavailable"
            elif t1_conf < config.OCR_TIER1_MIN_CONF:
                reason = f"low_confidence({t1_conf:.2f})"
            elif _garbage_ratio(t1_text) >= config.OCR_GARBAGE_RATIO_MAX:
                reason = f"garbage_ratio({_garbage_ratio(t1_text):.2f})"

            if reason:
                t2 = _tier2_ocr(img)
                if t2:
                    text2, conf2, engine2 = t2
                    pages.append({"page": i + 1, "text": text2, "extraction": "ocr",
                                  "ocr_conf": conf2, "ocr_engine": engine2,
                                  "escalated_because": reason, "line_fonts": None})
                    continue
                # Tier 2 unavailable -> keep best effort with honest low conf
                if t1_text:
                    pages.append({"page": i + 1, "text": t1_text, "extraction": "ocr",
                                  "ocr_conf": t1_conf, "ocr_engine": t1_engine,
                                  "escalated_because": reason + ",tier2_unavailable",
                                  "line_fonts": None})
                else:
                    pages.append({"page": i + 1, "text": "", "extraction": "failed",
                                  "ocr_conf": 0.0, "ocr_engine": None,
                                  "escalated_because": reason + ",tier2_unavailable",
                                  "line_fonts": None})
                continue

            pages.append({"page": i + 1, "text": t1_text, "extraction": "ocr",
                          "ocr_conf": t1_conf, "ocr_engine": t1_engine,
                          "escalated_because": None, "line_fonts": None})
    return pages


# ── FR-1.7: figure extraction — diagrams as first-class cited assets ─────────
def extract_page_figures(pdf_path: str, storage_dir: str) -> list:
    """Extract embedded images from PDF pages as figure assets:
    cropped PNG + bbox reference point + nearby caption + OCR of the figure."""
    import pdfplumber
    figs = []
    fig_dir = os.path.join(storage_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    with pdfplumber.open(pdf_path) as pdf:
        n = 0
        for i, page in enumerate(pdf.pages):
            if not page.images:
                continue
            rendered = _render_page_image(pdf_path, i)
            if rendered is None:
                continue
            scale = rendered.width / float(page.width)
            text = page.extract_text() or ""
            caption = next((l.strip() for l in text.splitlines()
                            if l.strip().lower().startswith("figure")), "")
            for im in page.images:
                bbox = (int(im["x0"] * scale), int(im["top"] * scale),
                        int(im["x1"] * scale), int(im["bottom"] * scale))
                crop = rendered.crop(bbox)
                if crop.width < 60 or crop.height < 60:
                    continue    # decorative speck, not a figure
                n += 1
                fname = os.path.basename(pdf_path).rsplit(".", 1)[0] + f"_fig{n}.png"
                fpath = os.path.join(fig_dir, fname)
                crop.save(fpath)
                ftext, conf, _eng = _tier1_ocr(crop)
                figs.append({"page": i + 1, "figure_n": n, "image_path": fpath,
                             "bbox": list(bbox), "caption": caption,
                             "ocr_text": ftext or "", "ocr_conf": conf})
    return figs
