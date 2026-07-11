"""3D 360-degree view of the 3-plane context graph (three.js / 3d-force-graph).

Planes at fixed heights: y+ knowledge (top), x spine (middle), y- code (bottom).
Drag = rotate, scroll = zoom, right-drag = pan, click = fly to node.

Run:  python -m truthguard.viz3d   -> writes graph3d.html
"""
import json
import warnings

warnings.filterwarnings("ignore")

from collections import Counter
from .context_graph import ContextGraph

PLANE_Z = {"y_community": 220, "knowledge": 150, "spine": 0, "x_community": 60,
           "code": -150, "code_symbol": -150, "code_community": -220}
PLANE_COLOR = {"spine": None, "x_community": "#e3b341", "knowledge": "#39d2c0",
               "y_community": "#0f9d94", "code": "#ffa657",
               "code_symbol": "#ff7b72", "code_community": "#c2451e"}
KIND = {"answer": "#2ecc71", "refusal": "#e74c3c",
        "dual_answer": "#e67e22", "clarify": "#f1c40f"}
LINK_COLOR = {"follows": "#bc8cff", "grounds": "#39d2c0", "references": "#ffa657",
              "references_symbol": "#ff7b72", "member_of": "#e3b341",
              "calls": "#ff7b72", "quotes": "#ffa657"}


def export(path: str = "graph3d.html") -> dict:
    g = ContextGraph().g
    cites = Counter(v for u, v, e in g.edges(data=True) if e.get("relation") == "grounds")
    nodes, links = [], []
    for n, d in g.nodes(data=True):
        p = d.get("plane", "spine")
        color = PLANE_COLOR.get(p) or KIND.get(d.get("kind"), "#bc8cff")
        if p == "knowledge" and cites.get(n, 0) >= 20:
            color = "#ff4d4d"
        label = (d.get("question") or d.get("summary") or d.get("source") or n)[:60]
        size = 8 if "community" in p else (6 if p == "spine" else (7 if cites.get(n, 0) >= 20 else 4))
        nodes.append({"id": n, "name": f"[{p}] {label}", "color": color,
                      "val": size, "fz": PLANE_Z.get(p, 0)})
    for u, v, e in g.edges(data=True):
        r = e.get("relation", "")
        links.append({"source": u, "target": v, "color": LINK_COLOR.get(r, "#555"),
                      "name": r, "w": 2 if r in ("references_symbol", "calls") else 1})
    data = json.dumps({"nodes": nodes, "links": links})
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>TruthGuard 3D</title>
<style>body{{margin:0;background:#05070f;color:#c9d1d9;font-family:system-ui}}
#hud{{position:absolute;top:10px;left:14px;z-index:9;background:#0d1117cc;padding:10px 14px;border-radius:10px;font-size:12px;border:1px solid #30363d}}
#hud b{{color:#e3b341}}</style></head><body>
<div id="hud"><b>TruthGuard - 3-Plane Context Graph (3D)</b><br>
drag = rotate 360 | scroll = zoom | right-drag = pan | hover = details | click = focus<br>
<span style="color:#39d2c0">&#9632; y+ knowledge (top)</span>
<span style="color:#bc8cff">&#9632; x spine (mid)</span>
<span style="color:#ffa657">&#9632; y- code (bottom)</span>
<span style="color:#e3b341">&#9632; communities</span></div>
<div id="g"></div>
<script src="https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js"></script>
<script>
const data = {data};
const G = ForceGraph3D()(document.getElementById('g'))
  .graphData(data).backgroundColor('#05070f').nodeLabel('name')
  .nodeColor('color').nodeVal('val').linkColor('color')
  .linkWidth(l => l.w * 0.6).linkOpacity(0.45)
  .linkDirectionalParticles(l => l.name === 'grounds' ? 0 : 1)
  .linkDirectionalParticleWidth(1.2)
  .onNodeClick(n => G.cameraPosition({{x:n.x*1.2,y:n.y*1.2,z:(n.z||0)+120}}, n, 900));
let a=0, s=true;
const t=setInterval(()=>{{if(!s)return clearInterval(t);a+=0.25;
 G.cameraPosition({{x:480*Math.sin(a*Math.PI/180),z:480*Math.cos(a*Math.PI/180),y:80}});}},40);
document.getElementById('g').addEventListener('pointerdown',()=>s=false,{{once:true}});
</script></body></html>"""
    open(path, "w", encoding="utf-8").write(html)
    return {"path": path, "nodes": len(nodes), "links": len(links)}


if __name__ == "__main__":
    print(export())
