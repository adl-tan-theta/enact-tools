#!/usr/bin/env python3
"""Render the Enact sync status report to a single self-contained HTML file."""
from __future__ import annotations

import html
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(ROOT, "status.json")))

CSS = r"""
:root{
  --bg:#0e1116; --bg2:#141922; --panel:#171d27; --panel2:#1c2430;
  --line:#253040; --line2:#2f3b4d;
  --tx:#e6edf6; --tx2:#9fb0c6; --tx3:#6b7c92;
  --acc:#5b9cff; --acc2:#7db4ff;
  --good:#3fb950; --warn:#f0883e; --bad:#f85149; --info:#a371f7;
  --r:10px; --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
html[data-theme=light]{
  --bg:#f6f8fb; --bg2:#ffffff; --panel:#ffffff; --panel2:#f0f4f9;
  --line:#dde5ee; --line2:#c9d5e3;
  --tx:#16202e; --tx2:#4a5b70; --tx3:#7c8ca0;
  --acc:#1668d6; --acc2:#0d5ac4;
  --good:#1a7f37; --warn:#bc4c00; --bad:#cf222e; --info:#8250df;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
  font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px 96px}
code,.mono{font-family:var(--mono);font-size:.88em}
code{background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:1px 5px;
  word-break:break-word}

header.top{border-bottom:1px solid var(--line);background:var(--bg2);position:sticky;top:0;z-index:10;
  backdrop-filter:blur(8px)}
.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;padding-top:14px;padding-bottom:14px}
.brand{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.brand h1{margin:0;font-size:17px;letter-spacing:-.01em}
.brand .sub{color:var(--tx3);font-size:13px}
.tbtn{background:var(--panel);border:1px solid var(--line);color:var(--tx2);border-radius:7px;
  padding:5px 12px;cursor:pointer;font-size:13px;font-family:inherit}
.tbtn:hover{border-color:var(--line2);color:var(--tx)}

.hero{padding:44px 0 8px}
.hero h2{margin:0 0 14px;font-size:31px;line-height:1.2;letter-spacing:-.022em;font-weight:650}
.hero p.lede{margin:0 0 22px;color:var(--tx2);font-size:16.5px;max-width:74ch}
.verdict{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--acc);
  border-radius:var(--r);padding:16px 20px;color:var(--tx);max-width:88ch}
.verdict b{color:var(--acc2)}

section{margin-top:52px}
section > h3{margin:0 0 6px;font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--tx3);
  font-weight:700}
section > .note{color:var(--tx2);font-size:14px;margin:0 0 18px;max-width:88ch}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px;margin-bottom:12px}
.card h4{margin:0 0 8px;font-size:16px}
.card p{margin:0 0 8px;color:var(--tx2)}
.card p:last-child{margin-bottom:0}

.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:12px}

.pill{display:inline-block;font-size:11px;letter-spacing:.05em;text-transform:uppercase;font-weight:700;
  padding:2px 8px;border-radius:20px;border:1px solid var(--line2);color:var(--tx3);
  vertical-align:middle;margin-left:8px}
.pill.good{color:var(--good);border-color:color-mix(in srgb,var(--good) 40%,transparent)}
.pill.warn{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 40%,transparent)}
.pill.bad{color:var(--bad);border-color:color-mix(in srgb,var(--bad) 40%,transparent)}
.pill.info{color:var(--info);border-color:color-mix(in srgb,var(--info) 40%,transparent)}

table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);
  border-radius:var(--r);overflow:hidden;font-size:14px}
th,td{text-align:left;padding:9px 14px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--panel2);color:var(--tx3);font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;font-weight:700}
tr:last-child td{border-bottom:none}
td.mono,th.mono{font-family:var(--mono);font-size:12.5px}

ol.steps{list-style:none;counter-reset:s;padding:0;margin:0}
ol.steps li{counter-increment:s;position:relative;padding:14px 18px 14px 58px;background:var(--panel);
  border:1px solid var(--line);border-radius:var(--r);margin-bottom:10px}
ol.steps li::before{content:counter(s);position:absolute;left:16px;top:14px;width:26px;height:26px;
  border-radius:50%;background:var(--panel2);border:1px solid var(--line2);color:var(--acc);
  display:flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:700;font-family:var(--mono)}
ol.steps li h4{margin:0 0 5px;font-size:15px}
ol.steps li p{margin:0;color:var(--tx2);font-size:14px}

.risk{border-left:3px solid var(--bad)}
.risk.medium{border-left-color:var(--warn)}
.risk.resolved{border-left-color:var(--good)}
.risk.low{border-left-color:var(--tx3)}
.risk .sev{font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:var(--bad)}
.risk.medium .sev{color:var(--warn)}
.risk.resolved .sev{color:var(--good)}
.risk.low .sev{color:var(--tx3)}

ul.plain{margin:0;padding-left:20px;color:var(--tx2)}
ul.plain li{margin-bottom:6px}

.anchor{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:12px 14px;
  margin-bottom:10px;font-family:var(--mono);font-size:12.5px;line-height:1.6}
.anchor .moved{color:var(--warn)}
.anchor .now{color:var(--good)}
.anchor .was{color:var(--tx3)}
.anchor .arrow{color:var(--tx3);padding:0 6px}

.rules{list-style:none;padding:0;margin:0}
.rules li{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:14px 18px;margin-bottom:10px}
.rules li b{display:block;margin-bottom:4px}
.rules li span{color:var(--tx2);font-size:14px}

.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:18px}
.fact{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.fact .k{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--tx3);font-weight:700}
.fact .v{font-size:19px;font-weight:650;margin-top:3px;font-family:var(--mono)}
.fact .v.ok{color:var(--good)} .fact .v.no{color:var(--bad)} .fact .v.warn{color:var(--warn)}

footer{margin-top:64px;padding-top:20px;border-top:1px solid var(--line);color:var(--tx3);font-size:13px}
footer code{font-size:12px}
"""

JS = r"""
(function(){
  var root=document.documentElement, k='enact-status-theme';
  var saved=null; try{saved=localStorage.getItem(k)}catch(e){}
  if(saved){root.setAttribute('data-theme',saved)}
  else if(window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches){
    root.setAttribute('data-theme','light');
  }
  var b=document.getElementById('theme');
  if(b){b.addEventListener('click',function(){
    var cur=root.getAttribute('data-theme')==='light'?'dark':'light';
    root.setAttribute('data-theme',cur);
    try{localStorage.setItem(k,cur)}catch(e){}
    b.textContent=cur==='light'?'Dark':'Light';
  })}
})();
"""


def esc(text) -> str:
    return html.escape(str(text))


def code(text) -> str:
    return f"<code>{esc(text)}</code>"


def render() -> str:
    d = D
    derived = d.get("derived", {})
    out = []
    add = out.append

    add("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    add("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    add(f"<title>{esc(d['question'])}</title>")
    add(f"<style>{CSS}</style></head><body>")

    # header
    add("<header class='top'><div class='wrap'>")
    add("<div class='brand'><h1>Enact — status &amp; upstream sync</h1>")
    add(f"<span class='sub'>{esc(d['generated'])}</span></div>")
    add("<button class='tbtn' id='theme'>Light</button>")
    add("</div></header>")

    add("<div class='wrap'>")

    # hero
    add("<div class='hero'>")
    add(f"<h2>{esc(d['question'])}</h2>")
    add(f"<p class='lede'>{esc(d['headline'])}</p>")
    add(f"<div class='verdict'><b>Verdict.</b> {esc(d['verdict'])}</div>")
    add("</div>")

    # where we stand
    add("<section><h3>Where we stand</h3>")
    add("<p class='note'>Two repositories, both public. The product side is a fork of zeroclaw; "
        "the workspace side holds the review and the host bridge.</p>")
    add("<div class='grid2'>")
    for repo in d["repos"]:
        kind = repo.get("state_kind", "good")
        pill = {"good": "good", "warn": "warn", "bad": "bad"}.get(kind, "info")
        label = {"good": "in sync", "warn": "needs attention", "bad": "blocked"}.get(kind, kind)
        add("<div class='card'>")
        add(f"<h4><a href='{esc(repo['url'])}'>{esc(repo['name'])}</a>"
            f"<span class='pill {pill}'>{esc(label)}</span></h4>")
        add(f"<p><b>{esc(repo['role'])}</b></p>")
        add(f"<p>{esc(repo['state'])}</p>")
        add(f"<p>{esc(repo['detail'])}</p>")
        add("</div>")
    add("</div></section>")

    # roadmap
    add("<section><h3>The roadmap</h3>")
    add("<p class='note'>All five phases of the tool-surface review are implemented, "
        "committed and verified in the fork.</p>")
    add("<table><thead><tr><th>Phase</th><th>Title</th><th>What landed</th><th>State</th></tr></thead><tbody>")
    for phase in d["roadmap"]:
        add(f"<tr><td class='mono'>{esc(phase['phase'])}</td><td><b>{esc(phase['title'])}</b></td>")
        add(f"<td>{esc(phase['detail'])}</td><td><span class='pill good'>landed</span></td></tr>")
    add("</tbody></table></section>")

    # verification
    add("<section><h3>Evidence</h3>")
    add("<p class='note'>What was actually run, and what it said.</p>")
    add("<table><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>")
    for item in d["verification"]:
        pill = item.get("state", "good")
        add(f"<tr><td>{esc(item['check'])}</td>"
            f"<td class='mono'><span class='pill {pill}'>{esc(item['result'])}</span></td></tr>")
    add("</tbody></table>")
    add(f"<p class='note' style='margin-top:12px'>{esc(d['verification_note'])}</p>")
    add("</section>")

    # the triage
    t = d["triage"]
    add("<section><h3>The triage</h3>")
    add(f"<p class='note'>{esc(t['headline'])}</p>")
    add(f"<p class='note'>{esc(t['method'])}</p>")
    add("<div class='facts'>")
    for key, value, cls in (
        ("Failures before", t["before"], "bad"),
        ("Failures after", t["after"], "good"),
    ):
        add(f"<div class='fact'><div class='k'>{esc(key)}</div>"
            f"<div class='v {cls}'>{esc(value)}</div></div>")
    add("</div>")
    add("<table><thead><tr><th>Test</th><th>Pristine upstream</th><th>The fork</th>"
        "<th>Cause and fix</th></tr></thead><tbody>")
    for row in t["rows"]:
        state = row.get("state", "good")
        pill = {"fixed": "good", "inherited": "warn"}.get(state, state)
        label = {"fixed": "fixed here", "inherited": "inherited"}.get(state, state)
        cause = row["cause"]
        if row.get("fix"):
            cause = f"{cause}<br><span class='note'>{esc(row['fix'])}</span>"
        add(f"<tr><td class='mono'>{esc(row['test'])}</td>"
            f"<td class='mono'>{esc(row['upstream'])}</td>"
            f"<td class='mono'><span class='pill {pill}'>{esc(label)}</span></td>"
            f"<td>{cause}</td></tr>")
    add("</tbody></table>")
    add(f"<p class='note' style='margin-top:12px'>{esc(t['note'])}</p>")
    add("</section>")

    # the sync
    s = d["sync"]
    add("<section><h3>The pending sync</h3>")
    add(f"<p class='note'>{esc(s['pending_commits'])} upstream commits are pending against "
        f"<code>upstream/master</code> at <code>{esc(s['upstream_head'])}</code>. "
        "The merge was rehearsed in a scratch worktree and is measured, not estimated.</p>")

    facts = [
        ("Pending commits", s["pending_commits"], "warn"),
        ("Merge conflicts", s["conflicts"], "good"),
        ("Files changed", s["files_changed"], ""),
        ("Lines", f"+{s['insertions']:,} / −{s['deletions']:,}", ""),
        ("New crates", len(s["new_crates"]), "warn"),
        ("Version", "0.9.0", "warn"),
    ]
    add("<div class='facts'>")
    for key, value, cls in facts:
        add(f"<div class='fact'><div class='k'>{esc(key)}</div>"
            f"<div class='v {cls}'>{esc(value)}</div></div>")
    add("</div>")

    add("<table><thead><tr><th>Fact</th><th>Value</th></tr></thead><tbody>")
    rows = [
        ("Upstream head", f"{s['upstream_head']} — {s['upstream_head_subject']}"),
        ("Merge base", s["merge_base"]),
        ("Fork core currently matches", f"{s['fork_core_matches']} — {s['fork_core_subject']}"),
        ("New crates", ", ".join(f"<code>{esc(c)}</code>" for c in s["new_crates"])),
        ("Version change", s["version_change"]),
        ("Cargo.lock", s["cargo_lock"]),
        ("Tool inventory", s["inventory"]),
    ]
    for key, value in rows:
        add(f"<tr><td><b>{esc(key)}</b></td><td>{value}</td></tr>")
    add("</tbody></table></section>")

    # anchors
    a = d["anchors"]
    add("<section><h3>Overlay anchors</h3>")
    add(f"<p class='note'>{esc(a['method'])} "
        f"{a['checked']} anchors checked &middot; <b style='color:var(--warn)'>{a['broken']} broken</b> "
        f"across {a['files']} files. {esc(a['surviving'])}</p>")
    for item in a["items"]:
        add("<div class='anchor'>")
        add(f"<div class='was'>{esc(item['file'])}</div>")
        add(f"<div>{esc(item['anchor'])}</div>")
        add(f"<div class='was'>was: {esc(item['was'])}</div>")
        add(f"<div><span class='arrow'>&rarr;</span><span class='now'>{esc(item['now'])}</span></div>")
        add(f"<div class='moved'>{esc(item['why'])}</div>")
        add("</div>")
    add("</section>")

    # hidden risks
    add("<section><h3>What the anchor count cannot see</h3>")
    add("<p class='note'>These are the real constraints. Each one is a compile or test "
        "failure that a text-match check passes straight through.</p>")
    for risk in d["hidden_risks"]:
        sev = risk.get("severity", "medium")
        add(f"<div class='card risk {esc(sev)}'>")
        add(f"<div class='sev'>{esc(sev)}</div>")
        add(f"<h4>{esc(risk['title'])}</h4>")
        add(f"<p>{esc(risk['detail'])}</p>")
        add("</div>")
    add("</section>")

    # plan
    add("<section><h3>The plan</h3>")
    add("<p class='note'>Follow upstream's structure — do not reshape its RPC types. "
        "Re-point the overlay onto the protocol crate and satisfy the two "
        "exhaustiveness constraints upstream imposes on its own method set.</p>")
    add("<ol class='steps'>")
    for step in d["plan"]:
        add(f"<li><h4>{esc(step['title'])}</h4><p>{esc(step['detail'])}</p></li>")
    add("</ol></section>")

    # rules
    add("<section><h3>Working rules</h3>")
    add("<ul class='rules'>")
    for rule in d["rules"]:
        add(f"<li><b>{esc(rule['rule'])}</b><span>{esc(rule['detail'])}</span></li>")
    add("</ul></section>")

    # open
    add("<section><h3>Not done yet</h3>")
    add("<p class='note'>What this report does not claim.</p>")
    add("<div class='card'><ul class='plain'>")
    for item in d["open"]:
        add(f"<li>{esc(item)}</li>")
    add("</ul></div>")
    add("</section>")

    # derived facts
    if derived:
        add("<section><h3>Re-derived from the tree</h3>")
        add("<p class='note'>Facts the report re-reads from the repositories at build "
            "time, so it cannot drift from what it describes.</p>")
        add("<table><thead><tr><th>Fact</th><th>Value</th></tr></thead><tbody>")
        labels = {
            "enact_agent_head": "enact-agent HEAD",
            "enact_agent_branch": "enact-agent branch",
            "enact_agent_clean": "enact-agent working tree clean",
            "upstream_head": "upstream/master head",
            "upstream_pending": "upstream commits pending",
            "core_matches": "fork core matches 06765b1e6",
            "release_pinned_base": "release.json pinned base",
            "release_gate_core_match": "documented release-gate core check passes",
        }
        for key, value in derived.items():
            label = labels.get(key, key)
            if isinstance(value, bool):
                shown = "yes" if value else "no"
                pill = "good" if value else "bad"
                add(f"<tr><td><b>{esc(label)}</b></td>"
                    f"<td><span class='pill {pill}'>{esc(shown)}</span></td></tr>")
            else:
                add(f"<tr><td><b>{esc(label)}</b></td><td class='mono'>{esc(value)}</td></tr>")
        add("</tbody></table></section>")

    add("<footer>")
    add("Generated by <code>build_status.py</code> &rarr; <code>status.json</code> &rarr; "
        "<code>render_status.py</code>. Facts are re-derived from the working tree at "
        "build time; the analysis is curated in <code>build_status.py</code>.")
    add("</footer>")

    add("</div>")
    add(f"<script>{JS}</script></body></html>")
    return "".join(out)


def main() -> None:
    out = os.path.join(ROOT, "enact-sync-status.html")
    with open(out, "w") as handle:
        handle.write(render())
    print(f"wrote {out} {os.path.getsize(out)} bytes")


if __name__ == "__main__":
    main()
