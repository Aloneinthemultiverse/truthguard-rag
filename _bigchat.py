import os, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_OFFLINE","1"); os.environ.setdefault("TRANSFORMERS_OFFLINE","1")
from truthguard.chunk_store import ChunkStore
from truthguard.llm import LLM
from truthguard.controller import ask

s = ChunkStore(); llm = LLM()
QUESTIONS = [
    ("doc",     "What is the remote work stipend and who qualifies?"),
    ("doc",     "Which vendors are approved and how are their invoices processed?"),
    ("code",    "What does the retry_with_backoff function do and what are its parameters?"),
    ("codegraph","Who calls retry_with_backoff?"),
    ("conflict", "How many days do I have to file a travel expense claim?"),
    ("figure",  "What does Figure 1 in the quarterly report show?"),
    ("docx",    "How often are monitors and docking stations refreshed?"),
    ("ocr",     "What is the late-claim penalty and who signed the memo announcing it?"),
    ("clarify", "What is the limit?"),
    ("security","How often do passwords rotate and what happens with phishing reports?"),
]
for tag, q in QUESTIONS:
    try:
        r = ask(s, llm, q)
        if r["kind"] == "clarify":
            r = ask(s, llm, q, followup="the meal allowance limit")
            print(f"[{tag}] clarify->followup -> {r['kind']}: {r['text'][:90]}")
        else:
            print(f"[{tag}] {r['kind']} conf={r.get('confidence')}: {r['text'][:90]}")
    except Exception as e:
        print(f"[{tag}] ERROR {e}")

# rebuild x-plane topic communities over the grown spine
import anthropic
from sentence_transformers import SentenceTransformer
from truthguard import config
from truthguard.context_graph import ContextGraph
from truthguard.planes import build_x
cg = ContextGraph()
cg.g.remove_nodes_from([n for n,d in cg.g.nodes(data=True) if d.get("plane")=="x_community"])
client = anthropic.Anthropic(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
embed = SentenceTransformer(config.EMBED_MODEL)
print("\nx-plane rebuild:", build_x(cg, client, embed))

from truthguard.viz import export_html
print("viz:", export_html("context_graph_dg.html"))
