"""3-plane context graph -> self-contained interactive HTML.

Ported from Decision_Graph's code_graph_viz.py (same template, same offline
vis-network bundle, same god-node highlighting) — pointed at context_graph.pkl
instead of the SQLite code graph.

Planes render as layers (hierarchical Y): knowledge/communities on top,
spine in the middle, code + symbols below. Most-cited sources = god-nodes (red),
exactly like DG highlighted chokepoint symbols.

Usage:  python -m truthguard.viz  [out.html]
"""
import json
import sys
from pathlib import Path
from collections import Counter

from . import config
from .context_graph import ContextGraph

_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  html, body { margin:0; padding:0; height:100%; font-family:system-ui,sans-serif; background:#0d1117; color:#c9d1d9; }
  #toolbar { padding:8px 16px; background:#161b22; border-bottom:1px solid #30363d; display:flex; gap:14px; align-items:center; flex-wrap:wrap; }
  #toolbar h1 { font-size:14px; margin:0; }
  #toolbar label { font-size:12px; color:#8b949e; user-select:none; }
  #toolbar input[type=checkbox] { accent-color:#58a6ff; }
  #toolbar input[type=text] { background:#0d1117; color:#c9d1d9; border:1px solid #30363d; border-radius:4px; padding:4px 8px; font-size:12px; width:240px; }
  #viz { width:100%; height:calc(100vh - 50px); }
  #info { position:fixed; top:60px; right:16px; max-width:360px; background:#161b22; border:1px solid #30363d; padding:10px 12px; border-radius:6px; font-size:12px; display:none; }
  #info b { color:#7ee787; }
  .legend { display:flex; gap:8px; font-size:11px; }
  .swatch { width:10px; height:10px; border-radius:50%; display:inline-block; margin-right:4px; vertical-align:middle; }
</style>
</head>
<body>
<div id="toolbar">
  <h1>__TITLE__</h1>
  <span class="legend">
    <span><span class="swatch" style="background:#bc8cff"></span>x spine</span>
    <span><span class="swatch" style="background:#39d2c0"></span>y+ knowledge</span>
    <span><span class="swatch" style="background:#ffa657"></span>y&minus; code</span>
    <span><span class="swatch" style="background:#ff7b72"></span>symbol</span>
    <span><span class="swatch" style="background:#e3b341"></span>community</span>
    <span><span class="swatch" style="background:#f85149"></span>god-node</span>
  </span>
  <label><input type="checkbox" id="hideComm"> hide communities</label>
  <input type="text" id="search" placeholder="search turns, sources, symbols...">
  <span style="font-size:11px;color:#8b949e">__SUMMARY__</span>
</div>
<div id="viz"></div>
<div id="info"></div>

<script>
__VIS_BUNDLE__
</script>
<script>
const DATA = __DATA__;
const nodes = new vis.DataSet(DATA.nodes);
const edges = new vis.DataSet(DATA.edges);
let network = new vis.Network(document.getElementById('viz'),
  { nodes, edges },
  {
    interaction: { hover:true, tooltipDelay:120 },
    nodes: { shape:'dot', size:8, font:{ color:'#c9d1d9', size:10 } },
    edges: { arrows:{ to:{ enabled:true, scaleFactor:0.5 } }, smooth:false,
             font:{ color:'#8b949e', size:8, strokeWidth:0 } },
    layout: { hierarchical: { enabled:true, direction:'UD',
              sortMethod:'directed', levelSeparation:150, nodeSpacing:120 } },
    physics: false,
  });

document.getElementById('hideComm').addEventListener('change', e => {
  nodes.update(DATA.nodes.map(n => ({...n, hidden: e.target.checked && n.isComm})));
});

document.getElementById('search').addEventListener('input', e => {
  const q = e.target.value.toLowerCase();
  if (!q) { nodes.update(DATA.nodes.map(n => ({...n, color:n.origColor}))); return; }
  nodes.update(DATA.nodes.map(n => ({...n,
    color: (n.label||'').toLowerCase().includes(q) || (n.title||'').toLowerCase().includes(q)
           ? {background:'#f85149', border:'#fff'} : '#30363d'})));
});

network.on('click', params => {
  const info = document.getElementById('info');
  if (!params.nodes.length) { info.style.display='none'; return; }
  const n = nodes.get(params.nodes[0]);
  info.innerHTML = '<b>'+n.label+'</b><br><i>'+(n.title||'')+'</i>';
  info.style.display = 'block';
});
</script>
</body>
</html>"""

_PLANE_STYLE = {
    #  plane            color      level  size
    "y_community":    ("#e3b341", 0, 14),
    "knowledge":      ("#39d2c0", 1, 9),
    "x_community":    ("#e3b341", 2, 14),
    "spine":          ("#bc8cff", 3, 12),
    "code":           ("#ffa657", 4, 9),
    "code_symbol":    ("#ff7b72", 5, 11),
    "code_community": ("#e3b341", 6, 14),
}

_EDGE_COLOR = {
    "follows": "#bc8cff", "grounds": "#39d2c0",
    "references": "#ffa657", "references_symbol": "#ff7b72",
    "member_of": "#e3b341", "calls": "#ff7b72", "quotes": "#ffa657",
}


def export_html(out_path: str = "context_graph_dg.html") -> dict:
    cg = ContextGraph()
    g = cg.g

    # god-nodes: most-cited sources, DG-style chokepoint highlighting
    cites = Counter(v for _u, v, d in g.edges(data=True)
                    if d.get("relation") in ("grounds", "references"))
    god = {n for n, _c in cites.most_common(4)}

    nodes = []
    for n, d in g.nodes(data=True):
        plane = d.get("plane", "knowledge")
        color, level, size = _PLANE_STYLE.get(plane, ("#8b949e", 1, 8))
        is_god = n in god
        if is_god:
            color, size = "#f85149", size + 6
        label = (d.get("question") or d.get("summary") or d.get("source") or n)[:34]
        title = f"[{plane}] " + (d.get("summary") or d.get("source") or "") \
                + (f" · kind={d.get('kind')}" if d.get("kind") else "") \
                + (f" · conf={d.get('confidence')}" if d.get("confidence") is not None else "") \
                + (f" · {d.get('extraction')}" if d.get("extraction") else "") \
                + (" · GOD-NODE (most cited)" if is_god else "")
        nodes.append({"id": n, "label": label, "title": title,
                      "color": color, "origColor": color,
                      "size": size, "level": level,
                      "isComm": "community" in plane})

    edges = []
    for u, v, d in g.edges(data=True):
        rel = d.get("relation", "")
        edges.append({"from": u, "to": v, "color": _EDGE_COLOR.get(rel, "#30363d"),
                      "label": rel if rel not in ("follows", "grounds") else "",
                      "width": 1.6 if rel in ("references_symbol", "calls") else 1.0})

    # DG's offline bundle if present (copied from Decision_Graph), else CDN
    bundle = Path(__file__).parent / "_vis_network.js"
    if bundle.exists() and bundle.stat().st_size > 100_000:
        vis_bundle = bundle.read_text(encoding="utf-8")
    else:
        vis_bundle = ('document.write(\'<script src="https://unpkg.com/'
                      'vis-network/standalone/umd/vis-network.min.js">'
                      '<\\/script>\')')

    title = "TruthGuard — 3-Plane Context Graph (DG visualizer)"
    summary = (f"{len(nodes)} nodes · {len(edges)} edges · "
               f"{sum(1 for n in nodes if n['isComm'])} communities · "
               f"{len(god)} god-nodes")
    html = (_HTML_TEMPLATE
            .replace("__TITLE__", title)
            .replace("__SUMMARY__", summary)
            .replace("__VIS_BUNDLE__", vis_bundle)
            .replace("__DATA__", json.dumps({"nodes": nodes, "edges": edges})))
    Path(out_path).write_text(html, encoding="utf-8")
    return {"path": out_path, "nodes": len(nodes), "edges": len(edges),
            "size_kb": round(len(html) / 1024, 1)}


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "context_graph_dg.html"
    print(export_html(out))
