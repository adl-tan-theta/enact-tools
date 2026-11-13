#!/usr/bin/env python3
"""Render the enact-tools comparison report to a single self-contained HTML file."""
import json, os, html

ROOT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(ROOT, "data.json")))
S = D["stats"]

CSS = r"""
:root{
  --bg:#0e1116; --bg2:#141922; --panel:#171d27; --panel2:#1c2430;
  --line:#253040; --line2:#2f3b4d;
  --tx:#e6edf6; --tx2:#9fb0c6; --tx3:#6b7c92;
  --acc:#5b9cff; --acc2:#7db4ff;
  --keep:#3fb950; --enhance:#3b82f6; --merge:#e3a008; --add:#a371f7;
  --ext:#8b98a9; --disable:#6e7b8d; --warn:#f0883e; --bad:#f85149;
  --c-add:#a371f7; --c-merge:#e3a008; --c-keep:#3fb950;
  --c-enhance:#3b82f6; --c-ext:#8b98a9; --c-disable:#6e7b8d;
  --r:10px; --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
html[data-theme=light]{
  --bg:#f6f8fb; --bg2:#ffffff; --panel:#ffffff; --panel2:#f0f4f9;
  --line:#dde5ee; --line2:#c9d5e3;
  --tx:#16202e; --tx2:#4a5b70; --tx3:#7c8ca0;
  --acc:#1668d6; --acc2:#0d5ac4;
  --keep:#1a7f37; --enhance:#0969da; --merge:#9a6700; --add:#8250df;
  --ext:#6e7b8d; --disable:#8c959f; --warn:#bc4c00; --bad:#cf222e;
  --c-add:#8250df; --c-merge:#9a6700; --c-keep:#1a7f37;
  --c-enhance:#0969da; --c-ext:#6e7b8d; --c-disable:#8c959f;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth; scroll-padding-top:86px}
body{margin:0;background:var(--bg);color:var(--tx);
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1400px;margin:0 auto;padding:0 24px}

/* ---- header ---- */
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

/* ---- hero ---- */
.hero{padding:52px 0 30px;border-bottom:1px solid var(--line)}
.eyebrow{font:600 11px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--acc);margin-bottom:14px}
h1{font-size:clamp(28px,4.2vw,44px);line-height:1.12;letter-spacing:-.03em;margin:0 0 14px;font-weight:760}
.sub{color:var(--tx2);font-size:16px;max-width:900px;margin:0}
.sub code{font:13px var(--mono);background:var(--panel2);padding:2px 6px;border-radius:5px;color:var(--acc2)}

/* ---- stats ---- */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-top:30px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:15px 16px}
.stat .n{font:700 27px/1.1 var(--mono);letter-spacing:-.02em}
.stat .l{font-size:11.5px;color:var(--tx3);margin-top:5px;text-transform:uppercase;letter-spacing:.07em;font-weight:600}
.stat .d{font-size:12px;color:var(--tx2);margin-top:7px}
.stat.a .n{color:var(--acc)} .stat.k .n{color:var(--keep)}
.stat.m .n{color:var(--merge)} .stat.x .n{color:var(--add)} .stat.d .n{color:var(--disable)}

/* ---- sections ---- */
section{padding:44px 0;border-bottom:1px solid var(--line)}
.shead{display:flex;align-items:flex-end;gap:14px;margin-bottom:8px;flex-wrap:wrap}
h2{font-size:25px;letter-spacing:-.02em;margin:0;font-weight:700}
h3{font-size:16.5px;margin:26px 0 11px;font-weight:650;letter-spacing:-.01em}
.lede{color:var(--tx2);margin:0 0 22px;max-width:1000px;font-size:14.5px}
.tag{font:600 10.5px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;
  color:var(--tx3);border:1px solid var(--line2);border-radius:99px;padding:5px 10px}

/* ---- cards ---- */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px}
.card.hi{border-color:color-mix(in srgb,var(--acc) 45%,var(--line))}
.card h4{margin:0 0 4px;font-size:16px;letter-spacing:-.01em;display:flex;align-items:center;gap:8px}
.card .who{font:11px var(--mono);color:var(--tx3);margin-bottom:14px}
.card ul{margin:0;padding-left:18px;color:var(--tx2);font-size:13.5px}
.card li{margin-bottom:6px}
.card li b{color:var(--tx);font-weight:620}
.pill{display:inline-block;font:600 10px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;
  padding:4px 8px;border-radius:99px;border:1px solid var(--line2);color:var(--tx3)}
.pill.acc{color:var(--acc);border-color:color-mix(in srgb,var(--acc) 40%,transparent)}
.pill.k{color:var(--keep);border-color:color-mix(in srgb,var(--keep) 40%,transparent)}
.pill.m{color:var(--merge);border-color:color-mix(in srgb,var(--merge) 40%,transparent)}
.pill.x{color:var(--add);border-color:color-mix(in srgb,var(--add) 40%,transparent)}
.pill.d{color:var(--disable);border-color:color-mix(in srgb,var(--disable) 40%,transparent)}

/* ---- callout ---- */
.call{border:1px solid var(--line);border-left:3px solid var(--acc);background:var(--panel);
  border-radius:0 var(--r) var(--r) 0;padding:16px 18px;margin:18px 0}
.call.warn{border-left-color:var(--warn)} .call.bad{border-left-color:var(--bad)} .call.good{border-left-color:var(--keep)}
.call h4{margin:0 0 7px;font-size:14.5px;font-weight:650}
.call p{margin:0;color:var(--tx2);font-size:13.5px}
.call p+p{margin-top:8px}

/* ---- table ---- */
.tbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:0 0 14px}
input[type=search],select{background:var(--panel);border:1px solid var(--line2);color:var(--tx);
  border-radius:8px;padding:8px 11px;font-size:13px;font-family:inherit}
input[type=search]{min-width:280px;flex:1;max-width:420px}
input[type=search]:focus,select:focus{outline:none;border-color:var(--acc)}
.count{font:12px var(--mono);color:var(--tx3);margin-left:auto}
.tbl{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;font:600 10.5px/1.3 var(--mono);letter-spacing:.1em;text-transform:uppercase;
  color:var(--tx3);padding:11px 13px;border-bottom:1px solid var(--line);background:var(--panel2);
  position:sticky;top:0;white-space:nowrap;z-index:2}
td{padding:10px 13px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:var(--panel2)}
code,td .mono{font-family:var(--mono);font-size:12.3px}
.tname{font-family:var(--mono);font-size:12.6px;font-weight:600;color:var(--tx);white-space:nowrap}
.ops{color:var(--tx3);font-size:11.5px;max-width:390px;line-height:1.5}
.ops b{color:var(--tx2);font-weight:500}
.v{font:700 10px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:4px 7px;
  border-radius:5px;white-space:nowrap;display:inline-block}
.v-KEEP{color:var(--keep);background:color-mix(in srgb,var(--keep) 15%,transparent)}
.v-ENHANCE{color:var(--enhance);background:color-mix(in srgb,var(--enhance) 15%,transparent)}
.v-MERGE{color:var(--merge);background:color-mix(in srgb,var(--merge) 16%,transparent)}
.v-ADD{color:var(--add);background:color-mix(in srgb,var(--add) 16%,transparent)}
.v-EXT{color:var(--ext);background:color-mix(in srgb,var(--ext) 16%,transparent)}
.v-DISABLE{color:var(--disable);background:color-mix(in srgb,var(--disable) 16%,transparent)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}
.dot.y{background:var(--keep);box-shadow:0 0 7px color-mix(in srgb,var(--keep) 55%,transparent)}
.dot.p{background:var(--acc);box-shadow:0 0 7px color-mix(in srgb,var(--acc) 55%,transparent)}
.dot.n{background:var(--line2)}
.dot.x{background:var(--disable)}
.tier{font:600 10.5px/1 var(--mono);letter-spacing:.05em;padding:4px 7px;border-radius:5px;
  border:1px solid var(--line2);color:var(--tx3);white-space:nowrap}
.tier.Core{color:var(--keep);border-color:color-mix(in srgb,var(--keep) 40%,transparent)}
.tier.Host{color:var(--acc);border-color:color-mix(in srgb,var(--acc) 40%,transparent)}
.tier.Optional{color:var(--tx3)}
.comp{font-size:11.5px;color:var(--tx3);font-family:var(--mono)}
.off{color:var(--disable)}
.note{color:var(--tx2);font-size:12.6px;max-width:460px}

/* ---- bars ---- */
.bars{display:flex;flex-direction:column;gap:9px;margin:16px 0}
.bar{display:grid;grid-template-columns:150px 1fr 52px;align-items:center;gap:12px;font-size:13px}
.bar .t{color:var(--tx2)}
.bar .r{height:9px;background:var(--panel2);border-radius:99px;overflow:hidden}
.bar .f{height:100%;border-radius:99px;min-width:6px}
.bar .q{font:600 12px var(--mono);color:var(--tx3);text-align:right}

/* ---- merge ---- */
.mrow{display:grid;grid-template-columns:130px 1fr 92px;gap:14px;align-items:center;
  padding:12px 0;border-bottom:1px solid var(--line)}
.mrow:last-child{border-bottom:none}
.mrow .fam{font-family:var(--mono);font-weight:650;color:var(--acc2);font-size:13.5px}
.mrow .from{font:11.5px/1.7 var(--mono);color:var(--tx3)}
.mrow .from b{color:var(--tx2);font-weight:500}
.mrow .to{font:600 11px/1 var(--mono);color:var(--merge);text-align:right}

/* ---- roadmap ---- */
.rm{display:grid;gap:14px}
.phase{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px}
.phase h4{margin:0 0 4px;font-size:16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.phase .meta{font:11px var(--mono);color:var(--tx3);margin-bottom:14px}
.phase ul{margin:0;padding-left:19px;color:var(--tx2);font-size:13.5px}
.phase li{margin-bottom:8px}
.phase li b{color:var(--tx)}
.gantt{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:6px}
footer{padding:34px 0 56px;color:var(--tx3);font-size:12.5px}
footer a{color:var(--tx2)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
@media(max-width:760px){
  .gantt{grid-template-columns:1fr}.bar{grid-template-columns:110px 1fr 44px}
  .mrow{grid-template-columns:1fr}.mrow .to{text-align:left}
}
"""

JS = r"""
const S=__STATS__, V=__VERDICTS__, TOOLS=__TOOLS__, NEW=__NEW__, HOOKS=__HOOKS__;
const HOSTS=__HOSTS__, PORT=__PORT__, JTOOLS=__JTOOLS__, JFACTS=__JFACTS__;
const JHOOKS=__JHOOKS__;

const tierColor=t=>t==='Core'?'var(--keep)':t==='Host'?'var(--acc)':'var(--tx3)';
const compShort=c=>c==='Always'?'always':c==='External'?'external':(c.startsWith('OptIn')?'opt-in':'—');

function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}

function renderTools(){
  const q=(document.getElementById('q').value||'').toLowerCase();
  const fv=document.getElementById('fv').value;
  const ft=document.getElementById('ft').value;
  const fs=document.getElementById('fs').value;
  let rows=TOOLS.map(t=>{
    const v=V[t.name]||['KEEP','','',''];
    return {...t,v};
  }).filter(t=>{
    if(fv&&t.v[0]!==fv)return false;
    if(ft&&t.tier!==ft)return false;
    if(fs==='on'&&t.disabled)return false;
    if(fs==='off'&&!t.disabled)return false;
    if(q){
      const hay=(t.name+' '+t.ops.join(' ')+' '+t.v[1]+' '+t.v[2]+' '+t.v[3]+' '+t.tier).toLowerCase();
      if(!hay.includes(q))return false;
    }
    return true;
  });
  const tb=document.getElementById('tbody');
  tb.innerHTML=rows.map(t=>{
    const omp=t.v[1],lcx=t.v[2];
    const dot=v=>v&&v!=='-'&&v!==''?'<span class="dot y"></span>':'<span class="dot n"></span>';
    return `<tr>
      <td><div class="tname">${esc(t.name)}</div>
          <div class="comp">${compShort(t.compilation)}${t.disabled?' · <span class="off">off</span>':''}</div></td>
      <td><div class="ops"><b>${t.ops.length}</b> · ${t.ops.map(o=>esc(o)).join(', ')}</div></td>
      <td><span class="tier ${t.tier}">${t.tier}</span></td>
      <td><span class="v v-${t.v[0]}">${t.v[0]}</span></td>
      <td>${dot(omp)}<span style="font-size:11.5px;color:var(--tx3)">${omp&&omp!=='-'?esc(omp):'—'}</span></td>
      <td>${dot(lcx)}<span style="font-size:11.5px;color:var(--tx3)">${lcx&&lcx!=='-'?esc(lcx):'—'}</span></td>
      <td><div class="note">${esc(t.v[3])}</div></td>
    </tr>`;
  }).join('');
  document.getElementById('cnt').textContent=rows.length+' of '+TOOLS.length+' tools';
}
function renderNew(){
  const q=(document.getElementById('nq').value||'').toLowerCase();
  const fp=document.getElementById('nfp').value;
  let rows=NEW.filter(n=>{
    if(fp&&n[3]!==fp)return false;
    if(q){const hay=(n.join(' ')).toLowerCase();if(!hay.includes(q))return false;}
    return true;
  });
  document.getElementById('ntbody').innerHTML=rows.map(n=>{
    const pc=n[3]==='P0'?'var(--bad)':n[3]==='P1'?'var(--warn)':n[3]==='P2'?'var(--acc)':'var(--tx3)';
    return `<tr>
      <td><div class="tname">${esc(n[0])}</div></td>
      <td><div class="note" style="color:var(--tx)">${esc(n[1])}</div></td>
      <td><div class="comp">${esc(n[2])}</div></td>
      <td><span class="tier" style="color:${pc};border-color:${pc}55">${n[3]}</span></td>
      <td><span class="comp">${esc(n[4])}</span></td>
      <td><div class="note">${esc(n[5])}</div></td>
    </tr>`;
  }).join('');
  document.getElementById('ncnt').textContent=rows.length+' of '+NEW.length+' proposals';
}
function renderHooks(){
  const q=(document.getElementById('hq').value||'').toLowerCase();
  const rows=HOOKS.filter(h=>!q||h.join(' ').toLowerCase().includes(q));
  document.getElementById('htbody').innerHTML=rows.map(h=>{
    const rec=h[4];
    const rc=rec==='ok'?'var(--keep)':rec==='ADD'?'var(--enhance)':rec==='KEEP'?'var(--tx3)':'var(--bad)';
    const lab=rec==='ok'?'parity':rec==='ADD'?'ADD':rec==='KEEP'?'KEEP':'BLOCKER';
    const cls=rec==='ok'?'KEEP':rec;
    return `<tr>
      <td><div class="note" style="color:var(--tx);font-weight:600">${esc(h[0])}</div></td>
      <td><div class="comp">${esc(h[1])}</div></td>
      <td><div class="comp">${esc(h[2])}</div></td>
      <td><div class="comp">${esc(h[3])}</div></td>
      <td><span class="v v-${cls}" style="color:${rc}">${lab}</span></td>
    </tr>`;
  }).join('');
  document.getElementById('hcnt').textContent=rows.length+' of '+HOOKS.length+' capabilities';
}
['q','fv','ft','fs'].forEach(id=>document.getElementById(id).addEventListener('input',renderTools));
['nq','nfp'].forEach(id=>document.getElementById(id).addEventListener('input',renderNew));
document.getElementById('hq').addEventListener('input',renderHooks);
renderTools();renderNew();renderHooks();

function renderHosts(){
  const q=(document.getElementById('pq')||{}).value;
  const qy=(q||'').toLowerCase();
  const rows=HOSTS.filter(h=>!qy||h.join(' ').toLowerCase().includes(qy));
  document.getElementById('ptbody').innerHTML=rows.map(h=>{
    const v=h[9];
    const col=v==='GAP'?'var(--bad)':v==='REFERENCE'?'var(--acc)':'var(--keep)';
    const yn=b=>b&&b.toLowerCase()!=='no'&&b.toLowerCase()!=='n/a'
        ? '<span class="dot y"></span>' : '<span class="dot n"></span>';
    const warn=b=>b&&b.toLowerCase().startsWith('no')?'style="color:var(--bad)"':'';
    return `<tr>
      <td><div class="tname">${esc(h[0])}</div><div class="comp">${esc(h[1])} · ${esc(h[2])}</div></td>
      <td>${yn(h[3])}<span style="font-size:11.5px;color:var(--tx3)">${esc(h[3])}</span></td>
      <td ${warn(h[4])}>${yn(h[4])}<span style="font-size:11.5px;color:var(--tx3)">${esc(h[4])}</span></td>
      <td><div class="comp">${esc(h[5])}</div></td>
      <td><div class="comp">${esc(h[6])}</div></td>
      <td><div class="note">${esc(h[7])}</div></td>
      <td><div class="note">${esc(h[8])}</div></td>
      <td><span class="v v-${v==='GAP'?'DISABLE':v==='REFERENCE'?'ENHANCE':'KEEP'}" style="color:${col}">${v}</span></td>
      <td><div class="note">${esc(h[10])}</div></td>
    </tr>`;
  }).join('');
  document.getElementById('pcnt').textContent=rows.length+' of '+HOSTS.length+' systems';
}
renderHosts();
if(document.getElementById('pq'))document.getElementById('pq').addEventListener('input',renderHosts);

function renderJTools(){
  const q=(document.getElementById('jq')||{}).value||'';
  const qy=q.toLowerCase();
  const rows=JTOOLS.filter(t=>!qy||t.join(' ').toLowerCase().includes(qy));
  document.getElementById('jtbody').innerHTML=rows.map(t=>
    `<tr><td><div class="tname">${esc(t[0])}</div></td><td><div class="note" style="color:var(--tx)">${esc(t[1])}</div></td></tr>`).join('');
  document.getElementById('jcnt').textContent=rows.length+' of '+JTOOLS.length+' tools';
}
renderJTools();
if(document.getElementById('jq'))document.getElementById('jq').addEventListener('input',renderJTools);

function renderJHooks(){
  document.getElementById('jhbody').innerHTML=JHOOKS.map(h=>
    `<tr><td><div class="tname" style="font-size:12.5px">${esc(h[0])}</div></td>
        <td><div class="comp">${esc(h[1])}</div></td>
        <td><div class="note" style="color:var(--tx)">${esc(h[2])}</div></td></tr>`).join('');
}
renderJHooks();

const th=document.getElementById('theme');
function setTheme(t){document.documentElement.setAttribute('data-theme',t);localStorage.setItem('report-theme',t);
  th.textContent=t==='dark'?'Light mode':'Dark mode';}
th.addEventListener('click',()=>setTheme(document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark'));
setTheme(localStorage.getItem('report-theme')||'dark');
"""


def build():
    stats = D["stats"]
    v = stats["verdict_counts"]
    vtotal = sum(v.values())
    vrow = "".join(
        f'<div class="bar"><div class="t">{k}</div><div class="r"><div class="f" style="width:{max(v[k]/vtotal*100,1.2):.1f}%;background:var(--c-{k.lower()})"></div></div><div class="q">{v[k]}</div></div>'
        for k in ["ADD", "MERGE", "KEEP", "ENHANCE", "EXT", "DISABLE"]
    )

    merge_rows = "".join(
        f"""<div class="mrow"><div class="fam">{html.escape(fam)}</div>
        <div class="from">{' · '.join('<b>'+html.escape(t)+'</b>' for t in tools_)}</div>
        <div class="to">{n} → 1</div></div>"""
        for fam, tools_, n, ops in D["merges"]
    )

    def md(text):
        """Minimal inline markdown: `code` -> <code>code</code>, with escaping."""
        out = html.escape(text)
        out = out.replace("`", "<code>").replace("`", "</code>")
        out = out.replace("&lt;", "&lt;")
        return out.replace("&amp;lt;", "&amp;lt;")

    port_cards = "".join(
        f"""<div class="card">
      <h4>{html.escape(p[0])}</h4>
      <div class="who">{md(p[1])}</div>
      <p style="color:var(--tx2);font-size:13px;margin:0 0 10px">{md(p[2])}</p>
      <p style="color:var(--acc2);font-size:12.5px;margin:0;padding-top:10px;border-top:1px solid var(--line)">{md(p[3])}</p>
    </div>"""
        for p in D["portability"]
    )

    host_rows = "".join(
        f"""<tr>
      <td><div class="tname">{html.escape(h[0])}</div><div class="comp">{html.escape(h[1])} · {html.escape(h[2])}</div></td>
      <td><div class="comp">{html.escape(h[3])}</div></td>
      <td><div class="comp">{html.escape(h[4])}</div></td>
      <td><div class="comp">{html.escape(h[5])}</div></td>
      <td><div class="comp">{html.escape(h[6])}</div></td>
      <td><div class="note">{html.escape(h[7])}</div></td>
      <td><div class="note">{html.escape(h[8])}</div></td>
      <td><span class="v v-{'DISABLE' if h[9]=='GAP' else ('ENHANCE' if h[9]=='REFERENCE' else 'KEEP')}"
            style="color:{'var(--bad)' if h[9]=='GAP' else ('var(--acc)' if h[9]=='REFERENCE' else 'var(--keep)')}">{html.escape(h[9])}</span></td>
      <td><div class="note">{html.escape(h[10])}</div></td>
    </tr>"""
        for h in D["host_layers"]
    )

    jcode_fact_rows = "".join(
        f"""<tr><td style="white-space:nowrap;vertical-align:top"><div class="tname" style="font-size:12px">{html.escape(f[0])}</div></td>
        <td><div class="note" style="max-width:720px">{html.escape(f[1])}</div></td></tr>"""
        for f in D["jcode_facts"]
    )

    jcode_hook_rows = "".join(
        f"""<tr><td><div class="tname" style="font-size:12.5px">{html.escape(h[0])}</div></td>
        <td><div class="comp">{html.escape(h[1])}</div></td>
        <td><div class="note" style="color:var(--tx)">{html.escape(h[2])}</div></td></tr>"""
        for h in D["jcode_hooks"]
    )

    html_doc = f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>enact-agent · Tool &amp; Hook Surface Review vs oh-my-pi and lean-ctx</title>
<style>{CSS}</style>
</head>
<body>
<header><div class="wrap hd">
  <div class="logo">enact-tools <span>· surface review</span></div>
  <nav>
    <a href="#summary">Summary</a>
    <a href="#systems">The Three Systems</a>
    <a href="#baseline">Baseline</a>
    <a href="#matrix">Full Matrix</a>
    <a href="#additions">New Tools</a>
    <a href="#hooks">Hooks</a>
    <a href="#portability">Portability</a>
    <a href="#jcode">jcode</a>
    <a href="#consolidate">Consolidation</a>
    <a href="#roadmap">Roadmap</a>
    <a href="#method">Method</a>
  </nav>
  <button class="tgl" id="theme">Light mode</button>
</div></header>

<div class="wrap">

<section class="hero" id="summary">
  <div class="eyebrow">Comparative Analysis · 2026-11-12</div>
  <h1>What enact-agent should borrow from<br>oh-my-pi and lean-ctx</h1>
  <p class="sub">A full audit of three agent tool surfaces — <code>enact-agent</code> (93 built-ins / 226 operations),
  <code>oh-my-pi</code> (30 built-ins) and <code>lean-ctx</code> (51 MCP tools) — plus their hook subsystems,
  distilled into a concrete <b>add / keep / enhance / merge</b> plan.</p>

  <div class="stats">
    <div class="stat"><div class="n">{stats['total_tools']}</div><div class="l">enact built-ins</div><div class="d">{stats['total_ops']} operations, 3 tiers</div></div>
    <div class="stat d"><div class="n">{stats['disabled_tools']}</div><div class="l">disabled in build</div><div class="d">{stats['disabled_ops']} operations off</div></div>
    <div class="stat m"><div class="n">{stats['post_merge_tools']}</div><div class="l">after merging</div><div class="d">from {stats['total_tools']}, zero ops lost</div></div>
    <div class="stat x"><div class="n">{v['ADD']}</div><div class="l">new tools</div><div class="d">from oh-my-pi + lean-ctx</div></div>
    <div class="stat a"><div class="n">{len(D['hooks'])}</div><div class="l">hook capabilities</div><div class="d">1 blocker identified</div></div>
  </div>
</section>

<section id="systems">
  <div class="shead"><h2>The three systems</h2><span class="tag">at a glance</span></div>
  <p class="lede">Each solves a different problem, and each is stronger than the others somewhere.
  The point of the comparison is not to copy a tool list — it is to see which <i>mechanisms</i> close gaps in enact-agent.</p>

  <div class="cards">
    <div class="card hi">
      <h4>enact-agent <span class="pill acc">baseline</span></h4>
      <div class="who">zeroclaw fork · Rust · 93 built-ins · 226 ops</div>
      <ul>
        <li><b>Rigorous three-axis model.</b> Tier (Core 11 / Host 51 / Optional 31) × compilation (Always / External / OptIn) × catalog selector (<code>[tools].optional</code>). Neither competitor has anything close.</li>
        <li><b>Strongest safety surface.</b> Risk profiles, Landlock/Bubblewrap/Seatbelt/Docker sandboxes, approval gates, HMAC-signed tool receipts, default-deny MCP bundle scoping.</li>
        <li><b>Unique runtime primitives.</b> SOP engine with approval gates and resumable runs; 30+ channel adapters; A2A client; ACP; gateway + web dashboard.</li>
        <li><b>The gap.</b> Hooks are a Rust trait only — <b>no user can write a hook</b>. No structural code tools, no context tooling, no plan/goal mode.</li>
      </ul>
    </div>

    <div class="card">
      <h4>oh-my-pi <span class="pill k">tool craft</span></h4>
      <div class="who">Rust + TS monorepo · 30 built-ins + 3 hidden</div>
      <ul>
        <li><b>Schema budget discipline.</b> Tools are <code>essential</code> (13, always top-level) or <code>discoverable</code> (mounted behind <code>xd://</code> devices, found by BM25). Unused schemas never enter the request.</li>
        <li><b>Best hook system of the three.</b> ~45 events, plain TypeScript files, <code>.omp/hooks/pre|post/*.ts</code>, with documented ordering, budgets and fail-closed semantics.</li>
        <li><b>Richest code intelligence.</b> <code>ast_grep</code>, <code>ast_edit</code>, <code>lsp</code>, <code>debug</code>, <code>find</code> — none of which enact-agent has.</li>
        <li><b>Modes.</b> Plan, Goal and Vibe. Plus approval tiers (read/write/exec) and restricted folders.</li>
      </ul>
    </div>

    <div class="card">
      <h4>lean-ctx <span class="pill m">context engine</span></h4>
      <div class="who">Rust · 51 public MCP tools · 12-tool lazy core</div>
      <ul>
        <li><b>Already did the consolidation.</b> 82 registry entry points → <b>35 canonical tools</b> with typed <code>action</code> enums, shipped in 3.11.5. Legacy names survive as aliases.</li>
        <li><b>Context as a first-class surface.</b> <code>compose</code>, <code>expand</code>, <code>compress</code>, <code>preload/prefetch</code>, <code>control</code> overlays, budget radar.</li>
        <li><b>Hook dialects for 11 hosts.</b> Installs into Claude Code, Codex, Cursor, Windsurf, Gemini, Copilot, Kiro, Cline, Vibe, CodeBuddy, Qoder.</li>
        <li><b>Two ideas worth stealing outright:</b> <i>mirror, don't grant</i> (a rewrite may only approve what the host would have approved anyway) and <i>never invalidate the cache prefix</i>.</li>
      </ul>
    </div>
  </div>

  <div class="call good">
    <h4>The headline finding</h4>
    <p>enact-agent already stores <b>tool name + operation enum</b> for all 226 operations — exactly the data model lean-ctx
    converged on. The 93 separate tool names are a presentation choice, not a structural constraint.
    Merging sibling families takes the surface to <b>{stats['post_merge_tools']} tools with zero operations lost</b>,
    and lean-ctx already proved the migration path (canonical + alias + telemetry before removal).</p>
  </div>
</section>

<section id="baseline">
  <div class="shead"><h2>Baseline: enact-agent today</h2><span class="tag">93 built-ins · 226 operations</span></div>
  <p class="lede">Where the current surface stands, and what the 13 disabled tools mean for the comparison.</p>

  <div class="cards">
    <div class="card">
      <h4>Tier 1 — Core <span class="pill k">11</span></h4>
      <div class="who">Always compiled · always in the minimal set</div>
      <ul><li><b>shell</b> · <b>file_read</b> · <b>file_write</b> · <b>file_edit</b> · <b>glob_search</b> · <b>content_search</b></li>
      <li><b>git_operations</b> · <b>memory_store</b> · <b>memory_recall</b> · <b>memory_forget</b> · <b>web_fetch</b></li></ul>
    </div>
    <div class="card">
      <h4>Tier 2 — Host-coupled <span class="pill acc">51</span></h4>
      <div class="who">Runtime keeps constructing them</div>
      <ul><li><b>Scheduling</b> cron_* ×6 + schedule</li>
      <li><b>Agent execution</b> spawn_subagent · delegate · send_message_to_peer</li>
      <li><b>Control plane</b> model_switch · model_routing_config · proxy_config</li>
      <li><b>Sessions</b> · <b>SOP</b> ×6 · <b>Channels</b> · <b>ACP</b> · <b>A2A</b> ×4 · <b>MCP</b> ×2</li></ul>
    </div>
    <div class="card">
      <h4>Tier 3 — Optional <span class="pill d">31</span></h4>
      <div class="who">Buildable from ToolRequest alone</div>
      <ul><li><b>9 register on a default config</b>: calculator · weather · pushover · screenshot · image_info · browser_open · http_request · web_search_tool · backup</li>
      <li>Rest need explicit config or an OptIn feature</li></ul>
    </div>
    <div class="card">
      <h4>Disabled in the Enact build <span class="pill d">13</span></h4>
      <div class="who">{stats['disabled_ops']} of {stats['total_ops']} operations are compiled out</div>
      <ul><li><b>OptIn SaaS</b> notion · jira · linkedin · composio · google_workspace · microsoft365</li>
      <li><b>OptIn coding CLIs</b> claude_code · codex_cli · gemini_cli · opencode_cli · claude_code_runner</li>
      <li><b>OptIn workflow</b> project_intel · report_template</li></ul>
      <p style="color:var(--tx3);font-size:12.5px;margin:10px 0 0">The live config is <code>optional = ["*"]</code> — full selection —
      but a compiled-out adapter can never be added by config. lean-ctx answers the same need with one
      <code>ctx_provider</code> gateway instead of six bespoke tools.</p>
    </div>
  </div>
</section>

<section id="matrix">
  <div class="shead"><h2>Full tool matrix</h2><span class="tag">all {stats['total_tools']} tools</span></div>
  <p class="lede">Every enact-agent built-in, its operations, and the verdict: <b>KEEP</b> as-is,
  <b>ENHANCE</b> in place, <b>MERGE</b> into an action-enum family tool, <b>EXT</b>ernalise,
  or <b>DISABLE</b> (already compiled out — leave off). Green dots mark a named counterpart in the other project.</p>

  <div class="bars">{vrow}</div>
  <p class="count" style="display:block;margin:4px 0 18px">Verdict distribution across all {vtotal} decisions — {stats['total_tools']} existing built-ins + {v['ADD']} proposed additions.</p>

  <div class="tbar">
    <input type="search" id="q" placeholder="Search tools, operations, or notes…">
    <select id="fv"><option value="">All verdicts</option><option>ADD</option><option>KEEP</option><option>ENHANCE</option><option>MERGE</option><option>EXT</option><option>DISABLE</option></select>
    <select id="ft"><option value="">All tiers</option><option>Core</option><option>Host</option><option>Optional</option></select>
    <select id="fs"><option value="">All build states</option><option value="on">Compiled in</option><option value="off">Disabled</option></select>
    <span class="count" id="cnt"></span>
  </div>

  <div class="tbl"><div class="scroll"><table>
    <thead><tr>
      <th>Tool</th><th>Operations</th><th>Tier</th><th>Verdict</th>
      <th>oh-my-pi</th><th>lean-ctx</th><th>Recommendation</th>
    </tr></thead>
    <tbody id="tbody"></tbody>
  </table></div></div>
</section>

<section id="additions">
  <div class="shead"><h2>Tools to add</h2><span class="tag">{v['ADD']} proposals</span></div>
  <p class="lede">Capabilities that exist in oh-my-pi or lean-ctx and have no counterpart in enact-agent.
  <b>P0</b> is the highest-value/lowest-effort set — four of these close a structural gap rather than adding breadth.</p>

  <div class="tbar">
    <input type="search" id="nq" placeholder="Search proposals…">
    <select id="nfp"><option value="">All priorities</option><option>P0</option><option>P1</option><option>P2</option><option>P3</option></select>
    <span class="count" id="ncnt"></span>
  </div>

  <div class="tbl"><div class="scroll"><table>
    <thead><tr><th>Proposed tool</th><th>What it does</th><th>Source</th><th>Priority</th><th>Area</th><th>Why</th></tr></thead>
    <tbody id="ntbody"></tbody>
  </table></div></div>
</section>

<section id="hooks">
  <div class="shead"><h2>Hook systems compared</h2><span class="tag">{len(D['hooks'])} capabilities</span></div>
  <p class="lede">The decisive difference: enact-agent's hooks are a Rust trait that only embedders can implement.
  oh-my-pi lets a user drop a TypeScript file in a folder; lean-ctx writes JSON or TOML into other agents' homes.
  <b>Enact-agent is the only one of the three where a user cannot add a hook at all.</b></p>

  <div class="call bad">
    <h4>Blocker — no user-scriptable hooks</h4>
    <p><code>HooksConfig</code> exposes exactly two fields (<code>enabled</code>, <code>builtin</code>) and
    <code>BuiltinHooksConfig</code> exactly two more (<code>command_logger</code>, <code>webhook_audit</code>).
    The WASM plugin system has capabilities <code>Tool | Channel | Memory | Observer | Skill</code> — <b>no Hook</b>.
    There is also no page in <code>docs/book/src/</code> describing the hook system at all.</p>
    <p>This is the single highest-leverage gap: the trait already models 18 events with correct cancel semantics,
    priority ordering and panic isolation. It needs an external surface, not a redesign.</p>
  </div>

  <div class="tbar">
    <input type="search" id="hq" placeholder="Search hook capabilities…">
    <span class="count" id="hcnt"></span>
  </div>

  <div class="tbl"><div class="scroll"><table>
    <thead><tr><th>Capability</th><th>enact-agent</th><th>oh-my-pi</th><th>lean-ctx</th><th>Verdict</th></tr></thead>
    <tbody id="htbody"></tbody>
  </table></div></div>

  <h3>What to adopt, concretely</h3>
  <div class="cards">
    <div class="card">
      <h4>1 · Declarative hook config</h4>
      <div class="who">enact-agent · new surface</div>
      <ul><li>TOML or JSON: <code>[hooks.commands.pre_tool_call]</code> → command + matcher + timeout</li>
      <li>stdin JSON payload, stdout JSON decision (<code>block</code>, <code>input</code>, <code>additionalContext</code>)</li>
      <li>Reuse the existing <code>HookRunner</code> dispatch — no trait change</li>
      <li>Follow lean-ctx's budget rule: fail-open on timeout, fail-closed on policy</li></ul>
    </div>
    <div class="card">
      <h4>2 · Plugin hook capability</h4>
      <div class="who">enact-agent · WASM plugins</div>
      <ul><li>Add <code>PluginCapability::Hook</code> to the five existing capabilities</li>
      <li>Signed manifests already exist (Ed25519) — the trust model is in place</li>
      <li>Give plugins a stdin/stdout hook host service, like the existing http/websocket/socket services</li></ul>
    </div>
    <div class="card">
      <h4>3 · Post-call output rewriting</h4>
      <div class="who">oh-my-pi + lean-ctx</div>
      <ul><li>enact-agent can block and rewrite <i>inputs</i>, but not rewrite <i>output</i></li>
      <li>Add <code>on_after_tool_call</code> → result patch (content / success flag)</li>
      <li>Unlocks dedup, compression and redaction at the tool boundary</li></ul>
    </div>
    <div class="card">
      <h4>4 · Trust-boundary discipline</h4>
      <div class="who">oh-my-pi docs/hooks.md</div>
      <ul><li>Separate <b>trusted</b> handler-authored context from <b>untrusted</b> tool output</li>
      <li>oh-my-pi delivers hook context with developer/system priority</li>
      <li>enact-agent's <code>before_llm_call</code> can inject context — but the two channels are not distinguished</li></ul>
    </div>
  </div>
</section>

<section id="portability">
  <div class="shead"><h2>One tool system across Codex &amp; Claude Code</h2><span class="tag">portability</span></div>
  <p class="lede">Can one tool system be handed to both Codex and Claude Code? <b>Yes — but not through a tool
  list.</b> Every host speaks MCP, and each has its own instruction and policy conventions. The answer is a
  six-layer stack, and every layer has a proven reference implementation.</p>

  <div class="call bad">
    <h4>The one gap that blocks it: enact-agent cannot serve MCP</h4>
    <p><code>crates/zeroclaw-tools/src/</code> ships <code>mcp_client.rs</code>, <code>mcp_transport.rs</code>,
    <code>mcp_tool.rs</code>, <code>mcp_deferred.rs</code> — an MCP <b>client</b>. There is no server implementation
    anywhere in the tree: no <code>ServerHandler</code>, no <code>list_tools</code>/<code>call_tool</code> server side,
    no <code>rmcp</code> dependency. The protocol is hand-rolled on the client side.</p>
    <p>This matters because <b>Codex CLI has no server mode either</b> — it is an MCP client and nothing more.
    Claude Code can serve its own tools (<code>claude mcp serve</code>); Codex cannot. So the only way to give Codex
    a tool set you control is to <b>be an MCP server</b>. That single missing mode is the whole difference between
    "enact-agent is one agent among many" and "enact-agent is the tool layer for every agent you use".</p>
  </div>

  <h3>The six-layer stack</h3>
  <div class="cards" style="grid-template-columns:repeat(auto-fit,minmax(340px,1fr))">
    {port_cards}
  </div>

  <h3>Who does what, today</h3>
  <p class="lede">Nine systems, compared on the axes that decide whether a tool set can cross host boundaries.
  <b>GAP</b> means the capability is missing; <b>REFERENCE</b> means it is the model others copy.</p>

  <div class="tbar">
    <input type="search" id="pq" placeholder="Search systems…">
    <span class="count" id="pcnt"></span>
  </div>

  <div class="tbl"><div class="scroll"><table>
    <thead><tr>
      <th>System</th><th>MCP client</th><th>MCP server</th><th>Hook surface</th>
      <th>Instructions</th><th>Claude Code</th><th>Codex</th><th>Verdict</th><th>Note</th>
    </tr></thead>
    <tbody id="ptbody"></tbody>
  </table></div></div>

  <div class="call good">
    <h4>The pattern everyone converged on</h4>
    <p>Read the MCP column again: <b>every serious system is an MCP client</b>, and the ones that are also
    <i>layers</i> rather than agents — lean-ctx, Serena — are MCP servers. jcode, goose and oh-my-pi go further and
    deliberately <b>read the host's own config</b>: jcode reads Claude Code's live <code>~/.claude.json</code> and
    one-time-imports Codex's <code>~/.codex/config.toml</code>; goose imports Claude Desktop's MCP config on first run
    and reads <code>~/.claude/agents</code> and <code>~/.claude/skills</code>. The convention is portable even when
    the product is not.</p>
  </div>
</section>

<section id="jcode">
  <div class="shead"><h2>jcode</h2><span class="tag">1jehuang/jcode · Rust · MIT · ~21k★</span></div>
  <p class="lede">The Rust harness you named. A single native binary built for running <i>dozens</i> of agents in
  parallel: ~19 ms time-to-first-input, megabytes per extra session, and a server-coordinated swarm that resolves
  the "agent B read a file agent A just edited" conflict for you.</p>

  <div class="call good">
    <h4>★ The finding that answers "pass one tool system to them"</h4>
    <p>jcode's Harness API does more than drive a UI — it lets an <b>external client inject a whole tool set</b>.
    <code>ApiRequest::ConfigureTools {{ session_id, tools: ToolConfiguration }}</code> carries
    <code>enabled</code>, <code>disabled</code> and <code>custom: Vec&lt;SessionToolDefinition&gt;</code>. A custom
    tool may even override a built-in of the same name. When the model calls it, the runtime emits a
    <code>ToolCall</code> event down <i>that client's own connection</i> and blocks; the client answers with a
    <code>ToolResult</code> (120 s deadline).</p>
    <p>And it keeps the safety model intact: a custom tool is an <i>execution adapter only, never installed in the
    shared registry</i> — so hooks, telemetry, output limits and permission gates behave exactly as they do for
    built-ins. That is a complete, versioned contract for being the tool layer for a runtime you do not own.</p>
  </div>

  <div class="cards">
    <div class="card hi">
      <h4>Harness API <span class="pill x">tool injection</span></h4>
      <div class="who">crates/jcode-harness-api · API_VERSION_MAJOR 1 / MINOR 11 · Unix socket, NDJSON</div>
      <ul>
        <li><b>A stable, versioned boundary between the harness and ANY UI</b> — TUI, desktop, web, scripts. Deliberately smaller than the internal <code>jcode-protocol</code>; only curated surface is public.</li>
        <li><b>NDJSON, one JSON object per line.</b> Every frame carries <code>v</code> (protocol major). Clients must ignore unknown fields and skip unknown event kinds.</li>
        <li><b>Additive changes bump the minor version; breaking changes bump major and must be negotiated in the handshake.</b></li>
        <li><b>The tool surface is reconfigurable at runtime</b> — enable, disable and add custom tools per session, with session-scoped ownership so a stale client cannot remove a successor's policy.</li>
        <li>There is also a TypeScript SDK (<code>@1jehuang/jcode-sdk</code>) with schema parity tests against the Rust side.</li>
      </ul>
    </div>
    <div class="card">
      <h4>MCP config interop</h4>
      <div class="who">crates/jcode-base/src/mcp/protocol.rs</div>
      <ul>
        <li><b>Project precedence:</b> <code>.jcode/mcp.json</code> → <code>.mcp.json</code> (Claude Code) → <code>.claude/mcp.json</code>. Later files override same-named servers.</li>
        <li><b>Claude Code stays a live source</b> — <code>~/.claude.json</code> is read, never copied.</li>
        <li><b>Codex is a one-time migration:</b> imported from <code>~/.codex/config.toml</code> <code>[mcp_servers.*]</code>, and only while <code>~/.jcode/mcp.json</code> does not exist.</li>
        <li><b>Runnable wins:</b> an existing working stdio server is kept over a lower-precedence definition, with a log line. A broken higher-precedence entry does not shadow a working one.</li>
      </ul>
    </div>
    <div class="card">
      <h4>Schema budget &amp; cache safety</h4>
      <div class="who">crates/jcode-app-core/src/tool/mcp.rs · agent.rs</div>
      <ul>
        <li><b>Three layers of mitigation.</b> Providers with native deferred loading get <code>defer_loading</code> + <code>cache_control</code>; the rest get a fixed <code>mcp</code> / <code>mcp_search</code> / <code>mcp_call</code> surface (<code>mcp_search</code> and <code>mcp_call</code> are compatibility aliases, not model-visible); and tools that arrive late are announced in the transcript instead of the cached prefix.</li>
        <li><b><code>mcp_search</code> budgets</b> — at most <b>32</b> tool references, under a <b>6 000-token</b> result budget; a broad query trims descriptions first, then drops schemas for lower-ranked matches. Description-only matches are dropped once any name matches.</li>
        <li><b>The tool list is locked after the first request</b> so the provider prompt cache is not invalidated. MCP servers connect in the background; exactly <b>one</b> deliberate rebuild is allowed to pick them up — an intentional one-time cache miss, latched by a guard that is deliberately not re-armed.</li>
        <li><b>Advertise-early</b>: proxy tools are registered from the on-disk schema cache before connections settle, so the first locked snapshot already contains MCP tools and the cache miss can be avoided entirely.</li>
        <li><b>AGENTS.md and the skills prompt section are snapshotted</b> at session start, so tool writes cannot mutate the provider's cacheable prefix mid-session.</li>
      </ul>
    </div>
    <div class="card">
      <h4>Swarm &amp; self-development</h4>
      <div class="who">crates/jcode-swarm-core · tool/communicate.rs</div>
      <ul>
        <li><b>The swarm tool is <code>communicate</code></b>, exposed as <code>swarm</code>. It spawns and coordinates child agents, DMs one agent, broadcasts to all, or broadcasts to one repo.</li>
        <li><b>File-change notices.</b> When agent A edits a file agent B has read, B is notified and can inspect the diff before it conflicts.</li>
        <li><b>Agents can spawn their own swarms</b> — the main agent becomes a coordinator, spawned agents become workers.</li>
        <li><b>Self-dev mode:</b> an agent edits, builds, tests and reloads jcode's own binary mid-session.</li>
      </ul>
    </div>
  </div>

  <h3>jcode's external-program hooks</h3>
  <p class="lede">jcode keeps its hook system deliberately small: eight events, each a command string or an array of
  commands, executed directly rather than through a shell. Observers run in declaration order; gates run
  sequentially and the first block wins. Notably, <code>post_tool_feedback</code> feeds its stdout back into the
  tool result — that is how linters and checkers report findings straight to the model.</p>

  <div class="tbl"><div class="scroll"><table>
    <thead><tr><th style="width:220px">Hook</th><th style="width:260px">Trigger</th><th>Capability</th></tr></thead>
    <tbody id="jhbody"></tbody>
  </table></div></div>

  <h3>jcode facts</h3>
  <div class="tbl"><div class="scroll"><table>
    <thead><tr><th style="width:210px">Aspect</th><th>Detail</th></tr></thead>
    <tbody>{jcode_fact_rows}</tbody>
  </table></div></div>

  <h3>jcode's {len(D['jcode_tools'])} built-in tools</h3>
  <div class="tbar">
    <input type="search" id="jq" placeholder="Search jcode tools…">
    <span class="count" id="jcnt"></span>
  </div>
  <div class="tbl"><div class="scroll"><table>
    <thead><tr><th style="width:220px">Tool</th><th>Purpose</th></tr></thead>
    <tbody id="jtbody"></tbody>
  </table></div></div>

  <div class="call">
    <h4>What jcode is actually evidence for</h4>
    <p>jcode is <b>not</b> a competitor to enact-agent's tool surface — it is a second Rust agent runtime that
    happens to solve the same context-budget problem three more times over. Its value here is threefold:
    it proves the <b>search + call</b> pattern for MCP schemas works in production, it shows the
    <b>config-interop precedence chain</b> that lets one agent read another agent's MCP servers, and its
    <b>Harness API</b> is a clean model for the kind of stable, versioned, host-agnostic boundary enact-agent's
    ACP gateway is reaching for.</p>
    <p>The most transferable single idea: <b>read the hosts' configs instead of asking users to re-declare
    everything.</b> Claude Code's <code>~/.claude.json</code>, Codex's <code>~/.codex/config.toml</code>,
    <code>AGENTS.md</code>, <code>SKILL.md</code> — those are the portable surfaces, and three of the four systems
    surveyed already read them.</p>
  </div>
</section>

<section id="consolidate">
  <div class="shead"><h2>Consolidation plan</h2><span class="tag">93 → {stats['post_merge_tools']} tools</span></div>
  <p class="lede">Sibling families that share a prefix and are always used together collapse into one tool with a typed
  action enum. <b>All {stats['total_ops']} operations survive</b> — only the tool names change.
  This is exactly the migration lean-ctx ran between 3.11.4 and 3.11.5: canonical tool + typed actions + legacy aliases
  + telemetry before removal.</p>

  <div class="call">
    <h4>Why this matters beyond tidiness</h4>
    <p>lean-ctx states the case directly: <i>"Agents currently receive too many overlapping MCP tool definitions.
    Large tool lists consume context, duplicate concepts across schemas, and make tool choice less reliable."</i>
    oh-my-pi solves the same problem from the other end — 13 <code>essential</code> tools in the schema,
    everything else behind <code>xd://</code> devices and BM25 discovery. enact-agent has
    <code>deferred_builtin_tools</code> and <code>tool_search</code> already, but the default catalog is still flat and large.</p>
  </div>

  <div class="tbl" style="padding:6px 18px">
    {merge_rows}
  </div>

  <h3>Sequencing, following lean-ctx's playbook</h3>
  <div class="cards">
    <div class="card"><h4>Step 1</h4><div class="who">no behaviour change</div>
      <ul><li>Introduce the canonical family tool with a typed <code>action</code> enum</li>
      <li>Keep every old name registered as a <b>thin alias</b> that validates, translates, and delegates</li>
      <li>Emit a one-time deprecation notice <b>outside</b> the tool result body</li></ul></div>
    <div class="card"><h4>Step 2</h4><div class="who">default catalog</div>
      <ul><li>Make the merged surface the default in <code>all_tools</code></li>
      <li>Keep a compatibility profile that advertises the legacy aliases</li>
      <li>Derive counts from the registry, never by hand</li></ul></div>
    <div class="card"><h4>Step 3</h4><div class="who">proof</div>
      <ul><li>Table-driven test: every legacy name routes to exactly one canonical action</li>
      <li>Assert alias and canonical results are byte-identical</li>
      <li>Assert the default profile advertises the new count</li></ul></div>
    <div class="card"><h4>Step 4</h4><div class="who">later</div>
      <ul><li>Remove aliases only in a major version</li>
      <li>Only after telemetry shows no alias use for two release cycles</li>
      <li>Publish the removal date and replacement route in release notes first</li></ul></div>
  </div>

  <div class="call good">
    <h4>Bonus: one gateway instead of six SaaS tools</h4>
    <p>The 13 disabled OptIn adapters are all the same shape — a vendor API behind an auth model.
    lean-ctx replaces all of them with one <code>ctx_provider</code> gateway (GitHub, GitLab, Jira, Postgres, MCP bridges, custom REST).
    If enact-agent wants those integrations back later, that is one tool to build, not six.</p>
  </div>
</section>

<section id="roadmap">
  <div class="shead"><h2>Recommended roadmap</h2><span class="tag">four phases</span></div>
  <p class="lede">Ordered by leverage, not by difficulty. Phase 1 closes the structural gaps; Phase 4 is optional polish.</p>

  <div class="rm">
    <div class="phase">
      <h4>Phase 0 · Become a tool layer <span class="pill" style="color:var(--bad);border-color:var(--bad)55">unlocks everything else</span></h4>
      <div class="meta">the only change that makes one tool set usable from Codex AND Claude Code</div>
      <div class="status"><b>Shipped.</b> A native MCP server (stdio and HTTP) serves the registry through <code>mcp_search</code>/<code>mcp_call</code>; it reads <code>~/.codex/config.toml</code>, <code>~/.claude.json</code> and the project <code>.mcp.json</code> with runnable-server precedence, and the bridge ships one AGENTS.md block, one CLAUDE.md, one settings file and one SKILL.md for both hosts.</div>
      <ul>
        <li><b>Add an MCP server mode</b> — <code>zeroclaw-mcp serve</code> exposing the tool registry over stdio (and HTTP). Today enact-agent is an MCP <i>client</i> only; Codex has no server mode either, so this is the only way to hand Codex a tool set you control.</li>
        <li><b>Adopt the search + call pattern</b> — expose <code>mcp_search</code> / <code>mcp_call</code> instead of advertising every MCP schema. jcode caps it at 32 references under a 6 000-token budget; enact-agent already has <code>tool_search</code> and <code>mcp_deferred</code> to build on.</li>
        <li><b>Read the hosts' MCP config</b> — <code>.mcp.json</code>, <code>~/.claude.json</code>, and a one-time import from <code>~/.codex/config.toml</code>, using jcode's precedence rules (runnable server wins over a lower-precedence broken one).</li>
        <li><b>Ship AGENTS.md + SKILL.md</b> so the same instructions load in both hosts, and honour each host's own policy surface (Codex <code>.rules</code>, Claude Code permissions) rather than assuming one model.</li>
      </ul>
    </div>

    <div class="phase">
      <h4>Phase 1 · Close the structural gaps <span class="pill" style="color:var(--bad);border-color:var(--bad)55">highest leverage</span></h4>
      <div class="meta">the one gap a user actually hits: they cannot add a hook</div>
      <div class="status"><b>Shipped.</b> Declarative hook config (six events, stdin JSON in, JSON decision out, per-hook timeout and fail-open), a hooks documentation page, post-call output rewriting that runs before the result is logged, and a trusted/untrusted split on the injection path are in. A WASM plugin can now serve as a hook too: the <code>hook-plugin</code> world, the <code>PluginCapability::Hook</code> capability, and the adapter that binds it to the same hook runner the command hooks use.</div>
      <ul>
        <li><b>Declarative hook config</b> — TOML/JSON mapping events to commands, stdin JSON in, JSON decision out. Reuse the existing <code>HookRunner</code> and its cancel/priority/panic semantics.</li>
        <li><b>Add <code>PluginCapability::Hook</code></b> so WASM plugins can register hooks with the existing Ed25519 trust model.</li>
        <li><b>Document the hook system</b> — it currently has no page in <code>docs/book/src/</code>.</li>
        <li><b>Add post-call output rewriting</b> to <code>on_after_tool_call</code> — unlocks dedup, compression and redaction at the tool boundary.</li>
        <li><b>Split trusted vs untrusted context</b> on the <code>before_llm_call</code> injection path.</li>
      </ul>
    </div>

    <div class="phase">
      <h4>Phase 2 · Context and code intelligence <span class="pill" style="color:var(--warn);border-color:var(--warn)55">the missing half</span></h4>
      <div class="meta">enact-agent can act on a machine but cannot reason about its context or its code</div>
      <div class="status"><b>Shipped.</b> <code>compose</code>, <code>expand</code>, <code>ast_grep</code>, <code>ast_edit</code>, <code>callgraph</code>, <code>graph</code> and <code>radar</code> are registered, and <code>file_read</code> grew the five read modes. Oversized tool output is archived, and <code>expand</code> retrieves it.</div>
      <ul>
        <li><b>compose</b> — one-call context assembly (ranked files + inline source). Replaces search→read→read chains; the single highest-value addition.</li>
        <li><b>expand</b> — retrieve archived output, so any future compression stays lossless.</li>
        <li><b>Read modes on file_read</b> — signatures, outline, diff, anchored, task. Orientation stops costing whole files.</li>
        <li><b>ast_grep + ast_edit</b> — structural code queries and previewed structural rewrites. Nothing in enact-agent matches this.</li>
        <li><b>callgraph + graph</b> — blast-radius analysis that content search cannot provide.</li>
        <li><b>radar</b> — context budget attribution. enact-agent tracks cost but not context spend.</li>
      </ul>
    </div>

    <div class="phase">
      <h4>Phase 3 · Surface consolidation <span class="pill m">93 → {stats['post_merge_tools']}</span></h4>
      <div class="meta">following lean-ctx's shipped 3.11.5 migration</div>
      <div class="status"><b>Shipped.</b> {stats['total_tools']} source tools become <b>{stats['post_merge_tools']} canonical tools</b> — the {stats['merged_tool_count']} siblings collapse into {len(D['merges'])} families whose action enums are the operations themselves, so nothing is lost. Legacy names keep working and carry a one-time notice beside the result body. The native and bridge surfaces publish the same action names, and the count is derived from the registry.</div>
      <ul>
        <li>Merge the {stats['merged_tool_count']} sibling tools into <b>{len(D['merges'])} family tools</b> with typed action enums, absorbing {stats['ops_absorbed']} operations with none lost.</li>
        <li>Canonical tool + legacy aliases + one-time deprecation notice outside the result body.</li>
        <li>Derive the advertised count from the registry; assert it in a test rather than by hand.</li>
        <li>Then lean on <code>deferred_builtin_tools</code> and <code>tool_search</code> for a bounded default schema.</li>
      </ul>
    </div>

    <div class="phase">
      <h4>Phase 4 · Coordination and modes <span class="pill">optional</span></h4>
      <div class="meta">copy where a competitor is clearly ahead; leave enact-agent's own strengths alone</div>
      <div class="status"><b>Shipped.</b> <code>wait</code> blocks on the durable task registry with a bounded timeout; <code>learn</code> records a lesson and can fold it into a named skill, and the skill tools are registered; approval tiers classify every tool read, write or exec and an operator may name a tier in <code>auto_approve</code> or <code>always_ask</code>; <code>checkpoint</code> and <code>rewind</code> mark and return to a point in the conversation; <code>plan_mode</code> puts the turn in plan mode, where only the read-tier tools run, and <code>plan_execute</code> asks the operator to let it act again. The three that need the conversation's history share one channel: the turn loop owns it, and the tools borrow it.</div>
      <ul>
        <li><b>wait</b> — await async results instead of polling (both competitors forbid polling).</li>
        <li><b>learn + manage_skill</b> — close the loop from a correction to a durable skill. enact-agent implements <code>skill_manage</code> but deliberately does not register it.</li>
        <li><b>checkpoint + rewind</b> — auto-include the pair; a one-sided tool strands the agent.</li>
        <li><b>Plan mode</b> — enact-agent has no plan/ask/research mode at all.</li>
        <li><b>Approval tiers</b> — read/write/exec, as a refinement of the existing risk profile and sandbox system.</li>
      </ul>
    </div>
  </div>

  <h3>What to leave alone</h3>
  <div class="call good">
    <p>enact-agent's <b>three-axis tier model</b>, <b>tool receipts</b>, <b>sandbox backends</b>, <b>approval gates</b>,
    <b>SOP engine</b>, <b>channel breadth</b>, <b>A2A client</b> and <b>per-agent MCP scoping</b> have no counterpart in
    either competitor and are stronger than what oh-my-pi or lean-ctx offer. The recommendation is
    <b>add and enhance</b>, never <b>replace</b>. In particular, keep the availability-vs-authorization split
    (<code>/// Availability only: callers must still enforce policy and prerequisites.</code>) —
    it is the cleanest expression of the safety model in any of the three projects.</p>
  </div>
</section>

<section id="method">
  <div class="shead"><h2>Method &amp; sources</h2><span class="tag">evidence</span></div>
  <div class="cards">
    <div class="card">
      <h4>Sources inspected</h4>
      <ul>
        <li><b>enact-agent</b> — <code>crates/zeroclaw-api/src/hook.rs</code>, <code>crates/zeroclaw-runtime/src/hooks/</code>, <code>crates/zeroclaw-config/src/builtin_tools.rs</code>, <code>crates/zeroclaw-config/src/schema.rs</code>, <code>crates/zeroclaw-tools/src/inventory.rs</code>, <code>docs/book/src/developing/tool-inventory.md</code>, <code>overlays/enact/</code></li>
        <li><b>oh-my-pi</b> — <code>packages/coding-agent/src/tools/builtin-names.ts</code>, <code>packages/coding-agent/src/tools/index.ts</code>, <code>packages/coding-agent/src/tools/essential-tools.ts</code>, <code>packages/coding-agent/src/extensibility/hooks/</code>, <code>packages/coding-agent/src/extensibility/extensions/</code>, <code>docs/hooks.md</code>, <code>README.md</code></li>
        <li><b>lean-ctx</b> — <code>rust/crates/lean-ctx-server/src/tools/registered/</code>, <code>rust/src/tool_defs/mod.rs</code>, <code>rust/crates/lean-ctx-hooks/src/</code>, <code>docs/tool-consolidation-plan.md</code>, <code>docs/PROTECTED-HOOKS.md</code>, <code>CONTRACTS.md</code></li>
      </ul>
    </div>
    <div class="card">
      <h4>How the numbers were derived</h4>
      <ul>
        <li><b>93 tools / 226 operations</b> — from <code>zeroclaw-tools-operations.csv</code> (unique <code>tool_name</code> × <code>operation</code>).</li>
        <li><b>13 disabled tools / 48 operations</b> — from the overlay copy at <code>overlays/enact/zeroclaw-tools-operations.csv</code>, which carries the real <code>compiled_in_enact</code> flags. The workspace copy of the CSV has that column rewritten to <code>TRUE</code> everywhere, which is why the disabled set is invisible there.</li>
        <li><b>Verdicts</b> — authored per tool from the three codebases; the merge set is derived mechanically from the CSV's <code>tool_name</code> families.</li>
      </ul>
    </div>
    <div class="card">
      <h4>Caveats</h4>
      <ul>
        <li>All findings are from <b>static source reads</b>; no crate was built or run.</li>
        <li>lean-ctx's tool counts are release-sensitive — its own catalog says not to repeat changing counts. Figures here are for the checked-out commit.</li>
        <li>oh-my-pi's <code>README.md</code> claims "31 built-in tools" while the registry lists 30 — an unreconciled drift in their repo.</li>
        <li>enact-agent's tier table is explicitly a <b>proposal</b> against a composition contract that is not yet in code, though the compiled inventory it backs is enforced by tests.</li>
      </ul>
    </div>
  </div>
</section>

<footer>
  <p>Generated from local clones of <a href="https://github.com/can1357/oh-my-pi">can1357/oh-my-pi</a> and
  <a href="https://github.com/yvgude/lean-ctx">yvgude/lean-ctx</a>, read against the
  <code>enact-agent</code> working tree and <code>zeroclaw-tools-operations.csv</code>.
  Research clones live under <code>research/</code>.</p>
</footer>

</div>
<script>{JS.replace('__STATS__', json.dumps(D['stats'])).replace('__VERDICTS__', json.dumps(D['verdicts'])).replace('__TOOLS__', json.dumps(D['tools'])).replace('__NEW__', json.dumps(D['new'])).replace('__HOOKS__', json.dumps(D['hooks'])).replace('__HOSTS__', json.dumps(D['host_layers'])).replace('__PORT__', json.dumps(D['portability'])).replace('__JTOOLS__', json.dumps(D['jcode_tools'])).replace('__JFACTS__', json.dumps(D['jcode_facts'])).replace('__JHOOKS__', json.dumps(D['jcode_hooks']))}</script>
</body></html>"""

    out = os.path.join(ROOT, "enact-tools-surface-review.html")
    with open(out, "w") as f:
        f.write(html_doc)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    build()
