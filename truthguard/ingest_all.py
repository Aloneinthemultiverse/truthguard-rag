"""One-shot project absorb: chat + ENTIRE codebase + ALL documents, cross-wired.

ingest_project(repo_path, chat_path=None):
  1. GitNexus-index the repo (full analysis, involved code or not)
  2. Load the whole code graph into the y- plane (nodes + calls/defines/imports)
  3. AST-digest every function/class body for content retrieval
  4. Find every document in the repo (.md/.pdf/.docx/.txt) -> corpus -> index
  5. Import the chat transcript (if given) -> spine turns
  6. Retro-link: every turn wired to the entities / doc chunks / code it mentions
  7. Re-export the live 3D view

Entity extraction (LLM) is NOT run automatically — call rebuild_communities after.

Run:  python -m truthguard.ingest_all <repo_path> [chat.jsonl|chat.txt]
"""
import os
import sys
import shutil
import subprocess
import warnings

warnings.filterwarnings("ignore")

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_EXTS = (".md", ".pdf", ".docx", ".txt")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist",
             "build", ".gitnexus", "storage", ".tmp", ".next"}


def ingest_project(repo_path: str = None, chat_path: str = None) -> dict:
    report = {}
    from . import code_link

    # 1) code: gitnexus full index + switch linked repo
    if repo_path:
        repo_path = os.path.abspath(repo_path)
        try:
            subprocess.run(["gitnexus", "analyze", repo_path],
                           capture_output=True, text=True, timeout=900, shell=True)
        except Exception as e:
            report["gitnexus"] = f"analyze failed: {e}"
        code_link.CODE_REPO = os.path.basename(os.path.normpath(repo_path))
        code_link._cache.clear()
        report["repo"] = code_link.CODE_REPO

        # 2) whole code graph -> y- plane
        from .context_graph import ContextGraph
        from .planes import load_code_plane, build_y_minus
        cg = ContextGraph()
        report["code_plane"] = load_code_plane(cg)
        report["code_communities"] = build_y_minus(cg)

        # 3) code bodies digest (this project + the new repo)
        from . import code_digest
        report["code_digest"] = code_digest.build([ROOT, repo_path], incremental=True)

        # 4) every document in the repo -> corpus
        copied = 0
        os.makedirs(config.CORPUS_DIR, exist_ok=True)
        for dirpath, dirnames, filenames in os.walk(repo_path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.lower().endswith(DOC_EXTS) and fn.upper() not in ("LICENSE.TXT",):
                    dst = f"{report['repo']}__{fn}"
                    try:
                        shutil.copy2(os.path.join(dirpath, fn),
                                     os.path.join(config.CORPUS_DIR, dst))
                        copied += 1
                    except OSError:
                        pass
        if copied:
            from .pipeline import ingest_corpus
            from .chunk_store import build_index
            _, ing = ingest_corpus()
            report["documents"] = {"copied": copied,
                                   "total_chunks": ing["total_chunks"],
                                   "engine": build_index()}

    # 5) chat transcript -> spine (import_chat retro-links + exports itself)
    if chat_path:
        from .import_chat import import_chat
        report["chat"] = import_chat(chat_path)
    else:
        # 6) still retro-link existing turns to the newly absorbed content
        try:
            from sentence_transformers import SentenceTransformer
            from .context_graph import ContextGraph
            from .planes import retro_link_spine
            report["cross_links"] = retro_link_spine(
                ContextGraph(), SentenceTransformer(config.EMBED_MODEL))
        except Exception as e:
            report["cross_links"] = str(e)

    # 7) live view
    try:
        from .full3d import export_full
        report["export"] = export_full()
    except Exception:
        pass
    return report


if __name__ == "__main__":
    import json
    repo = sys.argv[1] if len(sys.argv) > 1 else None
    chat = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(ingest_project(repo, chat), indent=1))
