"""Visual parity harness: drive the analyst reference and Earth Buddy through the same states, then diff them.

For each state it saves both screenshots and a pixel diff, and for each named component it records the bounding box
and the computed styles on both sides. report.json holds every number; report.md is the per-component table.

    uv pip install --python .venv -r tools/parity/requirements.txt
    .venv/bin/python -m playwright install chromium-headless-shell
    EB_PORT=8250 .venv/bin/python run.py &
    .venv/bin/python tools/parity/parity.py --out /tmp/parity            # captures both sides
    .venv/bin/python tools/parity/parity.py --out /tmp/parity --reuse-ref  # keeps the saved reference capture

Positions: x is measured from the parent component (or the viewport), y from the bottom of the `after` component
when one is named, else from the parent (or the viewport). A component passes when every style matches and every
delta is at most TOLERANCE px. When its text differs between the two sides, a size or position delta is reported as
"content" instead of a failure, because the two apps compute different numbers and words.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageOps
from playwright.sync_api import sync_playwright

QUESTION = "How is temperature changing in Phnom Penh?"
TABS = ["Trend", "Seasonal cycle", "Residual", "Where"]
TAB_TOP = 420
TOLERANCE = 2
DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}
ANSWER_TIMEOUT = 240_000

SIDES = {
    "ref": {
        "url": "https://earth-analyst.vercel.app/",
        "ready": "#app .chip",
        "input": "#askInput",
        "answered": "#app .mode",
        "after": ["#askChart svg"],
        "tab": "#app section.card > .seg > button",
        "chart": "#app section.card > .seg + div svg",
        "map": "#askMap .leaflet-tile-loaded",
    },
    "ours": {
        "url": "http://127.0.0.1:8250/",
        "ready": "#thread .chip",
        "input": "#ask-text",
        "answered": "#thread .headline",
        "after": ["#thread .short:not(.busy)", "#thread .answer-card svg"],
        "tab": "#thread .answer-card .tabs > button",
        "chart": "#thread .answer-card .tabs + div svg",
        "map": "#thread .answer-card .maplibregl-canvas",
    },
}

# name, reference selector, our selector, parent, after
COMPONENTS = [
    ("sidebar", "aside.sidebar", "#side", None, None),
    ("brand", "aside.sidebar .brand", "#side .brand", "sidebar", None),
    ("new-analysis", "#newBtn", "#new", "sidebar", "brand"),
    ("topics-header", 'details[data-sect="topics"] > summary', "#topics-box > summary", "sidebar", "new-analysis"),
    ("topic-list", ".topics", "#topics-box .topics", "sidebar", "topics-header"),
    ("topic-item", ".topics > details:first-child > summary", "#topics-box .topic > summary", "topic-list", None),
    ("sources-row", 'details[data-sect="sources"] > summary', "#sources-box > summary", "sidebar", "topic-list"),
    ("header", "header.top", "#top", None, None),
    ("region-button", "#regionBtn", "#region-btn", "header", None),
    ("title", "#app h1", "#thread h1", None, None),
    ("intro", "#app .lede", "#thread .lede", None, "title"),
    ("chips", "#app .chips", "#thread .chips", None, "intro"),
    ("chip", "#app .chip", "#thread .chip", "chips", None),
    ("bubble", "#app .bubble", "#thread .bubble", None, "intro"),
    ("who", "#app .thread .eyebrow", "#thread .who", None, "bubble"),
    ("headline", "#app .thread .answer", "#thread .headline", None, "who"),
    ("body", "#app .explain.lead", "#thread .short", None, "headline"),
    ("about-data", "#app .datanote", "#thread .about-data", None, "body"),
    ("tell-more", "#app .more > summary", "#thread .more > summary", None, "about-data"),
    ("mode", "#app .mode", "#thread .mode", None, "tell-more"),
    ("card", "#app section.card", "#thread .answer-card", None, "mode"),
    ("size-card", "#app .insight > .ibox:nth-child(1)", "#thread .size-card", "card", None),
    ("size-title", "#app .insight > .ibox:nth-child(1) .ititle", "#thread .size-card .ititle", "size-card", None),
    ("size-say", "#app .insight > .ibox:nth-child(1) .isay", "#thread .size-card .isay", "size-card", "size-title"),
    ("size-bar", "#app .irange", "#thread .size-card .irange", "size-card", "size-say"),
    ("sure-card", "#app .insight > .ibox:nth-child(2)", "#thread .sure-card", "card", None),
    ("sure-title", "#app .insight > .ibox:nth-child(2) .ititle", "#thread .sure-card .ititle", "sure-card", None),
    ("sure-say", "#app .insight > .ibox:nth-child(2) .isay", "#thread .sure-card .isay", "sure-card", "sure-title"),
    ("sure-scale", "#app .iscale", "#thread .sure-card .iscale", "sure-card", "sure-say"),
    ("coin", "#app .icoin i", "#thread .sure-card .icoin i", "sure-card", "sure-scale"),
    ("picture-label", "#app section.card > .k", "#thread .answer-card .pic-label", "card", "size-card"),
    ("tabs", "#app section.card > .seg", "#thread .answer-card .tabs", "card", "picture-label"),
    ("chart-area", "#app section.card > .seg + div", "#thread .answer-card .tabs + div", "card", "tabs"),
    ("legend", "#app section.card > .legend", "#thread .answer-card .legend", "card", "chart-area"),
    ("stats", "#app section.card > details.stats:not(.method) > summary", "#thread .answer-card details.numbers > summary", "card", "legend"),
    ("method", "#app section.card > details.method > summary", "#thread .answer-card details.method > summary", "card", "stats"),
    ("composer", "#askForm", "#composer .composer-row", None, None),
    ("composer-input", "#askInput", "#ask-text", "composer", None),
    ("send", "#askForm button", "#ask-go", "composer", None),
    ("footer", ".asknote", "#composer .foot", None, "composer"),
]

STYLE_PROPS = ["fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing", "textTransform", "color",
               "backgroundColor", "borderTopLeftRadius", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
               "rowGap", "columnGap"]

MEASURE_JS = """([sel, props]) => {
  const out = {};
  for (const [name, s] of Object.entries(sel)) {
    const el = document.querySelector(s);
    if (!el) { out[name] = null; continue; }
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    out[name] = {
      rect: [r.x, r.y, r.width, r.height].map(v => Math.round(v * 10) / 10),
      visible: r.width > 0 && r.height > 0 && cs.visibility !== "hidden",
      text: (el.innerText || el.value || el.placeholder || "").replace(/\\s+/g, " ").trim().slice(0, 140),
      style: Object.fromEntries(props.map(p => [p, cs[p]])),
    };
  }
  return out;
}"""


def measure(page, side):
    sel = {name: (ref if side == "ref" else ours) for name, ref, ours, _, _ in COMPONENTS}
    return page.evaluate(MEASURE_JS, [sel, STYLE_PROPS])


def settle(page, ms=600):
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(ms)


def shoot(page, side, state, out, data, full=False):
    d = out / state
    d.mkdir(parents=True, exist_ok=True)
    data[state] = {"scroll": page.evaluate("window.scrollY"), "components": measure(page, side)}
    page.screenshot(path=str(d / f"{side}.png"), full_page=full)


def capture(browser, side, out):
    cfg, data = SIDES[side], {}
    page = browser.new_page(viewport=DESKTOP)
    page.goto(cfg["url"], wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_selector(cfg["ready"], timeout=60_000)
    settle(page)
    shoot(page, side, "ask", out, data)

    page.fill(cfg["input"], QUESTION)
    page.press(cfg["input"], "Enter")
    page.wait_for_selector(cfg["answered"], timeout=ANSWER_TIMEOUT)
    for s in cfg["after"]:
        try:
            page.wait_for_selector(s, timeout=30_000)
        except Exception:
            data.setdefault("_notes", []).append(f"never appeared: {s}")
    settle(page, 1500)
    page.evaluate("window.scrollTo(0, 0)")
    settle(page)
    shoot(page, side, "answer", out, data)
    shoot(page, side, "full", out, data, full=True)

    for tab in TABS:
        state = "tab-" + tab.split()[0].lower()
        button = page.locator(cfg["tab"], has_text=tab)
        if not button.count():
            data[state] = {"missing": f"no {tab!r} tab"}
            continue
        button.first.click()
        try:
            page.wait_for_selector(cfg["map"] if tab == "Where" else cfg["chart"], timeout=ANSWER_TIMEOUT)
        except Exception as err:
            data[state] = {"missing": f"{tab!r} tab never drew: {err}"}
            continue
        settle(page, 3000 if tab == "Where" else 800)
        page.evaluate("""([s, top]) => { const el = document.querySelector(s);
                          if (el) window.scrollBy(0, el.getBoundingClientRect().top - top); }""",
                      [cfg["tab"].rsplit(" > ", 1)[0], TAB_TOP])
        settle(page)
        shoot(page, side, state, out, data)
    page.close()

    page = browser.new_page(viewport=PHONE)
    page.goto(cfg["url"], wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_selector(cfg["ready"], timeout=60_000)
    settle(page)
    shoot(page, side, "phone-ask", out, data)
    page.close()
    return data


def px(v):
    return float(v[:-2]) if isinstance(v, str) and v.endswith("px") else None


def same_style(prop, a, b):
    if prop == "fontFamily":
        first = lambda f: f.split(",")[0].strip().strip("\"'").lower()
        return first(a) == first(b)
    if prop == "letterSpacing":
        a, b = ("0px" if v == "normal" else v for v in (a, b))
    pa, pb = px(a), px(b)
    if pa is not None and pb is not None:
        return abs(pa - pb) <= 0.5
    return a == b


def placed(comps, name, parent, after):
    x, y, w, h = comps[name]["rect"]
    p = comps.get(parent) if parent else None
    a = comps.get(after) if after else None
    if p:
        x -= p["rect"][0]
    if a:
        y -= a["rect"][1] + a["rect"][3]
    elif p:
        y -= p["rect"][1]
    return x, y, w, h


def compare_state(ref, ours):
    rows = []
    for name, _, _, parent, after in COMPONENTS:
        r, o = ref["components"].get(name), ours["components"].get(name)
        if r is None and o is None:
            continue
        row = {"component": name}
        if r is None or o is None:
            row.update(verdict="missing", side="ours" if o is None else "ref")
            rows.append(row)
            continue
        rc = ref["components"]
        oc = ours["components"]
        rp, op = (parent if rc.get(parent) and oc.get(parent) else None), (after if rc.get(after) and oc.get(after) else None)
        rx, ry, rw, rh = placed(rc, name, rp, op)
        ox, oy, ow, oh = placed(oc, name, rp, op)
        delta = {"dx": round(ox - rx, 1), "dy": round(oy - ry, 1), "dw": round(ow - rw, 1), "dh": round(oh - rh, 1)}
        styles = {p: [r["style"][p], o["style"][p]] for p in STYLE_PROPS if not same_style(p, r["style"][p], o["style"][p])}
        worst = max(abs(v) for v in delta.values())
        text_same = r["text"] == o["text"]
        verdict = ("style" if styles else "pass" if worst <= TOLERANCE else "geometry" if text_same else "content")
        row.update(delta=delta, worst=worst, styles=styles, text_same=text_same, verdict=verdict,
                   text=[r["text"], o["text"]], visible=[r["visible"], o["visible"]])
        rows.append(row)
    return rows


def pixel_diff(d):
    a, b = Image.open(d / "ref.png").convert("RGB"), Image.open(d / "ours.png").convert("RGB")
    w, h = min(a.width, b.width), min(a.height, b.height)
    a, b = a.crop((0, 0, w, h)), b.crop((0, 0, w, h))
    mask = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 24 else 0)
    base = ImageOps.grayscale(b).point(lambda v: 160 + v * 95 // 255).convert("RGB")
    base.paste(Image.new("RGB", (w, h), (220, 30, 30)), mask=mask)
    base.save(d / "diff.png")
    changed = mask.histogram()[255]
    return {"size_ref": list(Image.open(d / "ref.png").size), "size_ours": list(Image.open(d / "ours.png").size),
            "diff_pct": round(100 * changed / (w * h), 2)}


def fmt_delta(row):
    if row["verdict"] == "missing":
        return f"missing on {row['side']}", "", ""
    d = row["delta"]
    geo = f"{d['dx']:+g} / {d['dy']:+g} / {d['dw']:+g} / {d['dh']:+g}"
    styles = "; ".join(f"{p}: {a} → {b}" for p, (a, b) in row["styles"].items())
    return geo, styles, "same" if row["text_same"] else "differs"


def write_report(out, ref, ours):
    states, summary = {}, {}
    for state in ref:
        if state.startswith("_"):
            continue
        if "missing" in ref[state] or "missing" in ours.get(state, {"missing": "not captured"}):
            states[state] = {"missing": {"ref": ref[state].get("missing"), "ours": ours.get(state, {}).get("missing")}}
            continue
        rows = compare_state(ref[state], ours[state])
        states[state] = {"pixels": pixel_diff(out / state), "components": rows}
        for row in rows:
            s = summary.setdefault(row["component"], {"states": {}, "worst": 0, "styles": {}})
            s["states"][state] = row["verdict"]
            s["worst"] = max(s["worst"], row.get("worst", 0) if row["verdict"] != "missing" else float("inf"))
            s["styles"].update({p: v for p, v in row.get("styles", {}).items()})
    (out / "report.json").write_text(json.dumps({"tolerance_px": TOLERANCE, "states": states, "summary": summary,
                                                 "ref": ref, "ours": ours}, indent=1, ensure_ascii=False, default=str))

    md = ["# Visual parity report", "",
          f"Reference {SIDES['ref']['url']} against ours {SIDES['ours']['url']}. Desktop {DESKTOP['width']}×{DESKTOP['height']}, "
          f"phone {PHONE['width']}×{PHONE['height']}. Tolerance {TOLERANCE} px.", "",
          "Verdicts: pass; style (a computed style differs); geometry (same text, box off by more than the tolerance); "
          "content (box off, but the text differs between the two apps); missing.", "",
          "## Per component", "", "| Component | Worst delta px | Verdict per state | Style mismatches (ref → ours) |", "|---|---|---|---|"]
    for name, _, _, _, _ in COMPONENTS:
        if name not in summary:
            continue
        s = summary[name]
        verdicts = ", ".join(f"{k}: {v}" for k, v in s["states"].items())
        styles = "; ".join(f"{p}: {a} → {b}" for p, (a, b) in s["styles"].items())
        md.append(f"| {name} | {s['worst']:g} | {verdicts} | {styles} |")
    for state, v in states.items():
        md += ["", f"## {state}", ""]
        if "missing" in v:
            md.append(f"Not compared: {v['missing']}")
            continue
        p = v["pixels"]
        md += [f"Pixels: {p['diff_pct']}% differ (ref {p['size_ref']}, ours {p['size_ours']}). "
               f"Images: `{state}/ref.png`, `{state}/ours.png`, `{state}/diff.png`.", "",
               "| Component | Verdict | dx / dy / dw / dh | Text | Style mismatches |", "|---|---|---|---|---|"]
        for row in v["components"]:
            geo, styles, text = fmt_delta(row)
            md.append(f"| {row['component']} | {row['verdict']} | {geo} | {text} | {styles} |")
    (out / "report.md").write_text("\n".join(md) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="/tmp/parity")
    ap.add_argument("--ours", default=SIDES["ours"]["url"])
    ap.add_argument("--ref", default=SIDES["ref"]["url"])
    ap.add_argument("--reuse-ref", action="store_true", help="reuse ref.json and the reference screenshots in --out")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    SIDES["ours"]["url"], SIDES["ref"]["url"] = args.ours, args.ref
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        if args.reuse_ref and (out / "ref.json").exists():
            ref = json.loads((out / "ref.json").read_text())
        else:
            ref = capture(browser, "ref", out)
            (out / "ref.json").write_text(json.dumps(ref, indent=1, ensure_ascii=False))
        ours = capture(browser, "ours", out)
        (out / "ours.json").write_text(json.dumps(ours, indent=1, ensure_ascii=False))
        browser.close()
    write_report(out, ref, ours)
    print((out / "report.md").read_text().split("\n## ask")[0])


if __name__ == "__main__":
    main()
