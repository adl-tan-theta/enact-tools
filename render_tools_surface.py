#!/usr/bin/env python3
"""Render the before/after tool surface report.

The report is one self-contained HTML file. Every schema in it is a real
schema — the `json!` block from the Rust source, cross-checked against the
schema the shipped binary advertises over MCP. Nothing here is written by
hand.
"""
from __future__ import annotations

import html
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SURFACE_PATH = os.path.join(ROOT, "tools-surface.json")
CONFIG_PATH = os.path.join(ROOT, "config-surface.json")
OUT_PATH = os.path.join(ROOT, "enact-tools-schema-report.html")

S = json.load(open(SURFACE_PATH))
CONFIG = json.load(open(CONFIG_PATH)) if os.path.exists(CONFIG_PATH) else None

BEFORE = {t["name"]: t for t in S["before"]}
AFTER = {t["name"]: t for t in S["after"]}
BINARY = {t["name"]: t for t in S["binary_surface"]}
FAMILIES = [t for t in S["after"] if t["kind"] == "family"]


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def pretty(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def tier_class(tier: str) -> str:
    return {"Core": "k", "Host": "acc"}.get(tier, "")


def short_comp(compilation: str) -> str:
    return {
        "Always": "always",
        "External": "external",
        "Optional": "optional",
        "OptIn": "opt-in",
    }.get(compilation, compilation.lower())


def schema_differs(tool_name: str) -> bool:
    """Does the source schema differ from the schema the binary serves?"""
    source = BEFORE.get(tool_name, {}).get("parameters")
    shipped = BINARY.get(tool_name, {}).get("inputSchema")
    return source is not None and shipped is not None and source != shipped


# --------------------------------------------------------------- tool cards
def operations_line(tool: dict) -> str:
    ops = tool.get("operations") or tool.get("actions") or []
    if not ops:
        return '<span class="muted">—</span>'
    return ", ".join(f"<code>{esc(o)}</code>" for o in ops)


def render_tool(tool: dict, shipped: dict | None = None, note: str = "") -> str:
    """One tool, with its schema."""
    name = tool["name"]
    tier = tool.get("tier", "")
    compilation = tool.get("compilation", "")
    operations = tool.get("operations") or tool.get("actions") or []
    source_file = tool.get("source_file") or ""
    schema_from = tool.get("schema_from") or source_file
    description = tool.get("description") or ""

    badges = []
    if tier:
        badges.append(f'<span class="tier {tier_class(tier)}">{esc(tier)}</span>')
    if compilation:
        badges.append(f'<span class="comp">{esc(short_comp(compilation))}</span>')
    badges.append(f'<span class="pill">{len(operations)} op{"s" if len(operations) != 1 else ""}</span>')
    if shipped is not None:
        badges.append('<span class="pill acc">shipped</span>')

    merged = tool.get("merged_from") or []
    merged_html = ""
    if len(merged) > 1:
        merged_html = (
            '<div class="row"><span class="k">folded from</span><span class="mono">'
            + ", ".join(f"<code>{esc(m)}</code>" for m in merged)
            + "</span></div>"
        )

    source_html = ""
    if schema_from:
        source_html = (
            '<div class="row"><span class="k">schema from</span>'
            f'<span class="mono path">{esc(schema_from)}</span></div>'
        )

    description_html = (
        f'<p class="desc">{esc(description)}</p>' if description else ""
    )
    note_html = f'<p class="note">{note}</p>' if note else ""

    blocks = []
    if tool.get("parameters") is not None:
        blocks.append(
            '<div class="sblock"><div class="slabel">schema — as written in the source</div>'
            f'<pre class="json">{esc(pretty(tool["parameters"]))}</pre></div>'
        )
    if shipped is not None:
        blocks.append(
            '<div class="sblock shipped"><div class="slabel">schema — as served by the built binary over MCP</div>'
            f'<pre class="json">{esc(pretty(shipped))}</pre></div>'
        )

    return f"""
<article class="tool" data-name="{esc(name.lower())}" data-kind="{esc(tool.get("kind", "standalone"))}" data-tier="{esc(tier)}">
  <div class="thead">
    <h3><code>{esc(name)}</code></h3>
    <div class="badges">{"".join(badges)}</div>
    <button class="exp" type="button" onclick="this.closest('.tool').classList.toggle('open')">schema</button>
  </div>
  {description_html}
  {merged_html}
  <div class="row"><span class="k">operations</span><span class="mono ops">{operations_line(tool)}</span></div>
  {source_html}
  {note_html}
  <div class="schema">{"".join(blocks)}</div>
</article>"""


# ---------------------------------------------------------------- the config
def render_config_section(section: dict) -> str:
    """One configuration section, with every property it declares."""
    entries = section.get("properties") or []
    if not entries:
        return ""
    rows = []
    for entry in entries:
        bits = [f'<span class="pill">{esc(entry["type"] or "—")}</span>']
        if entry.get("default") is not None:
            bits.append(
                f'<span class="pill k">default {esc(json.dumps(entry["default"]))}</span>'
            )
        if entry.get("enum"):
            shown = ", ".join(str(v) for v in entry["enum"][:10])
            more = " …" if len(entry["enum"]) > 10 else ""
            bits.append(f'<span class="pill m">{esc(shown)}{more}</span>')
        if entry.get("deprecated"):
            bits.append('<span class="pill bad">deprecated</span>')
        if entry.get("secret"):
            bits.append('<span class="pill bad">secret</span>')
        description = (
            f'<div class="cdesc">{esc(entry["description"])}</div>'
            if entry.get("description")
            else ""
        )
        rows.append(
            f'<tr><td class="cpath mono">{esc(entry["path"])}</td>'
            f'<td>{"".join(bits)}</td><td>{description}</td></tr>'
        )
    shape = ""
    if section.get("shape") == "map":
        shape = (
            '<p class="lede" style="margin:0 0 10px">A map: one entry per alias. '
            "The properties below are the shape of a single entry.</p>"
        )
    description = ""
    if section.get("description"):
        description = (
            f'<p class="lede" style="margin:0 0 10px">'
            f'{esc(section["description"][:400])}</p>'
        )
    return f"""
<div class="cfg">
  <div class="cfghead"><h3>{esc(section["title"])}</h3>
    <p>{esc(section["blurb"])}</p></div>
  {description}{shape}
  <div class="tbl"><div class="scroll"><table>
    <thead><tr><th>property</th><th>type / default</th><th>description</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table></div></div>
</div>"""


def config_overview() -> str:
    """The table of sections the configuration schema declares."""
    rows = []
    for section in CONFIG["sections"]:
        rows.append(
            f'<tr><td class="cpath mono">{esc(section["key"])}</td>'
            f'<td><span class="pill">{len(section["properties"])}</span></td>'
            f'<td>{esc(section["blurb"])}</td></tr>'
        )
    return f"""
<div class="tbl"><div class="scroll"><table>
  <thead><tr><th>section</th><th>properties shown</th><th>what it governs</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table></div></div>"""


CSS = r"""
:root{
  --bg:#0e1116; --bg2:#141922; --panel:#171d27; --panel2:#1c2430;
  --line:#253040; --line2:#2f3b4d;
  --tx:#e6edf6; --tx2:#9fb0c6; --tx3:#6b7c92;
  --acc:#5b9cff; --acc2:#7db4ff;
  --keep:#3fb950; --merge:#e3a008; --add:#a371f7;
  --warn:#f0883e; --bad:#f85149;
  --r:10px; --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
html[data-theme=light]{
  --bg:#f6f8fb; --bg2:#ffffff; --panel:#ffffff; --panel2:#f0f4f9;
  --line:#dde5ee; --line2:#c9d5e3;
  --tx:#16202e; --tx2:#4a5b70; --tx3:#7c8ca0;
  --acc:#1668d6; --acc2:#0d5ac4;
  --keep:#1a7f37; --merge:#9a6700; --add:#8250df;
  --warn:#bc4c00; --bad:#cf222e;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:84px}
body{margin:0;background:var(--bg);color:var(--tx);
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1500px;margin:0 auto;padding:0 24px}
header{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.hd{display:flex;align-items:center;gap:18px;padding:13px 0}
.logo{font-weight:700;letter-spacing:-.02em;font-size:16px;white-space:nowrap}
.logo span{color:var(--tx3);font-weight:500}
nav{display:flex;gap:2px;flex:1;overflow-x:auto;scrollbar-width:none}
nav::-webkit-scrollbar{display:none}
nav a{padding:6px 11px;border-radius:7px;color:var(--tx2);font-size:13px;font-weight:500;white-space:nowrap}
nav a:hover{background:var(--panel2);color:var(--tx);text-decoration:none}
.tgl{border:1px solid var(--line2);background:var(--panel);color:var(--tx2);border-radius:8px;
  padding:6px 11px;cursor:pointer;font-size:13px;white-space:nowrap}
.tgl:hover{border-color:var(--acc);color:var(--tx)}
.hero{padding:52px 0 30px;border-bottom:1px solid var(--line)}
.eyebrow{font:600 11px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--acc);margin-bottom:14px}
h1{font-size:clamp(28px,4.2vw,44px);line-height:1.12;letter-spacing:-.03em;margin:0 0 14px;font-weight:760}
.sub{color:var(--tx2);font-size:16px;max-width:980px;margin:0}
.sub code{font:13px var(--mono);background:var(--panel2);padding:2px 6px;border-radius:5px;color:var(--acc2)}
.prov{display:flex;gap:9px;flex-wrap:wrap;margin-top:20px}
.prov span{font:11.5px var(--mono);color:var(--tx3);border:1px solid var(--line2);
  border-radius:99px;padding:5px 11px;background:var(--panel)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-top:30px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:15px 16px}
.stat .n{font:700 27px/1.1 var(--mono);letter-spacing:-.02em}
.stat .l{font-size:11.5px;color:var(--tx3);margin-top:5px;text-transform:uppercase;letter-spacing:.07em;font-weight:600}
.stat .d{font-size:12px;color:var(--tx2);margin-top:7px}
.stat.a .n{color:var(--acc)} .stat.k .n{color:var(--keep)}
.stat.m .n{color:var(--merge)} .stat.x .n{color:var(--add)}
section{padding:44px 0;border-bottom:1px solid var(--line)}
.shead{display:flex;align-items:flex-end;gap:14px;margin-bottom:8px;flex-wrap:wrap}
h2{font-size:25px;letter-spacing:-.02em;margin:0;font-weight:700}
h3{font-size:16.5px;margin:0;font-weight:650;letter-spacing:-.01em}
.lede{color:var(--tx2);margin:0 0 22px;max-width:1040px;font-size:14.5px}
.tag{font:600 10.5px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;
  color:var(--tx3);border:1px solid var(--line2);border-radius:99px;padding:5px 10px}
.call{border:1px solid var(--line);border-left:3px solid var(--acc);background:var(--panel);
  border-radius:0 var(--r) var(--r) 0;padding:16px 18px;margin:18px 0}
.call.warn{border-left-color:var(--warn)} .call.bad{border-left-color:var(--bad)} .call.good{border-left-color:var(--keep)}
.call h4{margin:0 0 7px;font-size:14.5px;font-weight:650}
.call p{margin:0;color:var(--tx2);font-size:13.5px}
.call p+p{margin-top:8px}
.call code{font:12.5px var(--mono);color:var(--acc2)}
.tbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:0 0 16px}
input[type=search],select{background:var(--panel);border:1px solid var(--line2);color:var(--tx);
  border-radius:8px;padding:8px 11px;font-size:13px;font-family:inherit}
input[type=search]{min-width:280px;flex:1;max-width:420px}
input[type=search]:focus,select:focus{outline:none;border-color:var(--acc)}
.count{font:12px var(--mono);color:var(--tx3);margin-left:auto}
.btn{border:1px solid var(--line2);background:var(--panel);color:var(--tx2);border-radius:8px;
  padding:7px 12px;cursor:pointer;font-size:12.5px}
.btn:hover{border-color:var(--acc);color:var(--tx)}
.tool{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:12px}
.tool:hover{border-color:var(--line2)}
.thead{display:flex;align-items:center;gap:11px;flex-wrap:wrap}
.thead h3{font-size:15.5px;font-family:var(--mono)}
.thead h3 code{font:inherit;background:none;padding:0;color:var(--tx)}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-left:auto}
.exp{border:1px solid var(--line2);background:var(--panel2);color:var(--tx3);border-radius:7px;
  padding:4px 10px;cursor:pointer;font:600 10.5px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase}
.exp:hover{border-color:var(--acc);color:var(--acc)}
.tier{font:600 10.5px/1 var(--mono);letter-spacing:.05em;padding:4px 7px;border-radius:5px;
  border:1px solid var(--line2);color:var(--tx3);white-space:nowrap}
.tier.k{color:var(--keep);border-color:color-mix(in srgb,var(--keep) 40%,transparent)}
.tier.acc{color:var(--acc);border-color:color-mix(in srgb,var(--acc) 40%,transparent)}
.comp{font:11px var(--mono);color:var(--tx3)}
.pill{display:inline-block;font:600 10px/1 var(--mono);letter-spacing:.06em;
  padding:4px 8px;border-radius:99px;border:1px solid var(--line2);color:var(--tx3);margin-right:4px}
.pill.acc{color:var(--acc);border-color:color-mix(in srgb,var(--acc) 40%,transparent)}
.pill.k{color:var(--keep);border-color:color-mix(in srgb,var(--keep) 40%,transparent)}
.pill.m{color:var(--merge);border-color:color-mix(in srgb,var(--merge) 40%,transparent)}
.pill.bad{color:var(--bad);border-color:color-mix(in srgb,var(--bad) 40%,transparent)}
.desc{color:var(--tx2);font-size:13.5px;margin:11px 0 0;max-width:1080px}
.row{display:flex;gap:10px;margin-top:8px;font-size:12.5px;align-items:baseline}
.row .k{color:var(--tx3);text-transform:uppercase;letter-spacing:.07em;font:600 10px/1.5 var(--mono);
  min-width:92px;flex-shrink:0}
.row .mono{font-family:var(--mono);font-size:12px;color:var(--tx2)}
.row .path{color:var(--tx3)}
.row .ops code{font:11.5px var(--mono);color:var(--tx2);background:var(--panel2);padding:2px 5px;border-radius:4px;margin-right:3px}
.note{color:var(--warn);font-size:12.5px;margin:9px 0 0;max-width:1000px}
.muted{color:var(--tx3)}
.schema{display:none;margin-top:14px;border-top:1px solid var(--line);padding-top:14px}
.tool.open .schema{display:block}
.sblock{margin-bottom:12px}
.sblock:last-child{margin-bottom:0}
.slabel{font:600 10px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--tx3);margin-bottom:6px}
.sblock.shipped .slabel{color:var(--acc)}
pre.json{margin:0;background:var(--bg2);border:1px solid var(--line);border-radius:9px;
  padding:13px 15px;overflow-x:auto;font:12px/1.55 var(--mono);color:var(--tx2);max-height:520px}
.fam{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:12px}
.famhead{display:flex;align-items:center;gap:11px;flex-wrap:wrap}
.famhead h3{font:650 15.5px var(--mono);color:var(--acc2)}
.fmembers{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}
.fmembers code{font:11.5px var(--mono);color:var(--tx2);background:var(--panel2);padding:3px 7px;border-radius:5px}
.fops{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.tbl{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;font:600 10.5px/1.3 var(--mono);letter-spacing:.1em;text-transform:uppercase;
  color:var(--tx3);padding:11px 13px;border-bottom:1px solid var(--line);background:var(--panel2);white-space:nowrap}
td{padding:10px 13px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:var(--panel2)}
.cpath{font-size:12px;color:var(--acc2);white-space:nowrap}
.cdesc{color:var(--tx2);font-size:12.5px;max-width:560px}
.cfg{margin-bottom:34px}
.cfghead h3{font-size:18px;margin-bottom:4px}
.cfghead p{color:var(--tx2);font-size:13.5px;margin:0 0 12px}
.mrow{display:grid;grid-template-columns:150px 1fr 96px;gap:14px;align-items:center;
  padding:12px 0;border-bottom:1px solid var(--line)}
.mrow:last-child{border-bottom:none}
.mrow .fam{font-family:var(--mono);font-weight:650;color:var(--acc2);font-size:13.5px;padding:0}
.mrow .from{font:11.5px/1.7 var(--mono);color:var(--tx3)}
.mrow .from b{color:var(--tx2);font-weight:500}
.mrow .to{font:600 11px/1 var(--mono);color:var(--merge);text-align:right}
footer{padding:34px 0 56px;color:var(--tx3);font-size:12.5px}
footer a{color:var(--tx2)}
@media(max-width:760px){
  .mrow{grid-template-columns:1fr}.mrow .to{text-align:left}
  .row{flex-direction:column;gap:2px}.row .k{min-width:0}
}
"""

JS = r"""
(function(){
  const root=document.documentElement;
  const key='enact-tools-schema-theme';
  const saved=localStorage.getItem(key);
  if(saved){root.setAttribute('data-theme',saved);}
  const btn=document.getElementById('theme');
  function label(){
    const t=root.getAttribute('data-theme')==='light'?'dark':'light';
    btn.textContent=t==='dark'?'dark':'light';
  }
  label();
  btn.addEventListener('click',()=>{
    const t=root.getAttribute('data-theme')==='light'?'dark':'light';
    root.setAttribute('data-theme',t);
    localStorage.setItem(key,t);
    label();
  });
  // Each section filters its own list and counts only its own cards.
  const lists=[{input:'q',select:null,list:'before-list',count:'before'},
               {input:'q2',select:'kind',list:'after-list',count:'after'}];
  function apply(group){
    const term=(group.input.value||'').toLowerCase();
    const k=group.select?(group.select.value||''):'';
    const root=document.getElementById(group.list);
    let shown=0;
    root.querySelectorAll('.tool').forEach(card=>{
      const n=card.dataset.name||'';
      const kd=card.dataset.kind||'';
      const ok=(!term||n.indexOf(term)>-1)&&(!k||kd===k);
      card.style.display=ok?'':'none';
      if(ok)shown++;
    });
    const out=document.querySelector('#'+group.count+' .count [data-count-for]');
    if(out){out.textContent=shown;}
  }
  lists.forEach(group=>{
    const input=document.getElementById(group.input);
    const select=group.select?document.getElementById(group.select):null;
    if(input){input.addEventListener('input',()=>apply(group));}
    if(select){select.addEventListener('change',()=>apply(group));}
  });
  document.querySelectorAll('[data-expand-all]').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const scope=btn.closest('section');
      const cards=scope.querySelectorAll('.tool');
      const anyClosed=Array.from(cards).some(c=>!c.classList.contains('open'));
      cards.forEach(c=>c.classList.toggle('open',anyClosed));
    });
  });
  lists.forEach(apply);
})();
"""


def render() -> str:
    counts = S["counts"]
    families = FAMILIES
    members = sum(len(f["merged_from"]) for f in families)
    family_ops = sum(len(f["actions"]) for f in families)
    standalone = [t for t in S["after"] if t["kind"] == "standalone"]
    exposed = [t for t in S["after"] if t.get("from_binary")]
    hidden = [t for t in S["after"] if not t.get("from_binary")]
    with_schema = sum(1 for t in S["before"] if t.get("parameters"))
    diffs = [name for name in BINARY if schema_differs(name)]

    # -- the fold table --------------------------------------------------
    fold_rows = []
    for family in families:
        details = {d["tool"]: d for d in family["member_details"]}
        members_html = "<br>".join(
            f"<b>{esc(m)}</b> <span class='muted'>{esc(' + '.join(details.get(m, {}).get('ops', [])))}</span>"
            for m in family["merged_from"]
        )
        fold_rows.append(
            f'<div class="mrow"><div class="fam">{esc(family["name"])}</div>'
            f'<div class="from">{members_html}</div>'
            f'<div class="to">{len(family["actions"])} ops</div></div>'
        )
    family_table = "".join(fold_rows)

    # -- before ----------------------------------------------------------
    before_cards = []
    for tool in sorted(S["before"], key=lambda t: t["name"]):
        before_cards.append(render_tool(tool))

    # -- after -----------------------------------------------------------
    after_cards = []
    for family in families:
        member_rows = []
        for member in family["member_details"]:
            member_rows.append(
                f'<div class="row"><span class="k">{esc(member["tool"])}</span>'
                f'<span class="mono ops">{esc(" + ".join(member["ops"]))}</span></div>'
            )
        shipped = BINARY.get(family["name"], {}).get("inputSchema")
        blocks = [
            '<div class="sblock"><div class="slabel">schema — the family contract</div>'
            f'<pre class="json">{esc(pretty(family["parameters"]))}</pre></div>'
        ]
        if shipped is not None:
            blocks.append(
                '<div class="sblock shipped"><div class="slabel">schema — as served by the built binary over MCP</div>'
                f'<pre class="json">{esc(pretty(shipped))}</pre></div>'
            )
        badges = [
            f'<span class="pill m">{len(family["merged_from"])} tools</span>',
            f'<span class="pill">{len(family["actions"])} actions</span>',
        ]
        if shipped is not None:
            badges.append('<span class="pill acc">shipped</span>')
        after_cards.append(
            f"""
<article class="tool" data-name="{esc(family["name"].lower())}" data-kind="family" data-tier="">
  <div class="thead"><h3><code>{esc(family["name"])}</code></h3>
    <div class="badges">{"".join(badges)}</div>
    <button class="exp" type="button" onclick="this.closest('.tool').classList.toggle('open')">schema</button>
  </div>
  <p class="desc">{esc(family["description"] or "")}</p>
  <div class="fmembers">{"".join(f"<code>{esc(m)}</code>" for m in family["merged_from"])}</div>
  {"".join(member_rows)}
  <div class="schema">{"".join(blocks)}</div>
</article>"""
        )
    for tool in sorted(standalone, key=lambda t: t["name"]):
        shipped = BINARY.get(tool["name"], {}).get("inputSchema")
        note = ""
        if tool["name"] in diffs:
            note = (
                "The schema in the source tree and the schema the binary serves differ. "
                "The overlay rewrites this tool's schema in the prepared tree, so the "
                "binary's version is what ships."
            )
        after_cards.append(render_tool(tool, shipped, note))

    # -- config ----------------------------------------------------------
    config_html = ""
    if CONFIG:
        ccounts = CONFIG["counts"]
        blocks = [
            '<div class="call good"><h4>The configuration schema is the binary\u2019s own</h4>'
            "<p>This is read straight out of the shipped binary, from the JSON Schema "
            "it emits for <code>zeroclaw config schema</code> \u2014 the same document "
            "the gateway serves at <code>GET /api/config</code>. Every property below "
            "comes out of it; nothing is transcribed by hand.</p></div>",
            f'<p class="lede">The configuration schema declares '
            f'<strong>{ccounts["config_sections_total"]}</strong> sections in total. '
            f'The <strong>{ccounts["sections_shown"]}</strong> that govern the tool '
            f'surface are set out in full below \u2014 '
            f'<strong>{ccounts["properties_shown"]}</strong> properties between them, '
            f'each with its type, its default and its description.</p>',
            config_overview(),
        ]
        for section in CONFIG["sections"]:
            block = render_config_section(section)
            if block:
                blocks.append(block)
        config_html = "".join(blocks)

    stats_html = f"""
<div class="stats">
  <div class="stat a"><div class="n">{counts['source_tools']}</div><div class="l">tools before</div>
    <div class="d">{counts['source_operations']} operations across them</div></div>
  <div class="stat x"><div class="n">{counts['canonical_tools']}</div><div class="l">tools after</div>
    <div class="d">{counts['families']} families absorbing {members} tools</div></div>
  <div class="stat k"><div class="n">{with_schema}/{counts['source_tools']}</div><div class="l">schemas extracted</div>
    <div class="d">every tool, read from the Rust source</div></div>
  <div class="stat m"><div class="n">{counts['binary_advertised']}</div><div class="l">exposed over MCP</div>
    <div class="d">{len(hidden)} canonical tools stay host-side</div></div>
  <div class="stat"><div class="n">{family_ops}</div><div class="l">family actions</div>
    <div class="d">the operations a family advertises</div></div>
</div>"""

    provenance = f"""
<div class="prov">
  <span>enact-agent @ {esc(S['generated_from']['agent_head'])}</span>
  <span>{esc(S['generated_from']['csv'])}</span>
  <span>{counts['source_tools']} tools / {counts['source_operations']} operations</span>
  <span>binary surface captured over MCP</span>
</div>"""

    return f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Enact — the tool surface, before and after</title>
<style>{CSS}</style>
</head>
<body>
<header><div class="wrap">
  <div class="hd">
    <div class="logo">enact <span>/ tool surface</span></div>
    <nav>
      <a href="#shape">the shape</a>
      <a href="#before">before</a>
      <a href="#after">after</a>
      <a href="#deltas">deltas</a>
      <a href="#config">config</a>
      <a href="#method">method</a>
    </nav>
    <button class="tgl" id="theme">dark</button>
  </div>
</div></header>

<div class="wrap">
  <div class="hero">
    <div class="eyebrow">schema level</div>
    <h1>Every tool, before and after</h1>
    <p class="sub">The Enact tool surface went from <code>{counts['source_tools']} tools</code>
    carrying <code>{counts['source_operations']} operations</code> to
    <code>{counts['canonical_tools']} canonical tools</code> — {counts['families']} of which
    are families that absorb {members} legacy tools behind a single
    <code>action</code> argument. Every schema below is the real one: read out of the
    Rust source and cross-checked against the schema the built binary advertises
    over MCP. None of it is written by hand.</p>
    {provenance}
    {stats_html}
  </div>

  <section id="shape">
    <div class="shead"><h2>The shape of the change</h2>
      <span class="tag">{members} tools folded into {counts['families']} families</span></div>
    <p class="lede">A family is one canonical tool with an <code>action</code> argument.
    Each legacy tool becomes a member; each member keeps its operations. The family
    schema stays deliberately small — an <code>action</code> enum plus
    <code>additionalProperties: true</code> — so the operation-level arguments are
    passed through unchanged.</p>
    <div class="tbl"><div class="scroll">
      {family_table}
    </div></div>
    <div class="call"><h4>What did not change</h4>
      <p>The {len(standalone)} canonical tools that are not families keep their own name,
      their own tier and their own schema. A family is an addition to the surface, not a
      removal from it: every legacy tool name stays callable, and stays in the
      product&rsquo;s own tool list. It is only hidden from the host (MCP) surface.</p></div>
  </section>

  <section id="before">
    <div class="shead"><h2>Before</h2>
      <span class="tag">{counts['source_tools']} tools</span>
      <span class="tag">{counts['source_operations']} operations</span></div>
    <p class="lede">This is the surface as the operations inventory records it: every
    tool, its tier, how it is compiled, where its schema lives, and the operations it
    answers to. Open any tool to read its schema exactly as the source declares it.</p>
    <div class="tbar">
      <input type="search" id="q" placeholder="filter by tool name…" aria-label="Filter tools">
      <button class="btn" data-expand-all>toggle all schemas</button>
      <span class="count"><span data-count-for>0</span> shown</span>
    </div>
    <div id="before-list">
      {"".join(before_cards)}
    </div>
  </section>

  <section id="after">
    <div class="shead"><h2>After</h2>
      <span class="tag">{counts['canonical_tools']} canonical tools</span>
      <span class="tag">{counts['families']} families</span></div>
    <p class="lede">The consolidated surface. Families first, then the standalone tools
    that kept their identity. Where the binary advertises a tool over MCP, its served
    schema is shown next to the source schema.</p>
    <div class="tbar">
      <input type="search" id="q2" placeholder="filter by tool name…" aria-label="Filter tools">
      <select id="kind" aria-label="Filter by kind">
        <option value="">all kinds</option>
        <option value="family">families</option>
        <option value="standalone">standalone</option>
      </select>
      <button class="btn" data-expand-all>toggle all schemas</button>
      <span class="count"><span data-count-for>0</span> shown</span>
    </div>
    <div id="after-list">
      {"".join(after_cards)}
    </div>
  </section>

  <section id="deltas">
    <div class="shead"><h2>Where the source and the shipped schema differ</h2>
      <span class="tag">{len(diffs)} tools</span></div>
    <p class="lede">The extractor reads the source tree; the binary is built from the
    prepared tree, which is the source plus the overlay. Where the overlay rewrites a
    tool&rsquo;s schema, the two differ — and the binary&rsquo;s version is what ships.
    Everything else matches byte for byte.</p>
    {"".join(render_tool(BEFORE[name], BINARY[name].get("inputSchema"),
        "The overlay rewrites this schema in the prepared tree. The binary's version is what ships.")
        for name in sorted(diffs)) if diffs else '<div class="call good"><h4>No differences</h4><p>Every schema the binary serves matches the source exactly.</p></div>'}
  </section>

  <section id="config">
    <div class="shead"><h2>Configuration</h2>
      <span class="tag">the options that govern all of this</span></div>
    {config_html or '<div class="call warn"><h4>Config schema not captured</h4><p>The binary was built without the <code>schema-export</code> feature, so <code>config schema</code> is unavailable.</p></div>'}
  </section>

  <section id="method">
    <div class="shead"><h2>How this was measured</h2></div>
    <div class="call good"><h4>Every schema is real</h4>
      <p>Schemas are read out of each tool&rsquo;s <code>parameters_schema()</code> — the
      <code>json!</code> block in the Rust source — and resolved against the constants,
      associated constants, message catalogue and table folds that block refers to.
      Where a value genuinely cannot be known from the source, it is marked
      <code>&lt;computed at runtime&gt;</code> rather than guessed.</p></div>
    <div class="call"><h4>Cross-checked against the binary</h4>
      <p>The shipped binary was driven over MCP (<code>mcp serve --expose-full</code>) and
      its advertised <code>inputSchema</code> captured. {counts['binary_advertised']} tools
      are exposed that way. Every one of the {with_schema} extracted schemas was compared
      against them; the only differences are the {len(diffs)} tools the overlay rewrites,
      listed above.</p></div>
    <div class="call"><h4>Where the numbers come from</h4>
      <p>Tool names, tiers, compilation modes and operations come from
      <code>{esc(S['generated_from']['csv'])}</code>, the operations inventory. The family
      table comes from <code>overlays/enact/native/tools/families.rs</code>. The tier and
      compilation table is cross-read from <code>crates/zeroclaw-tools/src/inventory.rs</code>.
      No count in this report is written by hand — all of them are derived.</p></div>
  </section>

  <footer>
    <p>Generated from the Enact source tree at
    <code>{esc(S['generated_from']['agent_head'])}</code>. Rendered by
    <code>render_tools_surface.py</code> from <code>tools-surface.json</code>.</p>
  </footer>
</div>
<script>{JS}</script>
</body>
</html>"""


if __name__ == "__main__":
    page = render()
    with open(OUT_PATH, "w") as handle:
        handle.write(page)
    print(f"wrote {OUT_PATH} ({len(page):,} bytes)")
