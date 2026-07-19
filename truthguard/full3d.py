"""Full 3-plane 3D exporter — ALL entities: documents + code + chat.

Reads storage/truthguard/context_graph.pkl (the live graph the MCP writes to)
and produces graph3d_data.json for the live view. Every plane, every node:
  y+ document ENTITIES + doc-communities (top)
  x  chat turns (middle)
  y- code files + code symbols (bottom)

export_full() is called by the MCP server on every chat/ingest, so the view
grows live as the user talks.

Run standalone:  python -m truthguard.full3d   -> writes graph3d_data.json + FULL_3plane_clean.html
"""
import os
import json
import pickle

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PLANE_Z = {"doc_community": 320, "entity": 200, "y_community": 200,
           "spine": 0, "chat": 0, "x_community": 60,
           "code_file": -180, "code": -300, "code_symbol": -300,
           "code_community": -360, "knowledge": 200}
PLANE_COLOR = {"doc_community": "#0f9d94", "entity": "#39d2c0", "y_community": "#0f9d94",
               "knowledge": "#39d2c0", "chat": "#bc8cff", "x_community": "#e3b341",
               "code_file": "#ffd166", "code": "#ff8c42", "code_symbol": "#ff7b72",
               "code_community": "#c2451e"}
KIND = {"answer": "#2ecc71", "refusal": "#e74c3c", "dual_answer": "#e67e22",
        "clarify": "#f1c40f", "chat": "#bc8cff"}
LINK_COLOR = {"follows": "#8a63d2", "grounds": "#39d2c0", "references": "#ff8c42",
              "references_symbol": "#ff7b72", "calls": "#ff7b72", "edited": "#ff2d55",
              "member_of": "#e3b341", "defines": "#7a5c2e", "quotes": "#ffa657"}


def _graph(storage_dir=None):
    p = os.path.join(storage_dir or config.STORAGE_DIR, "context_graph.pkl")
    if not os.path.exists(p):
        return None
    return pickle.load(open(p, "rb"))["g"]


def export_full(storage_dir=None, out=None):
    """Write graph3d_data.json with every plane. Returns node/edge counts."""
    g = _graph(storage_dir)
    if g is None:
        return {"nodes": 0, "links": 0}
    deg = dict(g.degree())
    # one distinct hue + x-offset per chat session so conversations
    # occupy separate regions instead of mingling in the force layout
    SESSION_COLORS = ["#bc8cff", "#58a6ff", "#f78166", "#7ee787", "#d2a8ff",
                      "#ffa657", "#79c0ff", "#ff7b72"]
    sessions = sorted({d.get("session", "live") for _, d in g.nodes(data=True)
                       if d.get("plane") == "spine"})
    s_color = {s: SESSION_COLORS[i % len(SESSION_COLORS)]
               for i, s in enumerate(sessions)}
    s_fx = {s: (i - (len(sessions) - 1) / 2) * 1100 for i, s in enumerate(sessions)}

    def _jitter(node_id, spread=380):
        """Deterministic per-node offset so each galaxy is a CLOUD, not a sheet."""
        h = hash(node_id) & 0xffff
        return (h / 0xffff - 0.5) * 2 * spread
    nodes, links = [], []
    for n, d in g.nodes(data=True):
        p = d.get("plane", "chat")
        label = (d.get("label") or d.get("question") or d.get("summary")
                 or d.get("source") or n)
        node = {"id": n, "name": f"[{p}] {label[:70]}",
                "val": 3 + min(deg.get(n, 0), 18) * 0.55,
                "fz": PLANE_Z.get(p, 0)}
        if p == "spine":
            s = d.get("session", "live")
            node["color"] = s_color.get(s, "#bc8cff")
            node["fx"] = s_fx.get(s, 0) + _jitter(n, 180)   # lane + thread spread
            node["name"] = f"[chat @{s}] {label[:70]}"
        else:
            node["color"] = PLANE_COLOR.get(p) or KIND.get(d.get("kind"), "#bc8cff")
            # SOLAR SYSTEMS: pin each session's content near its own chat.
            # Which system does a non-chat node belong to?
            src = str(d.get("source", "")) + " " + str(n) + " " + str(d.get("repo", ""))
            # repo tag if present; else path heuristic (truthguard dirs -> dg lane)
            if d.get("repo") == "vibe-thinker" or "vibe-thinker" in src or (
                    p in ("code", "code_file") and not src.split()[0].startswith(
                        ("truthguard", "decisiongraph", "demo_repo", "eval", "_", "vendor_sdk"))):
                node["fx"] = s_fx.get(next((x for x in sessions
                                            if "vibe" in x), None), 0) + _jitter(n)
            elif p == "x_community":
                # topic hub: pin to majority session; mixed hubs sit center
                ss = [g.nodes[u].get("session") for u, _, e in g.in_edges(n, data=True)
                      if e.get("relation") == "member_of"]
                if ss:
                    top = max(set(ss), key=ss.count)
                    node["fx"] = s_fx.get(top, 0) * (0.7 if len(set(ss)) > 1 else 1.0) + _jitter(n, 250)
            elif p in ("code", "code_file", "knowledge"):
                node["fx"] = s_fx.get("decisiongraph-7d4c2d0d",
                                      -abs(list(s_fx.values())[0]) if s_fx else 0) + _jitter(n)
        nodes.append(node)
    for u, v, e in g.edges(data=True):
        r = e.get("relation", "")
        du, dv = g.nodes[u], g.nodes[v]
        cross = (du.get("plane") == "spine" and dv.get("plane") == "spine"
                 and du.get("session") != dv.get("session"))
        links.append({"source": u, "target": v, "name": r,
                      # cross-session semantic bridges: nearly invisible threads
                      "color": "#10162a" if cross else LINK_COLOR.get(r, "#3a4a6a"),
                      "w": 0.1 if cross else
                           (3 if r == "edited" else
                            (2 if r in ("grounds", "references", "calls") else 1))})
    out = out or os.path.join(ROOT, "graph3d_data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"nodes": nodes, "links": links}, f)
    return {"nodes": len(nodes), "links": len(links)}


def write_html(path=None):
    path = path or os.path.join(ROOT, "FULL_3plane_clean.html")
    export_full()
    html = """<!doctype html><html><head><meta charset="utf-8"><title>TruthGuard — Full 3-Plane (live)</title>
<style>body{margin:0;background:#05070f;color:#c9d1d9;font-family:system-ui}
#hud{position:absolute;top:10px;left:14px;z-index:9;background:#0d1117e0;padding:11px 15px;border-radius:10px;font-size:12px;border:1px solid #30363d;max-width:720px}
#hud b{color:#fff} #stat{color:#39d2c0;font-weight:700}</style></head><body>
<div id="hud"><b>TruthGuard — FULL 3-Plane Context Graph (LIVE)</b> <span id="stat"></span><br>
documents (entities) + code (.py) + chat — grows as you chat via MCP<br>
drag=rotate 360&deg; | scroll=zoom | right-drag=pan | hover | click=fly in<br>
<span style="color:#39d2c0">&#9632; doc entities (top)</span>
<span style="color:#bc8cff">&#9632; chat (mid)</span>
<span style="color:#ff8c42">&#9632; code (bottom)</span>
<span style="color:#ff2d55">&mdash; edited</span> <span style="color:#ff7b72">&mdash; calls</span> <span style="color:#8a63d2">&mdash; follows</span></div>
<div id="g"></div>
<script src="https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js"></script>
<script>
const G=ForceGraph3D()(document.getElementById('g'))
 .backgroundColor('#05070f').nodeLabel('name').nodeColor('color').nodeVal('val')
 .linkColor('color').linkWidth(l=>l.w*0.5).linkOpacity(0.5)
 .linkDirectionalParticles(l=>l.name==='edited'||l.name==='calls'?2:0).linkDirectionalParticleWidth(1.4)
 .onNodeClick(n=>G.cameraPosition({x:n.x*1.15,y:n.y*1.15,z:(n.z||0)+110},n,900));
let known=0, spin=true;
async function poll(){
 try{
  const d=await (await fetch('graph3d_data.json?t='+Date.now())).json();
  if(d.nodes.length!==known){
   const cur=Object.fromEntries(G.graphData().nodes.map(n=>[n.id,n]));
   d.nodes.forEach(n=>{const o=cur[n.id]; if(o){n.x=o.x;n.y=o.y;n.z=o.z;}});
   G.graphData(d); known=d.nodes.length;
   document.getElementById('stat').textContent=`· ${d.nodes.length} nodes / ${d.links.length} edges — ${new Date().toLocaleTimeString()}`;
  }
 }catch(e){document.getElementById('stat').textContent='· waiting for MCP…';}
}
poll(); setInterval(poll,4000);
let a=0;const t=setInterval(()=>{if(!spin)return clearInterval(t);a+=0.24;
 G.cameraPosition({x:760*Math.sin(a*Math.PI/180),z:760*Math.cos(a*Math.PI/180),y:15});},40);
document.getElementById('g').addEventListener('pointerdown',()=>spin=false,{once:true});
</script></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


if __name__ == "__main__":
    print("data:", export_full())
    print("html:", write_html())
