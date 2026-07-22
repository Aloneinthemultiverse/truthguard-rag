"""Push the TruthGuard API to a Hugging Face Space.

Run `huggingface-cli login` first; this script reads the stored token and never
takes one as an argument, so no credential passes through a shell history.

    python deploy_hf.py                 # full graph
    python deploy_hf.py --no-chats      # strip the conversation plane first
"""
import argparse
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SPACE_NAME = "truthguard-api"

# Only these paths go up. An allowlist rather than an ignore list, so a new file
# on disk cannot silently end up in a public Space.
INCLUDE = [
    "truthguard", "corpus", "storage", "eval",
    "requirements.txt", "Dockerfile", ".dockerignore",
    "graph3d_data.json", "FULL_3plane_clean.html",
]
# Belt and braces: never upload these even if nested inside an included dir.
DENY_SUFFIX = (".env", ".env.bak.nim", ".pyc", ".log")
DENY_DIRS = {"__pycache__", "node_modules", ".git", "locomo_data", "longmemeval_data"}


def strip_chats(storage_dir: str) -> int:
    """Drop the conversation plane from the graph copy that gets published."""
    import pickle
    p = os.path.join(storage_dir, "context_graph.pkl")
    d = pickle.load(open(p, "rb"))
    G = d["g"]
    doomed = [n for n, a in G.nodes(data=True) if a.get("plane") in ("spine", "chat")]
    G.remove_nodes_from(doomed)
    pickle.dump(d, open(p, "wb"))
    return len(doomed)


def stage(no_chats: bool) -> str:
    tmp = tempfile.mkdtemp(prefix="tg_space_")
    for item in INCLUDE:
        src = os.path.join(ROOT, item)
        if not os.path.exists(src):
            print(f"  skip (missing): {item}")
            continue
        dst = os.path.join(tmp, item)
        if os.path.isdir(src):
            shutil.copytree(
                src, dst,
                ignore=lambda d, names: [
                    n for n in names
                    if n in DENY_DIRS or n.endswith(DENY_SUFFIX)])
        else:
            shutil.copy2(src, dst)
        print(f"  staged: {item}")

    # The Space's README carries the required YAML frontmatter.
    shutil.copy2(os.path.join(ROOT, "HF_SPACE_README.md"), os.path.join(tmp, "README.md"))

    if no_chats:
        n = strip_chats(os.path.join(tmp, "storage", "truthguard"))
        print(f"  stripped {n} conversation nodes from the published graph")

    # Final sweep: fail loudly rather than publish a credential.
    import re
    pat = re.compile(rb"nvapi-[A-Za-z0-9_\-]{15,}|sk-[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{30,}")
    for dirpath, dirnames, filenames in os.walk(tmp):
        dirnames[:] = [d for d in dirnames if d not in DENY_DIRS]
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            if os.path.getsize(fp) > 20_000_000:
                continue
            try:
                if pat.search(open(fp, "rb").read()):
                    sys.exit(f"ABORT: credential-shaped string found in {os.path.relpath(fp, tmp)}")
            except OSError:
                pass
    print("  secret sweep: clean")
    return tmp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-chats", action="store_true",
                    help="strip the conversation plane before publishing")
    args = ap.parse_args()

    from huggingface_hub import HfApi
    api = HfApi()
    try:
        user = api.whoami()["name"]
    except Exception:
        sys.exit("Not logged in. Run:  huggingface-cli login")
    repo_id = f"{user}/{SPACE_NAME}"
    print(f"user: {user}\ntarget: https://huggingface.co/spaces/{repo_id}\n")

    print("staging files:")
    tmp = stage(args.no_chats)

    api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker",
                    exist_ok=True)
    print("\nuploading (first build takes ~10 min while Docker installs deps)…")
    api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=tmp,
                      commit_message="Deploy TruthGuard API")
    shutil.rmtree(tmp, ignore_errors=True)

    url = f"https://{user.lower().replace('_', '-')}-{SPACE_NAME}.hf.space"
    print(f"\ndone.\n  Space:    https://huggingface.co/spaces/{repo_id}")
    print(f"  API base: {url}")
    print(f"\nWatch the build log on the Space page. When it says Running, test:")
    print(f"  curl {url}/stats")


if __name__ == "__main__":
    main()
