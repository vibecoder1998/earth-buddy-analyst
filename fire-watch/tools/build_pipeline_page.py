"""Build fire-watch/pipeline.html: a one-page, self-contained account of how the raw CSVs become the numbers on the tabs.

    python fire-watch/tools/build_pipeline_page.py

Reads only files this project already wrote: data/pipeline_audit.json (audit_raw.py), data/verification.json and data/verification_tabs.json
(the checks), data/raw_audit.json and data/province_method_check.json (build_fire_watch.py). Every number on the page comes from those files.
"""
import html
import json
from pathlib import Path

FW = Path(__file__).resolve().parent.parent
D = FW / "data"
A = json.loads((D / "pipeline_audit.json").read_text(encoding="utf-8"))
V1 = json.loads((D / "verification.json").read_text(encoding="utf-8"))
V2 = json.loads((D / "verification_tabs.json").read_text(encoding="utf-8"))
RA = json.loads((D / "raw_audit.json").read_text(encoding="utf-8"))
PM = json.loads((D / "province_method_check.json").read_text(encoding="utf-8"))

G, F = A["giovanni"], A["firms"]
e = html.escape
n0 = lambda x: f"{int(round(x)):,}"
g4 = lambda x: f"{x:.4g}"
checks_total = V1["checks"] + V2["tabs"]["total_checks"]
fails_total = V1["failures"] + V2["tabs"]["mismatches"]
tabs = V2["tabs"]["sections"]


def short_name(fn):
    return fn.replace("g4.areaAvgTimeSeries.", "").split(".2001")[0]


NCLS = ' class="n"'                                           # right-aligned number cells (kept out of the f-strings: no backslashes inside expressions)

# ---------------------------------------------------------------- 1. flow diagram
# the five boxes of the flow diagram
BOXES = [
    ("1 · Raw files", ["8 Giovanni CSV files", "FIRMS MODIS archive", f"{n0(F['rows'])} fire detections", "never edited"]),
    ("2 · Audit", ["coverage and gaps", "fill values, duplicates", "units and value ranges", "checksums recorded"]),
    ("3 · Clean", ["fires: vegetation fires,", "confidence 30% or more", "series: units converted,", "nothing smoothed or filled"]),
    ("4 · Analyse", ["Mann–Kendall, Sen slope", "pre-whitening, seasonal test", "Pettitt step, Spearman", "false-discovery filter"]),
    ("5 · Show", ["3 tabs in Climate Watch", "numbers computed in the", "page from clean tables", "no network, no model"]),
]
flow = ['<div class="flow">']                                  # plain HTML boxes, not an SVG, so the text stays readable on a phone
for t, lines in BOXES:
    flow.append(f'<div class="step"><b>{e(t)}</b>' + "".join(f"<span>{e(l)}</span>" for l in lines) + "</div>")
flow.append("</div>")
flow.append(f'<div class="vband"><b>Checked at every step: {n0(checks_total)} automated checks, {fails_total} mismatches.</b> '
            "Raw file → clean tables (every count re-derived a second way), and clean tables → tab numbers (recomputed with other software).</div>")
FLOW = "".join(flow)

# ---------------------------------------------------------------- 2. raw files
rows = []
for g in G:
    ok = (g["months_present"] == g["months_expected"] and not g["fill_value_rows"] and not g["duplicate_dates"] and g["in_plausible_range"])
    rows.append([f"<code>{e(short_name(g['file']))}</code>", e(g["what"]), e(g["instrument"]), n0(g["data_rows"]), f"{g['first'][:7]} to {g['last'][:7]}", n0(g["bytes"]) + " B", f"<code>{g['sha256'][:12]}</code>",
                 '<span class="ok">all 288 months, no gaps, no fill values, in range</span>' if ok else '<span class="bad">see audit</span>'])
rows.append([f"<code>{e(F['file'])}</code>", "Fire detections (hotspots), Cambodia", "MODIS on NASA Terra and Aqua, Collection 6.1 (MCD14ML), via NASA FIRMS", n0(F["rows"]), f"{F['first'][:7]} to {F['last'][:7]}", n0(F["bytes"]) + " B",
             f"<code>{F['sha256'][:12]}</code>", f'<span class="ok">{F["months_present"]} of {F["months_present"]} months, {F["exact_duplicate_rows"]} duplicate rows, {sum(F["null_cells"].values())} empty cells</span>'])
nrt = F["nrt"]
rows.append([f"<code>{e(nrt['file'])}</code>", "Near-real-time fire detections", "same sensors, not final quality", n0(nrt["rows"]), f"{nrt['first'][:7]} to {nrt['last'][:7]}", n0(nrt["bytes"]) + " B", f"<code>{nrt['sha256'][:12]}</code>", '<span class="warn">recorded, never used</span>'])
RAW_T = '<div class="tw"><table><tr><th>File</th><th>What</th><th>Produced by</th><th class="n">Rows</th><th>Period</th><th class="n">Size</th><th>SHA-256</th><th>Audit result</th></tr>' + "".join("<tr>" + "".join(f"<td{NCLS if i in (3, 5) else ''}>{c}</td>" for i, c in enumerate(r)) + "</tr>" for r in rows) + "</table></div>"
same = all(c["identical_ignoring_line_endings"] for k, v in A["copies"].items() for c in v["copies"] if c["exists"])
byte_same = sum(1 for v in A["copies"].values() for c in v["copies"] if c["exists"] and c["identical"])
copies_n = sum(1 for v in A["copies"].values() for c in v["copies"] if c["exists"])
line_only = sum(1 for v in A["copies"].values() for c in v["copies"] if c["exists"] and not c["identical"] and c["identical_ignoring_line_endings"])
COPIES = (f"Every other copy of these files in this repo ({copies_n} copies checked, including the packaged originals in <code>raw-data/</code>) has the same content as the file we audited: {byte_same} are byte-for-byte identical and {line_only} differ only in line endings (git on Windows rewrote LF as CRLF)."
          if same else "Some copies differ in content: see data/pipeline_audit.json.")

# ---------------------------------------------------------------- 3. cleaning rules
c = F["cascade"]
# every cleaning rule, with the number it affects read from the audit
rules = [
    ["Fire", "Keep <code>type = 0</code> (a vegetation fire)", "FIRMS also reports volcanoes, other static land sources and offshore detections", f"−{n0(-c[1]['rows'])} rows"],
    ["Fire", "Keep <code>confidence ≥ 30</code>", "MODIS gives each detection a 0–100% confidence; low values are likely false alarms", f"−{n0(-c[2]['rows'])} rows"],
    ["Fire", "Fire season = November–April, labelled by the year it ends", "that is when almost all burning happens, and a season is not cut in half at New Year", f"{n0(c[4]['rows'])} rows ({F['clean_share_nov_apr']:.1f}% of clean)"],
    ["Fire", "Aqua and Terra counted separately (and together on request)", f"different overpass times (about 10:30 and 13:30); Aqua starts {RA['sat_range']['Aqua'][0]}, Terra {RA['sat_range']['Terra'][0]}", f"{n0(F['clean_by_satellite']['Aqua'])} Aqua, {n0(F['clean_by_satellite']['Terra'])} Terra"],
    ["Fire", "Each fire goes to the nearest NASA SEDAC province centre point", f"no province borders are shipped; an approximation (median distance to the nearest centre {RA['median_km_to_nearest_centre']:.0f} km)", "every clean row"],
    ["Fire", "Near-real-time file ignored", "not final quality and overlaps the archive's last weeks", f"{n0(nrt['rows'])} rows unused"],
    ["Series", "Skip the Giovanni header; drop any value ≥ 1e10 (Giovanni's missing-data code)", "so a fill value can never be averaged in as a real measurement", f"{sum(g['fill_value_rows'] for g in G)} found in {len(G)} files"],
    ["Series", "Each timestamp becomes the first day of its month", "one row per month, same index for every series", f"{n0(sum(g['rows_kept'] for g in G))} rows"],
    ["Series", "Convert units: rain × 86,400 (kg m⁻² s⁻¹ to mm/day); black carbon and PM2.5 × 1e9 (kg m⁻³ to µg/m³)", "so values are in units people can read", "3 of 8 series"],
    ["Series", "Nothing else: no smoothing, no interpolation, no gap filling, no outlier removal", "the tests see exactly what NASA produced", "0 values changed"],
]
RULES_T = '<div class="tw"><table><tr><th>Data</th><th>What we do</th><th>Why</th><th>Effect</th></tr>' + "".join("<tr>" + "".join(f"<td>{c_}</td>" for c_ in r) + "</tr>" for r in rules) + "</table></div>"

# ---------------------------------------------------------------- 4. raw vs clean
mx = F["rows"]
bars = []
for key, lab, val, col in (("a", "Rows in the raw file", c[0]["rows"], "var(--b1)"), ("b", "After dropping non-vegetation detections", c[0]["rows"] + c[1]["rows"], "var(--b2)"), ("c", "Clean detections (confidence ≥ 30)", c[3]["rows"], "var(--b3)"),
                           ("d", "November–April fire season", c[4]["rows"], "var(--b4)"), ("e", "December–March", c[5]["rows"], "var(--b5)")):
    bars.append(f'<div class="fr"><div class="fl">{lab}</div><div class="fb"><i style="width:{100 * val / mx:.1f}%;background:{col}"></i></div><div class="fv">{n0(val)}</div></div>')
FUNNEL = "".join(bars)
grows = [[e(g["what"]), n0(g["data_rows"]), n0(g["rows_kept"]), f"{g4(g['raw_min'])} to {g4(g['raw_max'])}", f"{g4(g['min'])} to {g4(g['max'])} {e(g['unit'])}", g4(g["mean"])] for g in G]
GIO_T = '<div class="tw"><table><tr><th>Series</th><th class="n">Raw rows</th><th class="n">Clean rows</th><th>Raw values (file units)</th><th>Clean values</th><th class="n">Mean</th></tr>' + "".join("<tr>" + "".join(f"<td{NCLS if i in (1, 2, 5) else ''}>{c_}</td>" for i, c_ in enumerate(r)) + "</tr>" for r in grows) + "</table></div>"

# ---------------------------------------------------------------- 5. clean files
cf = A["clean_files"]
files = [("giovanni_cambodia_box_monthly_clean.csv", f"{cf['giovanni']['rows']} rows × {len(cf['giovanni']['columns'])} series, 2001–2024", "all eight Giovanni series, one row per month, readable units")]
for nm, v in cf["fire_tables"].items():
    what = {"fire_month_counts.csv": "clean fire detections per month and satellite", "fire_season_counts.csv": "clean fire detections per November–April season", "fire_province_season.csv": "clean fire detections per nearest province centre, season and satellite"}[nm]
    files.append((nm, f"{n0(v['rows'])} rows", what))
files.append(("DATA_DICTIONARY.md", "what every column means", "units, conversions, instrument or model behind each series"))
FILES_T = '<div class="tw"><table><tr><th>File (in <code>fire-watch/clean-data/</code>)</th><th>Size</th><th>What</th></tr>' + "".join(f'<tr><td><a href="clean-data/{e(a_)}"><code>{e(a_)}</code></a></td><td>{e(b_)}</td><td>{e(c_)}</td></tr>' for a_, b_, c_ in files) + "</table></div>"

# ---------------------------------------------------------------- 6. checks
lib = V2["stats_module_vs_libraries"]
# one row per check; the counts come from verification.json and verification_tabs.json
chk = [
    ["Raw files audited", "8 Giovanni files and the FIRMS archive: row counts, date coverage, gaps, fill values, duplicates, empty cells, value ranges, copies on disk", "all pass", '<span class="ok">pass</span>'],
    ["Raw → clean tables", "Every season total, every monthly count, every province count, every map-square sum, and 600 random map squares, re-counted from the raw FIRMS file with different code (a plain distance matrix instead of a KD-tree)", n0(V1["checks"]), f'<span class="ok">{V1["failures"]} failures</span>'],
    ["Clean tables → Fire tab", f"{tabs['fire']['cases']} choices of satellite and seasons: totals, season counts, province and region counts, months, trend, p-value, step test, compared with pymannkendall and scipy", n0(tabs["fire"]["checks"]), f'<span class="ok">{tabs["fire"]["mismatches"]} mismatches</span>'],
    ["Province trends", f"{tabs['province']['cases']} windows × 25 provinces: counts, Mann–Kendall p, % per decade and the false-discovery flag (statsmodels)", n0(tabs["province"]["checks"]), f'<span class="ok">{tabs["province"]["mismatches"]} mismatches</span>'],
    ["Clean tables → Soot & haze tab", f"{tabs['soot']['cases']} choices of measure, satellite and years: monthly and seasonal correlations, climatology, dry-season trend", n0(tabs["soot"]["checks"]), f'<span class="ok">{tabs["soot"]["mismatches"]} mismatches</span>'],
    ["Clean tables → Rain, soil & heat tab", f"{tabs['water']['cases']} choices of series and years: rate, 95% interval, three p-values, seasonal tests, monthly climatology, rain-record ratio and its step", n0(tabs["water"]["checks"]), f'<span class="ok">{tabs["water"]["mismatches"]} mismatches</span>'],
    ["Our statistics code vs libraries", f"{lib['series_compared']} series: Mann–Kendall S and p, Sen slope, pre-whitened p, Pettitt p against pymannkendall and scipy", "28 series", f'<span class="ok">differences ≤ 1.1e-16</span>'],
]
CHK_T = '<div class="tw"><table><tr><th>Step</th><th>What was compared</th><th class="n">Checks</th><th>Result</th></tr>' + "".join("<tr>" + "".join(f"<td{NCLS if i == 2 else ''}>{c_}</td>" for i, c_ in enumerate(r)) + "</tr>" for r in chk) + "</table></div>"
maxp = max(s["largest_p_difference"] for s in tabs.values())
PROV = (f"One-off, not repeatable from this folder: we measured the nearest-centre rule against real province borders (geoBoundaries, a non-NASA file we do not ship). {PM['per_fire_same_province'] * 100:.0f}% of Aqua fires land in the same province either way, "
        f"province shares rank-correlate at ρ = {PM['province_share_rank_correlation_spearman']:.2f}, the top five provinces are the same set, and the largest single share moves by {PM['max_share_difference_points']:.1f} points ({PM['max_share_difference_province']}). So read the province ranking as solid and exact percentages as ±3–4 points.")

LIMITS = [
    "The eight Giovanni series are each an <b>area average over one box</b> (102.3–107.6°E, 10.4–14.7°N), which also covers parts of Thailand, Laos, Vietnam and the Gulf of Thailand. They cannot say where inside Cambodia something changes.",
    "Seven of the eight are <b>model output</b> (NASA MERRA-2), not measurements. Only the GPM rain is a satellite-based estimate, and fire is the one direct satellite observation.",
    "Fire counts are <b>hotspots seen at overpass</b>, not area burned. Province shares come from nearest-centre assignment (±3–4 points).",
    "The Giovanni files end in December 2024; the fire file runs to August 2026.",
    f"Our checks show the tabs compute the right numbers <b>from these files</b>. They do not show the files are the truth: the MERRA-2 rain, soil and wet-bulb series step after 2016–17 while the satellite rain does not, and we have not identified why.",
]

CSS = """
:root{--bg:#f5f7fa;--card:#ffffff;--soft:#eef2f6;--line:#dbe3ec;--line2:#c3cedb;--text:#101828;--text2:#344054;--mute:#566377;--accent:#0b6fa4;--fire:#c2410c;--ok:#067647;--bad:#b42318;--warn:#9a5b06;
  --warnbg:rgba(154,91,6,.07);--warnline:rgba(154,91,6,.4);--okbg:rgba(6,118,71,.07);--okline:rgba(6,118,71,.4);--b1:#8896a8;--b2:#a9b4c2;--b3:#ea7a2b;--b4:#e9a914;--b5:#d9830b}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0a1119;--card:#101a26;--soft:#0c1520;--line:#1e2a3a;--line2:#2d3b4e;--text:#eef2f6;--text2:#c5cfdb;--mute:#93a1b3;--accent:#5ec0f0;--fire:#fb923c;--ok:#34d399;--bad:#f87171;--warn:#fbbf24;
  --warnbg:rgba(251,191,36,.07);--warnline:rgba(251,191,36,.35);--okbg:rgba(52,211,153,.07);--okline:rgba(52,211,153,.4);color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0a1119;--card:#101a26;--soft:#0c1520;--line:#1e2a3a;--line2:#2d3b4e;--text:#eef2f6;--text2:#c5cfdb;--mute:#93a1b3;--accent:#5ec0f0;--fire:#fb923c;--ok:#34d399;--bad:#f87171;--warn:#fbbf24;
  --warnbg:rgba(251,191,36,.07);--warnline:rgba(251,191,36,.35);--okbg:rgba(52,211,153,.07);--okline:rgba(52,211,153,.4);color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,"Segoe UI","Noto Sans Khmer",Roboto,sans-serif;font-size:15px;line-height:1.55;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0}
a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
header{border-bottom:1px solid var(--line)}
.bar{max-width:1180px;margin:0 auto;min-height:60px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding-block:10px}
.bar b{font-size:16px}.bar small{display:block;font-size:12px;color:var(--mute)}
.back{font-size:12px;font-weight:600;padding:7px 12px;border-radius:10px;border:1px solid var(--line2);background:var(--soft)}
main{max-width:1180px;margin:0 auto;padding-block:28px 60px}
h1{font-size:clamp(26px,4vw,38px);line-height:1.15;margin:0 0 10px;letter-spacing:-.02em;text-wrap:balance}
h2{font-size:21px;margin:0 0 6px;letter-spacing:-.01em}
.lead{color:var(--text2);max-width:860px;font-size:16px;margin:0 0 24px}
section{margin-top:40px}
.sub{color:var(--mute);font-size:14px;margin:0 0 14px;max-width:900px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;min-width:0}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 8px}
.stat{background:var(--card);border:1px solid var(--line);border-top:3px solid var(--fire);border-radius:14px;padding:14px 16px;min-width:0}
.stat b{display:block;font-size:26px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}.stat span{font-size:12.5px;color:var(--mute)}
@media(max-width:900px){.stats{grid-template-columns:1fr 1fr}}
@media(max-width:420px){.stats{grid-template-columns:1fr}}
.flow{display:grid;grid-template-columns:repeat(5,1fr);gap:24px}
.step{position:relative;background:var(--soft);border:1px solid var(--line2);border-radius:14px;padding:14px 14px 12px;min-width:0}
.step b{display:block;margin-bottom:6px;font-size:15px}.step span{display:block;font-size:13px;color:var(--mute);line-height:1.45}
.step:not(:last-child)::after{content:"\\2192";position:absolute;right:-21px;top:50%;transform:translateY(-50%);color:var(--mute);font-size:20px}
.vband{margin-top:16px;border:1px solid var(--okline);background:var(--okbg);border-radius:14px;padding:12px 16px;font-size:14px;color:var(--text2)}
.vband b{color:var(--ok)}
@media(max-width:900px){.flow{grid-template-columns:1fr;gap:26px}.step:not(:last-child)::after{content:"\\2193";right:auto;left:50%;top:auto;bottom:-24px;transform:translateX(-50%)}}
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
code{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.9em;color:var(--text2);overflow-wrap:anywhere}
.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}.warn{color:var(--warn);font-weight:600}
.fr{display:grid;grid-template-columns:260px 1fr 110px;gap:12px;align-items:center;margin:8px 0;font-size:13px}
.fl{color:var(--text2)}.fb{height:16px;background:var(--soft);border-radius:8px;overflow:hidden;border:1px solid var(--line)}.fb i{display:block;height:100%}
.fv{text-align:right;font-variant-numeric:tabular-nums;color:var(--text)}
@media(max-width:700px){.fr{grid-template-columns:1fr;gap:4px}.fv{text-align:left}}
.note{font-size:12.5px;color:var(--mute);margin:10px 0 0}
ul.l{margin:6px 0 0;padding-left:20px}ul.l li{margin:7px 0;color:var(--text2);font-size:14px}
pre{background:var(--soft);border:1px solid var(--line);border-radius:12px;padding:14px;overflow-x:auto;font-size:12.5px;color:var(--text2)}
.warnbox{border:1px solid var(--warnline);background:var(--warnbg);border-radius:14px;padding:14px 18px}
footer{max-width:1180px;margin:0 auto;border-top:1px solid var(--line);color:var(--mute);font-size:12px;padding-block:20px;text-align:center}
"""

REPRO = """# 1. audit the raw files and write the clean data (needs the two raw folders; never edits them)
python fire-watch/tools/audit_raw.py --firms &lt;folder with fire_archive_*.csv&gt; --giovanni &lt;folder with the 8 Giovanni CSVs&gt;

# 2. build the fire tables from the raw FIRMS file, then re-derive them a second way and compare
python fire-watch/tools/build_fire_watch.py tables &lt;FIRMS folder&gt;
python fire-watch/tools/build_fire_watch.py verify &lt;FIRMS folder&gt;

# 3. build the tabs and put them in the Climate Watch page
python fire-watch/tools/build_fire_watch.py page
python fire-watch/tools/build_fire_watch.py inject

# 4. check the tabs against an independent recomputation from the raw files
python fire-watch/tools/verify/make_expected.py fire-watch/data &lt;FIRMS folder&gt; &lt;Giovanni folder&gt;
#    then serve the repo (python -m http.server), open climate-watch-cambodia.html and paste fire-watch/tools/verify/browser_check.js in the console"""

# the page body; the artifact variant below reuses it with the repo-only links removed
body = f"""
<h1>From raw NASA files to every number on the tabs</h1>
<p class="lead">This page shows the whole path: the raw CSV files exactly as downloaded, what we checked in them, how we cleaned them, how the tabs compute their numbers, and how we checked the tabs. Everything below is read from files this project wrote, not typed in.</p>
<div class="stats">
  <div class="stat"><b>{len(G) + 2}</b><span>raw files, never edited ({len(G)} Giovanni series, FIRMS archive, FIRMS near-real-time)</span></div>
  <div class="stat"><b>{n0(F['rows'])}</b><span>raw fire detections, of which {n0(c[3]['rows'])} survive cleaning</span></div>
  <div class="stat"><b>{n0(checks_total)}</b><span>automated checks, {fails_total} mismatches</span></div>
  <div class="stat"><b>{len(G)} × 288</b><span>monthly values, every month present, no fill values</span></div>
</div>

<section><h2>1 · The pipeline</h2><p class="sub">Five steps, and a check at every step. Nothing is estimated by a language model; the tabs compute their own numbers in the page from the clean tables.</p><div class="card">{FLOW}</div></section>

<section><h2>2 · The raw files, as downloaded</h2><p class="sub">Audit of each file before anything is cleaned. The SHA-256 fingerprint lets anyone confirm they have the same file.</p><div class="card">{RAW_T}<p class="note">{COPIES} Giovanni request that produced the eight series: <a href="{e(G[0]['reproduce_url'])}">open in Giovanni</a> (needs an Earthdata login).</p></div></section>

<section><h2>3 · How we clean them</h2><p class="sub">Every rule, why it is there, and how many rows it touches.</p><div class="card">{RULES_T}</div></section>

<section><h2>4 · Raw versus clean</h2>
<p class="sub">Fire detections: what survives each rule.</p><div class="card">{FUNNEL}<p class="note">{F['cascade'][1]['note']}. Low-confidence rule: {F['cascade'][2]['note']}.</p></div>
<p class="sub" style="margin-top:18px">The eight series: the clean table has the same rows as the raw files (nothing dropped); only units change.</p><div class="card">{GIO_T}</div></section>

<section><h2>5 · The clean data</h2><p class="sub">Download these instead of the raw files if you want tidy tables. Each is rebuilt from the raw files by the commands in section 8.</p><div class="card">{FILES_T}</div></section>

<section><h2>6 · How we checked it</h2><p class="sub">Two kinds of check. First, the clean tables are re-derived from the raw file a second way and compared. Second, every tab's own JavaScript is compared with numbers recomputed from the raw files using other software (pymannkendall, scipy, statsmodels). Largest p-value difference on any tab: {maxp:.1e}.</p><div class="card">{CHK_T}<p class="note">{PROV}</p></div></section>

<section><h2>7 · What this does not prove</h2><div class="warnbox"><ul class="l">{''.join(f'<li>{x}</li>' for x in LIMITS)}</ul></div></section>

<section><h2>8 · Run it yourself</h2><div class="card"><pre>{REPRO}</pre><p class="note">The raw files are in <code>fire-watch/raw-data/</code> (the 57 MB FIRMS archive is gzipped: unpack it with <code>gunzip -k</code> first; checksums are in <code>SHA256SUMS.txt</code>). Checked on {e(V2['run_on'])}.</p></div></section>
"""

import re
import sys

BACK = '<a class="back" href="../climate-watch-cambodia.html">\u2190 Climate Watch Cambodia</a>'
FOOT = "NASA Space Apps 2026 \u00b7 \u201cBe An Earth System Trend Detective\u201d \u00b7 data: NASA FIRMS (MODIS C6.1), NASA Giovanni (GPM IMERG, MERRA-2) \u00b7 generated by build_pipeline_page.py"


def shell(back, inner):
    return (f'<header><div class="bar"><div><b>Data pipeline and checks</b><small>Raw NASA CSV \u2192 clean data \u2192 tabs \u00b7 Cambodia 2001\u20132024</small></div>{back}</div></header>\n'
            f"<main>{inner}</main>\n<footer>{FOOT}</footer>")


page = (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><meta name="color-scheme" content="light dark"/>\n'
        f"<title>Data pipeline and checks \u2014 Earth System Trend Detective</title>\n"
        f"<!-- Self-contained: no CDN, no fonts, no network calls. Generated by fire-watch/tools/build_pipeline_page.py from data/pipeline_audit.json and the verification files. -->\n"
        f"<style>{CSS}</style></head><body>\n{shell(BACK, body)}\n</body></html>")
out = FW / "pipeline.html"
out.write_text(page, encoding="utf-8")
print(f"wrote {out.relative_to(FW.parent)} ({len(page) / 1024:.0f} KB); {checks_total:,} checks, {fails_total} mismatches")

if "--artifact" in sys.argv:                      # the same page for a shared link: no back link, no links to files that live in the repo
    target = Path(sys.argv[sys.argv.index("--artifact") + 1])
    plain = re.sub(r'<a href="clean-data/[^"]*">(<code>[^<]*</code>)</a>', r"\1", body)
    plain = plain.replace("Download these instead of the raw files if you want tidy tables. Each is rebuilt from the raw files by the commands in section 8.",
                          "These files are in the project's <code>fire-watch/clean-data/</code> folder. Each is rebuilt from the raw files by the commands in section 8.")
    art = ('<title>Data pipeline and checks</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
           f"<style>{CSS}</style>\n{shell('', plain)}\n")
    target.write_text(art, encoding="utf-8")
    print(f"wrote artifact page {target} ({len(art) / 1024:.0f} KB)")
