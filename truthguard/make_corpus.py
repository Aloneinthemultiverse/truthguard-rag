"""M1 — generate the seeded evaluation corpus (traps disclosed in docs/PRD.md FR-5.2).

Planted traps:
  T1 contradiction : policy_2023.pdf says travel limit $300; policy_2024.pdf says $500
  T2 scoped-fact   : equipment limit differs by role (intern $200 / staff $800) — NOT a contradiction
  T3 scan-only fact: late-claim penalty (2%/week) exists ONLY in a scanned memo (image PDF)
  T4 ocr-numeral   : the scanned memo also shows the $500 travel limit (OCR may misread)
  T5 code-in-pdf   : vendor_api_guide.pdf embeds a Python retry function (monospace)
  T6 ambiguity     : "the limit" is ambiguous across travel/equipment/meal categories
  T7 absent topics : nothing anywhere about parental leave or crypto reimbursement

Run:  python -m truthguard.make_corpus
"""
import os
import io

from . import config

OUT = config.CORPUS_DIR

POLICY_2023 = """# Expense Reimbursement Policy (2023 Edition)
Effective: January 1, 2023. Document ID: POL-2023-EXP.

## 1. Travel expenses
The travel reimbursement limit is $300 per trip for all employees.
Claims must be filed within 30 days of travel completion.

## 2. Equipment purchases
Equipment reimbursement is role-dependent:
- Interns: up to $200 per fiscal year.
- Full-time staff: up to $800 per fiscal year.
Purchases above these limits require written pre-approval from Finance.

## 3. Meals
Meal allowance during business travel is $40 per day, receipts required.

## 4. Vendors
Approved vendors: Acme Supplies, Bright Office Co, and DataHub Ltd.
All vendor invoices are processed through the Finance portal.
"""

POLICY_2024 = """# Expense Reimbursement Policy (2024 Edition)
Effective: March 15, 2024. Document ID: POL-2024-EXP. Supersedes POL-2023-EXP
for travel expenses only; all other sections of the 2023 edition remain in force
unless amended separately.

## 1. Travel expenses (amended)
The travel reimbursement limit is $500 per trip for all employees.
Claims must be filed within 45 days of travel completion.

## 2. Remote work stipend (new)
A remote work stipend of $75 per month is available to hybrid employees
working from home at least three days per week.
"""

VENDOR_API_GUIDE_TEXT = """Vendor Invoice API — Integration Guide
Version 2.1. For the Finance portal team.

All vendor invoices are submitted through the REST endpoint POST /api/v2/invoices.
Authentication uses a bearer token issued per vendor. The API enforces a rate
limit of 60 requests per minute. On transient failures (HTTP 429 or 5xx),
clients MUST retry using the exponential backoff routine shipped in the SDK,
reproduced below (Listing 3):
"""

VENDOR_API_CODE = '''def retry_with_backoff(request_fn, max_retries=5, base_delay=1.0):
    """Retry a request with exponential backoff and jitter.

    Retries only on 429/5xx. Delay doubles each attempt, capped at 60s.
    Raises the last error after max_retries attempts.
    """
    import random, time
    for attempt in range(max_retries):
        try:
            resp = request_fn()
            if resp.status_code < 400:
                return resp
            if resp.status_code not in (429, 500, 502, 503, 504):
                resp.raise_for_status()
        except ConnectionError as e:
            last_err = e
        delay = min(base_delay * (2 ** attempt), 60.0)
        time.sleep(delay + random.uniform(0, 0.5))
    raise RuntimeError(f"request failed after {max_retries} retries")
'''

SCANNED_MEMO = """INTERNAL MEMO - FINANCE DEPARTMENT
Date: April 2, 2024        Ref: MEMO-FIN-118

Subject: Late expense claims and travel limit reminder

1. Effective May 1, 2024, expense claims submitted after the
   filing deadline incur a late-processing penalty of 2% of
   the claim value per week late, capped at 10%.

2. Reminder: the travel reimbursement limit is $500 per trip
   as per the 2024 policy edition.

3. Direct questions to the Finance service desk.

                                signed, R. Iyer, Finance Controller
"""

FILLER_HR = """# Employee Onboarding Handbook (extract)
Welcome to the company. Your first week includes IT setup, security training,
and a meeting with your manager. Badge access is issued on day one.
The IT helpdesk operates 9am-6pm on weekdays. Payroll runs on the 28th of
each month. For benefits enrollment, use the HR portal within 30 days of joining.
"""

FILLER_SECURITY = """# Data Security Guidelines (extract)
All laptops must use full-disk encryption. Passwords rotate every 90 days.
Confidential documents are shared only via the approved document management
system. Report suspected phishing to security@company.example within 24 hours.
USB storage devices are prohibited on production systems.
"""


def _write(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  wrote {path}")


def _md_to_pdf(md_text: str, pdf_path: str, mono_block: str = None) -> bool:
    """Render simple text to a native-text PDF. Monospace block rendered in Courier
    (this is what our code detector keys on). Returns False if fpdf2 missing."""
    try:
        from fpdf import FPDF
    except ImportError:
        return False
    md_text = md_text.replace("—", "-").replace("–", "-")
    if mono_block:
        mono_block = mono_block.replace("—", "-").replace("–", "-")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in md_text.splitlines():
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 15)
            pdf.multi_cell(180, 8, line[2:])
            pdf.set_font("Helvetica", size=11)
        elif line.startswith("## "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(180, 7, line[3:])
            pdf.set_font("Helvetica", size=11)
        elif not line.strip():
            pdf.ln(4)
        else:
            pdf.multi_cell(180, 6, line)
    if mono_block:
        pdf.set_font("Courier", size=9)
        for line in mono_block.splitlines():
            if line.strip():
                pdf.multi_cell(180, 5, line)
            else:
                pdf.ln(3)
    pdf.output(pdf_path)
    print(f"  wrote {pdf_path}")
    return True


def _make_scanned_pdf(text: str, pdf_path: str) -> bool:
    """Render text to an IMAGE, embed image in a PDF -> no text layer (a 'scan').
    Slight rotation makes it realistically messy. Returns False if deps missing."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        from fpdf import FPDF
    except ImportError:
        return False
    img = Image.new("RGB", (1240, 1754), "white")   # A4 @150dpi
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("cour.ttf", 28)   # Courier = typewriter memo
    except Exception:
        font = ImageFont.load_default()
    y = 80
    for line in text.splitlines():
        draw.text((90, y), line, fill=(20, 20, 20), font=font)
        y += 42
    img = img.rotate(-1.2, expand=False, fillcolor="white")  # crooked scan
    tmp_png = pdf_path.replace(".pdf", "_page1.png")
    img.save(tmp_png, dpi=(150, 150))
    pdf = FPDF(unit="mm", format="A4")
    pdf.add_page()
    pdf.image(tmp_png, x=0, y=0, w=210, h=297)
    pdf.output(pdf_path)
    os.remove(tmp_png)
    print(f"  wrote {pdf_path} (image-only, no text layer)")
    return True


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f"Generating seeded corpus in {OUT}/")

    # T1 contradiction pair (also T2 scoped facts inside 2023 doc)
    if not _md_to_pdf(POLICY_2023, os.path.join(OUT, "policy_2023.pdf")):
        _write(os.path.join(OUT, "policy_2023.md"), POLICY_2023)
    if not _md_to_pdf(POLICY_2024, os.path.join(OUT, "policy_2024.pdf")):
        _write(os.path.join(OUT, "policy_2024.md"), POLICY_2024)

    # T3/T4 scan-only memo (penalty fact exists ONLY here)
    if not _make_scanned_pdf(SCANNED_MEMO, os.path.join(OUT, "scanned_memo_118.pdf")):
        print("  !! PIL/fpdf2 missing - scan not generated (install fpdf2 pillow)")

    # T5 code embedded in a PDF (Courier block)
    if not _md_to_pdf(VENDOR_API_GUIDE_TEXT, os.path.join(OUT, "vendor_api_guide.pdf"),
                      mono_block=VENDOR_API_CODE):
        _write(os.path.join(OUT, "vendor_api_guide.md"),
               VENDOR_API_GUIDE_TEXT + "\n```python\n" + VENDOR_API_CODE + "\n```\n")

    # fillers (give retrieval something to be wrong about)
    _write(os.path.join(OUT, "onboarding_handbook.md"), FILLER_HR)
    _write(os.path.join(OUT, "security_guidelines.md"), FILLER_SECURITY)

    print("Done. Traps T1-T7 seeded (T6/T7 are question-side, no doc needed).")


if __name__ == "__main__":
    main()


def make_chart_pdf(out_dir: str = None):
    """A PDF containing a bar chart image + caption — exercises the Figure Asset path."""
    out_dir = out_dir or OUT
    try:
        from PIL import Image, ImageDraw, ImageFont
        from fpdf import FPDF
    except ImportError:
        return False
    img = Image.new("RGB", (900, 500), "white")
    d = ImageDraw.Draw(img)
    try:
        big = ImageFont.truetype("arial.ttf", 34)
        med = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        big = med = ImageFont.load_default()
    d.text((240, 20), "Invoice Volume by Quarter 2024", fill="black", font=big)
    data = [("Q1", 120), ("Q2", 180), ("Q3", 90), ("Q4", 210)]
    for i, (label, v) in enumerate(data):
        x = 120 + i * 190
        d.rectangle([x, 430 - v * 1.5, x + 110, 430], fill=(70, 90, 200))
        d.text((x + 25, 435), label, fill="black", font=med)
        d.text((x + 25, 395 - v * 1.5), str(v), fill="black", font=med)
    png = os.path.join(out_dir, "_chart_tmp.png")
    img.save(png)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(180, 8, "Finance Portal Quarterly Report (2024)")
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(180, 6, "The Finance portal processed vendor invoices throughout 2024. "
                           "Volumes varied by quarter as shown below.")
    pdf.image(png, x=15, y=40, w=180)
    pdf.set_y(145)
    pdf.multi_cell(180, 6, "Figure 1: Invoice volume by quarter, 2024 (count of invoices processed).")
    pdf.multi_cell(180, 6, "Q4 volume reflects the year-end procurement cycle.")
    pdf.output(os.path.join(out_dir, "quarterly_report.pdf"))
    os.remove(png)
    print(f"  wrote {out_dir}/quarterly_report.pdf (with embedded chart)")
    return True
