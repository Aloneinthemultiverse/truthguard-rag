import os, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_OFFLINE","1"); os.environ.setdefault("TRANSFORMERS_OFFLINE","1")
from truthguard.chunk_store import ChunkStore
from truthguard.llm import LLM
from truthguard.controller import ask
s = ChunkStore(); llm = LLM()
def run(tid, q, **kw):
    try:
        r = ask(s, llm, q, **kw)
        print(f"\n### {tid} [{r['kind']}] conf={r.get('confidence')}")
        print("A:", r["text"][:300].replace("\n"," | "))
        for f in r.get("figures") or []: print("IMAGE REF:", f)
    except Exception as e:
        print(f"\n### {tid} ERROR: {e}")
run("E14a-fix","What is the limit?")                                   # expect CLARIFY now
run("B5-fix","What is the travel limit in the 2025 policy?")           # expect year-guard REFUSAL
run("B6-fix","How much more is the 2024 travel limit than the 2023 limit?")  # expect difference line
run("A4-fix","What is the current travel reimbursement limit?")        # expect $500 answer or informative dual
run("D11-fix","Who calls the retry_with_backoff function?")            # expect structural answer
run("FIG1","Which quarter had the highest invoice volume in 2024?")    # expect Q4=210 + image ref
