"""Build the Fire Watch tables, the analysis panel and the Climate Watch tab entry.

Reads the repo's own data/. Writes only inside fire-watch/, except the `inject` stage, which rewrites two marked blocks in climate-watch-cambodia.html.

    python fire-watch/tools/build_fire_watch.py tables <folder with fire_archive_*.csv>   # needs the FIRMS download (raw CSV, ~57 MB)
    python fire-watch/tools/build_fire_watch.py page                                      # needs only fire-watch/data + the repo's data/
    python fire-watch/tools/build_fire_watch.py inject                                    # refresh the marked blocks in climate-watch-cambodia.html
    python fire-watch/tools/build_fire_watch.py verify <folder with fire_archive_*.csv>   # re-derive the tables from the raw CSV a second, independent way

NASA-only, to match docs/16-data-sources.md:
  * fires: MODIS Collection 6.1 active fire detections (MCD14ML), distributed by NASA FIRMS
  * black carbon: the repo's own data/giovanni/*BCSMASS*.csv (MERRA-2 M2TMNXAER v5.12.4 via Giovanni)
  * provinces: NASA SEDAC GPWv4 admin-unit centre points already in data/gazetteer.json. Each fire goes to the NEAREST
    province centre, which is an approximation (not exact borders).
  * cross-check: the repo's own data/v/fire.json (Earth Buddy's fire variable)
Regions are our own grouping of those 25 provinces (for readability); they are not an official or NASA classification.
"""
import base64
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
FW = HERE.parent                 # fire-watch/
REPO = FW.parent                 # repo root (read-only for this script)
DATA = FW / "data"
sys.path.insert(0, str(HERE))
import stats_tests as sx  # noqa: E402

CELL = 0.1                       # density-map square, degrees
SEASONS = list(range(2003, 2027))          # Nov-Apr seasons shown and selectable (tests default to 2003-2022)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NAME_FIX = {"Phnom Penh Municipality": "Phnom Penh", "Mondul Kiri": "Mondulkiri", "Ratanak Kiri": "Ratanakiri",
            "Otdar Meanchey": "Oddar Meanchey", "Tbong Khmum": "Tboung Khmum"}
REGIONS = [   # our own geographic grouping of the 25 provinces, for readability (not an official classification)
    ("ne", "North-East", ["Kratie", "Mondulkiri", "Ratanakiri", "Stung Treng"]),
    ("nw", "North & North-West", ["Preah Vihear", "Oddar Meanchey", "Banteay Meanchey", "Siem Reap", "Battambang", "Pailin"]),
    ("ts", "Tonle Sap & Centre", ["Kampong Thom", "Pursat", "Kampong Chhnang", "Kampong Cham", "Tboung Khmum"]),
    ("sw", "South-West & Coast", ["Kampong Speu", "Koh Kong", "Kampot", "Kep", "Preah Sihanouk"]),
    ("mk", "Mekong Plain", ["Kandal", "Phnom Penh", "Prey Veng", "Svay Rieng", "Takeo"]),
]



GRID_M2 = "0.5\u00b0 \u00d7 0.625\u00b0 (about 55 \u00d7 70 km)"
INSTR = {   # what produces each series; product names, titles and grids are the ones in the CSV headers
    "imerg": dict(label="GPM IMERG rain", short="GPM rain (satellite)", unit="mm/day", dec=2, zero=True, pattern="*GPM_3IMERGM*.csv", scale=1.0, kind="satellite-based estimate",
                  product="GPM_3IMERGM_07", title="Merged satellite-gauge precipitation estimate, Final Run (recommended for general use)", grid="0.1\u00b0 (about 10 km)", doi="10.5067/GPM/IMERG/3B-MONTH/07",
                  what="NASA's IMERG merges rain estimates from the passive-microwave sensors of the GPM satellite constellation, calibrated to the GPM Core Observatory's combined radar-and-radiometer product, and adjusts the result to monthly rain-gauge analyses (the Final Run).",
                  defn="Rain rate estimated from space and adjusted to rain gauges, averaged over the box. The most observation-based rain series in these files."),
    "m2rain": dict(label="MERRA-2 land rain", short="MERRA-2 rain (model)", unit="mm/day", dec=2, zero=True, pattern="*PRECTOTLAND*.csv", scale=86400.0, kind="model (reanalysis)",
                   product="M2TMNXLND v5.12.4 \u00b7 PRECTOTLAND", title="Total precipitation land, bias corrected", grid=GRID_M2, doi="10.5067/8S35XF81C28F",
                   what="MERRA-2 is NASA's atmospheric reanalysis: the GEOS-5 weather model run over many years and constrained by assimilated satellite and surface observations. This is the model's rain over land, \u201cbias corrected\u201d according to the file's title (the file does not say what it was corrected with). No instrument measures it directly.",
                   defn="Rain rate computed by the MERRA-2 model over land and bias-corrected, averaged over the box (converted from kg per m\u00b2 per second to mm per day)."),
    "soil": dict(label="Root-zone soil wetness", short="Soil wetness (model)", unit="fraction", dec=3, zero=False, pattern="*GWETROOT*.csv", scale=1.0, kind="model (land-surface model)",
                 product="M2TMNXLND v5.12.4 \u00b7 GWETROOT", title="Root zone soil wetness", grid=GRID_M2, doi="10.5067/8S35XF81C28F",
                 what="How full the top 100 cm of soil is, from 0 (dry) to 1 (saturated), computed by the Catchment land-surface model inside MERRA-2. Nothing in these files measures it directly.",
                 defn="Fraction of saturation of the top 100 cm of soil, computed by the MERRA-2 land model, averaged over the box."),
    "t2m": dict(label="2 m air temperature", short="Air temperature (model)", unit="\u00b0C", dec=2, zero=False, pattern="*T2M.*.csv", scale=1.0, kind="model (reanalysis)",
                product="M2TMNXSLV v5.12.4 \u00b7 T2M", title="2-meter air temperature", grid=GRID_M2, doi="10.5067/AP1B0BA5PD2K",
                what="Air temperature two metres above the ground from the MERRA-2 reanalysis: a model constrained by assimilated observations, not a thermometer record.",
                defn="Air temperature 2 m above the ground from the MERRA-2 reanalysis, averaged over the box."),
    "wet": dict(label="2 m wet-bulb temperature", short="Wet-bulb temperature (model)", unit="\u00b0C", dec=2, zero=False, pattern="*T2MWET*.csv", scale=1.0, kind="model (reanalysis)",
                product="M2TMNXSLV v5.12.4 \u00b7 T2MWET", title="2-meter wet bulb temperature", grid=GRID_M2, doi="10.5067/AP1B0BA5PD2K",
                what="The temperature a wet thermometer would read: it combines heat and humidity, so it tracks heat stress better than air temperature alone. Computed by MERRA-2.",
                defn="Wet-bulb temperature 2 m above the ground (heat and humidity together) from the MERRA-2 reanalysis, averaged over the box."),
}
AEROSOL_WHAT = {
    "bc": ("model (reanalysis, aerosol module)", "M2TMNXAER v5.12.4 \u00b7 BCSMASS", "Black Carbon Surface Mass Concentration",
           "Produced by the GOCART aerosol module inside MERRA-2's GEOS-5 model. Satellite aerosol optical depth (MODIS, AVHRR, MISR) and AERONET ground stations constrain the total aerosol; the split into black carbon and other types comes from the model, so black carbon is not measured directly."),
    "pm25": ("model (reanalysis, aerosol module)", "M2TMNXAER v5.12.4 \u00b7 TOTSMASS25", "Total Surface Mass Concentration - PM 2.5",
             "The model's total mass of aerosol particles smaller than 2.5 micrometres at the surface, all types together. Observations constrain total aerosol optical depth, not PM2.5 itself."),
    "aod": ("model, constrained by satellite and ground observations", "M2TMNXAER v5.12.4 \u00b7 TOTEXTTAU", "Total Aerosol Extinction AOT 550 nm",
            "How much light the aerosol in the whole air column blocks at 550 nm. This is the aerosol field MERRA-2 is directly constrained to match (satellite MODIS, AVHRR, MISR and AERONET observations), so it is the most observation-based of the three."),
}


def gpw_centres():
    g = json.loads((REPO / "data" / "gazetteer.json").read_text(encoding="utf-8"))
    rows = [r for r in g if r.get("iso3") == "KHM" and r.get("level") == 1]
    out = pd.DataFrame([{"province": NAME_FIX.get(r["name"].title(), r["name"].title()), "lat": r["lat"], "lon": r["lon"]} for r in rows])
    assert len(out) == 25, f"expected 25 Cambodian provinces in the gazetteer, found {len(out)}"
    region_of = {p: (k, label) for k, label, members in REGIONS for p in members}
    assert set(out.province) == set(region_of), f"region grouping does not match the 25 provinces: {set(out.province) ^ set(region_of)}"
    return out


def run_tests(years, values):
    x, yrs = np.asarray(values, float), np.asarray(years, float)
    n = len(x)
    mk = sx.mann_kendall(x)
    b, a = sx.sens_slope(x, yrs)
    mk_ar, r1, _ = sx.tfpw_mann_kendall(x)
    sig = bool(sx.ar1_is_significant(r1, n))
    p = mk_ar["p"] if sig else mk["p"]
    pet = sx.pettitt(x)
    verdict = ("increasing" if b > 0 else "decreasing") if p < 0.05 else ("borderline" if p < 0.10 else "no significant trend")
    return dict(n=int(n), mean=float(x.mean()), sd=float(x.std(ddof=1)), sen_per_decade=float(b * 10),
                pct_per_decade=float(100 * b * 10 / x.mean()) if x.mean() else None, p=float(p), p_raw=float(mk["p"]),
                memory_r1=float(r1), verdict=verdict, step_after=int(yrs[pet["index"]]), step_p=float(pet["p"]))


def clean_fires(raw):
    """Real vegetation fires (type 0) with confidence >= 30, plus calendar helpers. Season = Nov-Apr, labelled by the year it ends."""
    d = raw[(raw.type == 0) & (raw.confidence >= 30)].copy()
    d["date"] = pd.to_datetime(d.acq_date)
    d["year"], d["month"] = d.date.dt.year, d.date.dt.month
    d["season"] = d.year + (d.month >= 11).astype(int)
    return d


# ------------------------------------------------------------------------------------------------ tables
def build_tables(firms_dir):
    archive = next(Path(firms_dir).glob("fire_archive_*.csv"))
    raw = pd.read_csv(archive, usecols=["latitude", "longitude", "acq_date", "satellite", "confidence", "type"])
    d = clean_fires(raw)
    DATA.mkdir(parents=True, exist_ok=True)

    mc = d.groupby(["year", "month", "satellite"]).size().rename("detections").reset_index()
    mc.to_csv(DATA / "fire_month_counts.csv", index=False)

    ins = d[d.month.isin([11, 12, 1, 2, 3, 4])]
    sc = ins.pivot_table(index="season", columns="satellite", values="latitude", aggfunc="count", fill_value=0)
    sc.columns = [c.lower() for c in sc.columns]
    sc.to_csv(DATA / "fire_season_counts.csv")

    # nearest NASA SEDAC province centre (approximate), both satellites
    c = gpw_centres()
    k = np.cos(np.radians(12.6))
    tree = cKDTree(np.c_[c.lat.values, c.lon.values * k])
    dist, idx = tree.query(np.c_[ins.latitude.values, ins.longitude.values * k])
    ins = ins.assign(province=c.province.values[idx])
    ps = ins.groupby(["satellite", "province", "season"]).size().rename("detections").reset_index()
    ps.to_csv(DATA / "fire_province_season.csv", index=False)

    # fire-density map data: detections per 0.1-degree square, per satellite and Nov-Apr season, as dense uint8 rows (exact: max is < 256)
    # round before floor: 106.1 / 0.1 is 1060.9999999999998 in floating point, which would drop a detection on a square's edge into the wrong square
    w = ins[ins.season.isin(SEASONS)].assign(ix=lambda x: np.floor(np.round(x.longitude / CELL, 6)).astype(int),
                                             iy=lambda x: np.floor(np.round(x.latitude / CELL, 6)).astype(int))
    cells = w[["ix", "iy"]].drop_duplicates().sort_values(["iy", "ix"]).reset_index(drop=True)
    cells["ci"] = np.arange(len(cells))
    w = w.merge(cells, on=["ix", "iy"])
    g = w.groupby(["satellite", "season", "ci"]).size().rename("n").reset_index()
    assert g.n.max() < 256, "a cell has 256+ detections in one season: use uint16"
    out = dict(cell=CELL, ix=cells.ix.tolist(), iy=cells.iy.tolist(), seasons=SEASONS)
    for sat in ("Aqua", "Terra"):
        rows = []
        for s in SEASONS:
            a = np.zeros(len(cells), dtype=np.uint8)
            q = g[(g.satellite == sat) & (g.season == s)]
            a[q.ci.values] = q.n.values.astype(np.uint8)
            rows.append(base64.b64encode(a.tobytes()).decode("ascii"))
        out[sat.lower()] = rows
    (DATA / "fire_cells_by_season.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")

    audit = dict(
        raw_rows=int(len(raw)), first=str(raw.acq_date.min()), last=str(raw.acq_date.max()),
        raw_by_type={str(int(k)): int(v) for k, v in raw.type.value_counts().items()},
        raw_by_satellite={k: int(v) for k, v in raw.satellite.value_counts().items()},
        type0_low_confidence=int(((raw.type == 0) & (raw.confidence < 30)).sum()),
        clean_rows=int(len(d)), clean_by_satellite={k: int(v) for k, v in d.satellite.value_counts().items()},
        clean_share_nov_apr=float(100 * len(d[d.month.isin([11, 12, 1, 2, 3, 4])]) / len(d)),
        median_km_to_nearest_centre=float(np.median(dist) * 111),
        sat_range={k: [str(v.acq_date.min()), str(v.acq_date.max())] for k, v in raw.groupby("satellite")},
    )
    months = pd.to_datetime(raw.acq_date).dt.to_period("M")
    audit["months_present"] = int(months.nunique())
    audit["months_missing"] = [str(x) for x in pd.period_range(months.min(), months.max(), freq="M") if x not in set(months.unique())]
    nrt = next(Path(firms_dir).glob("fire_nrt_*.csv"), None)             # near-real-time companion file: recorded, never used
    if nrt is not None:
        n = pd.read_csv(nrt, usecols=["acq_date"])
        audit["nrt"] = dict(rows=int(len(n)), first=str(n.acq_date.min()), last=str(n.acq_date.max()))
    (DATA / "raw_audit.json").write_text(json.dumps(audit, indent=1), encoding="utf-8")
    print(f"FIRMS rows {len(raw):,} -> cleaned {len(d):,} | monthly rows {len(mc)} | seasons {len(sc)} | province-season rows {len(ps)} | "
          f"map squares {len(cells)} | median distance to nearest centre {audit['median_km_to_nearest_centre']:.0f} km")
    for f in sorted(DATA.glob("*")):
        print(f"  {f.name:30s} {f.stat().st_size / 1024:7.1f} KB")


# ------------------------------------------------------------------------------------------------ verify
def verify(firms_dir):
    """Second, independent derivation from the raw CSV (different code path: numpy distance matrix instead of a KD-tree, boolean masks
    instead of groupby) compared with the tables the panel embeds. Writes data/verification.json."""
    archive = next(Path(firms_dir).glob("fire_archive_*.csv"))
    raw = pd.read_csv(archive)
    lat, lon, conf, typ = raw.latitude.values, raw.longitude.values, raw.confidence.values, raw.type.values
    sat = raw.satellite.values
    dt = pd.to_datetime(raw.acq_date)
    yr, mo = dt.dt.year.values, dt.dt.month.values
    keep = (typ == 0) & (conf >= 30)
    season = yr + (mo >= 11)
    checks, fails = 0, []

    def check(name, got, want):
        nonlocal checks
        checks += 1
        if int(got) != int(want):
            fails.append(f"{name}: raw={int(want)} table={int(got)}")

    # 1. season totals per satellite
    sc = pd.read_csv(DATA / "fire_season_counts.csv", index_col="season")
    for s in SEASONS:
        for name in ("Aqua", "Terra"):
            m = keep & (sat == name) & (season == s) & np.isin(mo, [11, 12, 1, 2, 3, 4])
            check(f"season {s} {name}", sc.loc[s, name.lower()], m.sum())
    # 2. monthly totals
    mc = pd.read_csv(DATA / "fire_month_counts.csv")
    for r in mc.itertuples():
        check(f"month {r.year}-{r.month:02d} {r.satellite}", r.detections, (keep & (sat == r.satellite) & (yr == r.year) & (mo == r.month)).sum())
    # 3. province totals with a plain distance matrix
    c = gpw_centres()
    k = np.cos(np.radians(12.6))
    ins = keep & np.isin(mo, [11, 12, 1, 2, 3, 4])
    d2 = (lat[ins, None] - c.lat.values[None, :]) ** 2 + ((lon[ins, None] - c.lon.values[None, :]) * k) ** 2
    prov = c.province.values[d2.argmin(axis=1)]
    sat_i, season_i = sat[ins], season[ins]
    ps = pd.read_csv(DATA / "fire_province_season.csv")
    for r in ps.itertuples():
        check(f"province {r.province} {r.satellite} {r.season}", r.detections, ((prov == r.province) & (sat_i == r.satellite) & (season_i == r.season)).sum())
    # 4. map squares: every sat-season row sums to the season total, and 600 random squares are re-counted from the raw coordinates
    cells = json.loads((DATA / "fire_cells_by_season.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(7)
    ix, iy = np.array(cells["ix"]), np.array(cells["iy"])
    for name in ("Aqua", "Terra"):
        arrs = [np.frombuffer(base64.b64decode(b), dtype=np.uint8) for b in cells[name.lower()]]
        for s, a in zip(SEASONS, arrs):
            check(f"map sum {name} {s}", a.sum(), sc.loc[s, name.lower()])
        for _ in range(300):
            si, ci = int(rng.integers(len(SEASONS))), int(rng.integers(len(ix)))
            x0, y0, s = ix[ci] * CELL, iy[ci] * CELL, SEASONS[si]
            m = ins & (sat == name) & (season == s) & (lon >= x0 - 1e-9) & (lon < x0 + CELL - 1e-9) & (lat >= y0 - 1e-9) & (lat < y0 + CELL - 1e-9)
            check(f"map square {name} {s} ({ix[ci]},{iy[ci]})", arrs[si][ci], m.sum())
    result = dict(checks=checks, failures=len(fails), first_failures=fails[:10], raw_file=archive.name, raw_rows=int(len(raw)))
    (DATA / "verification.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"verify: {checks:,} checks against {archive.name} ({len(raw):,} rows), {len(fails)} failures")
    for f in fails[:10]:
        print("  FAIL", f)
    if fails:
        raise SystemExit(1)


# ------------------------------------------------------------------------------------------------ page
FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
BEGIN = "// ---- fire-watch:begin (generated by fire-watch/tools/build_fire_watch.py; re-run the `inject` stage instead of editing by hand) ----"
END = "// ---- fire-watch:end ----"
PANEL_BEGIN = "<!-- fire-watch:panel:begin (generated by fire-watch/tools/build_fire_watch.py; re-run the `inject` stage instead of editing by hand) -->"
PANEL_END = "<!-- fire-watch:panel:end -->"


def _fmt():
    sg = lambda x: ("+" if x >= 0 else "\u2212") + f"{abs(x):.1f}"
    fp = lambda p: "< 0.001" if p < 0.001 else (f"{p:.3f}" if p < 0.1 else f"{p:.2f}")
    eq = lambda p: "< 0.001" if p < 0.001 else (f"= {p:.3f}" if p < 0.1 else f"= {p:.2f}")
    return sg, fp, eq


def build_fire_case(P):
    """The 'fire_firms' entry for climate-watch-cambodia.html's CASES, in that page's own format. Fire only. Every number comes from P."""
    ta, tt = P["t_aqua"], P["t_terra"]
    sg, fp, eq = _fmt()
    n = lambda x: f"{round(x):,}"
    quiet = ta["verdict"] == "no significant trend"
    words = "no clear trend" if quiet else ("a borderline trend" if ta["verdict"] == "borderline" else f"a {ta['verdict']} trend")
    names = ", ".join(P["top5"][:-1]) + " and " + P["top5"][-1]
    first = FULL_MONTHS[P["months"].index(P["peak_month"])]
    colors = ["bg-orange-500", "bg-amber-500", "bg-rose-500", "bg-sky-500", "bg-purple-500", "bg-slate-500"]
    hot = [dict(label=r["name"], count=f"{r['share']:.1f}% \u00b7 {n(r['avg'])} per season", color=colors[i]) for i, r in enumerate(P["provinces"][:5])]
    rest = 100 - sum(r["share"] for r in P["provinces"][:5])
    hot.append(dict(label="Other 20 provinces", count=f"{rest:.1f}% of detections", color=colors[5]))
    yrs = f"{P['seasons'][0]['s']}\u2013{P['seasons'][-1]['s']}"
    return dict(
        tag="FIRE \u00b7 NASA FIRMS (AQUA + TERRA)",
        headline=f"Is Cambodia burning more? NASA FIRMS shows {words}",
        badge=f"Aqua {sg(ta['pct_per_decade'])}%/dec \u00b7 Mann\u2013Kendall p = {fp(ta['p'])} \u00b7 Terra {sg(tt['pct_per_decade'])}%/dec (p = {fp(tt['p'])})",
        c1Source="NASA FIRMS MODIS C6.1",
        c1Text=(f"{P['dec_mar']:.0f}% of real vegetation-fire detections (confidence \u2265 30) fall in December\u2013March, peaking in {first}. "
                f"{names} hold about {P['top5_share']:.0f}% of dry-season detections. Each fire is assigned to the nearest NASA SEDAC province centre, "
                f"so exact shares are \u00b13\u20134 points. (These four cards show the default view: Aqua, seasons 2003\u20132022. The controls below change the full analysis.)"),
        c2Title=f"2 \u00b7 Is this unusual? ({yrs})",
        c2Badge=f"p = {fp(ta['p'])} \u00b7 {'No Clear Trend (Aqua)' if quiet else ta['verdict'].title() + ' (Aqua)'}",
        c2Text=(f"{'Not statistically unusual.' if quiet else 'A statistically notable trend.'} Counting detections per November\u2013April season "
                f"(Aqua, {ta['n']} seasons to 2022) gives a Sen slope of {sg(ta['pct_per_decade'])}% per decade and Mann\u2013Kendall p = {fp(ta['p'])}. "
                f"Terra gives {sg(tt['pct_per_decade'])}% per decade (p = {fp(tt['p'])}), so the sign flips with the satellite and the data do not show fires "
                f"rising or falling. Blue bars (after 2022) are shown but not tested: satellite overpass times drifted and NASA changed processing version on 2023-01-01."),
        chartUnit=f"Aqua fire detections per Nov\u2013Apr season ({yrs}, labelled by the year it ends)",
        pettittLabel=(f"Pettitt: no step (p = {fp(ta['step_p'])}) \u00b7 blue = not tested" if ta["step_p"] >= 0.05
                      else f"Pettitt: step after {ta['step_after']} (p = {fp(ta['step_p'])}) \u00b7 blue = not tested"),
        series=[s["aqua"] for s in P["seasons"]],
        startYear=P["seasons"][0]["s"], breakIdx=[s["s"] for s in P["seasons"]].index(2023),
        axisLabels=["2003", "2009", "2014", "2020", str(P["seasons"][-1]["s"])],
        c3Text=(f"The dry season repeats: {P['dec_mar']:.0f}% of detections fall in December\u2013March and {first} is the busiest month. Over the {ta['n']} tested seasons Aqua counted "
                f"{n(ta['mean'])} detections on average, from {n(P['quietest_n'])} in {P['quietest']} to {n(P['busiest_n'])} in {P['busiest']}. "
                f"A new season outside that range would stand out; one inside it is ordinary variation."),
        cascade=["Dry-season burning (Dec\u2013Mar)", "\u2192", f"{P['top5_share']:.0f}% in five provinces", "\u2192", f"No clear trend (p = {fp(ta['p'])})"],
        actions=[
            f"Expect most burning in December\u2013March ({P['dec_mar']:.0f}% of detections, peak {first}); plan field work and burn management around it.",
            f"Put burn management first in {', '.join(P['top5'][:-1])} and {P['top5'][-1]} (about {P['top5_share']:.0f}% of detections).",
            "Quote the satellite with any fire trend: Aqua and Terra disagree on direction, so neither supports \u201cfires are rising\u201d on its own.",
        ],
        demo=[   # the four sentences read out by "Watch Demo 2" on the home screen, one per card
            f"Step 1/4 (What is happening): {P['dec_mar']:.0f}% of NASA FIRMS fire detections fall in December–March, and five provinces hold about {P['top5_share']:.0f}% of them.",
            f"Step 2/4 (Is this unusual?): Aqua shows {sg(ta['pct_per_decade'])}% per decade (p = {fp(ta['p'])}) and Terra {sg(tt['pct_per_decade'])}% (p = {fp(tt['p'])}): "
            f"{'neither is statistically significant' if ta['p'] >= 0.05 and tt['p'] >= 0.05 else 'see the tab for which one is significant'}, and the two satellites {'agree' if (ta['sen_per_decade'] > 0) == (tt['sen_per_decade'] > 0) else 'disagree'} on direction.",
            f"Step 3/4 (What comes next): the dry season repeats; {first} is the busiest month, and a season outside the usual {n(P['quietest_n'])}–{n(P['busiest_n'])} detections would stand out.",
            "Step 4/4 (What people can do): plan field work and burn management around December–March, and quote the satellite whenever you quote a fire trend.",
        ],
        hotspots=hot,
        qa=(f"Verified NASA FIRMS finding (MODIS C6.1, real vegetation fires, Nov\u2013Apr seasons 2003\u20132022): Aqua {sg(ta['pct_per_decade'])}% per decade, Mann\u2013Kendall p = {fp(ta['p'])} "
            f"({ta['verdict']}); Terra {sg(tt['pct_per_decade'])}% per decade, p = {fp(tt['p'])}. {P['dec_mar']:.0f}% of detections fall in December\u2013March and {names} hold about "
            f"{P['top5_share']:.0f}%."),
    )


def build_soot_case(P):
    """The 'soot_bc' entry: MERRA-2 black carbon (the repo's own Giovanni file) and how it lines up with FIRMS fire. Every number comes from P."""
    sm, S, ta = P["smoke"], P["soot"], P["t_aqua"]
    sg, fp, eq = _fmt()
    bt = sm["bc_trend"]
    clim = S["clim_all"]
    pk, lo = int(np.argmax(clim)), int(np.argmin(clim))
    pkn, lon_ = FULL_MONTHS[pk], FULL_MONTHS[lo]
    ratio = clim[pk] / clim[lo]
    quiet = bt["p"] >= 0.05
    mixed = (not quiet) and S["seasonal_p"] >= 0.05          # the yearly-mean test and the seasonal test disagree
    direction = "falling" if bt["sen_per_decade"] < 0 else "rising"
    dir_word = "decline" if bt["sen_per_decade"] < 0 else "rise"
    step_year = bt["step_after"]
    step_sig = bt["step_p"] < 0.05
    link = "holds" if sm["p_anom"] < 0.05 else "disappears"
    return dict(
        tag="SOOT & HAZE \u00b7 BLACK CARBON \u00b7 NASA MERRA-2",
        headline=("Soot peaks with the fire season; its long-run trend is not clear" if quiet else
                  f"Soot peaks with the fire season; whether it is {direction} depends on the test" if mixed else f"Soot peaks with the fire season, and its long-run trend is {direction}"),
        badge=f"Black carbon {sg(bt['pct_per_decade'])}%/dec \u00b7 yearly Mann\u2013Kendall p = {fp(bt['p'])} \u00b7 seasonal p = {fp(S['seasonal_p'])} \u00b7 peaks in {pkn}",
        c1Source="NASA MERRA-2 BCSMASS \u00b7 NASA FIRMS",
        c1Text=(f"Black carbon (soot) over Cambodia and parts of Thailand and Vietnam averages {S['mean']:.2f} \u00b5g/m\u00b3 over 2001\u20132024. It peaks in {pkn} ({clim[pk]:.2f}) and is lowest in "
                f"{lon_} ({clim[lo]:.2f}), about {ratio:.1f}\u00d7 lower. The November\u2013April fire season averages {S['dry']:.2f}, against {S['wet']:.2f} in May\u2013October. "
                f"(These cards show black carbon over the whole record. The panel below also has PM2.5 and aerosol optical depth, and lets you choose fire seasons to compare with fire.)"),
        c2Badge=f"p = {fp(bt['p'])} \u00b7 {'No Clear Trend' if quiet else 'Tests Disagree' if mixed else bt['verdict'].title()}",
        c2Text=(f"{'Not statistically unusual.' if quiet else 'Mixed evidence.' if mixed else 'A statistically notable trend.'} Yearly mean black carbon, 2001\u20132024: Sen slope {sg(bt['pct_per_decade'])}% per decade, Mann\u2013Kendall "
                f"p = {fp(bt['p'])}. "
                + (f"But the seasonal Mann\u2013Kendall test on all 288 months gives p = {fp(S['seasonal_p'])} and the month-by-month anomalies give p = {fp(S['deseason_p'])}, so the drop is fragile: it looks mostly like a single step after {step_year}. " if mixed else "")
                + f"The most likely step is after {step_year} (Pettitt p = {fp(bt['step_p'])}{', significant' if step_sig else ', not significant on its own'}). "
                f"MERRA-2 is a model product, not a direct measurement, so treat this as a question to follow up, not a finding."),
        chartUnit="Yearly mean black carbon, \u00b5g/m\u00b3 (2001\u20132024)",
        pettittLabel=f"Pettitt: most likely step after {step_year} (p = {fp(bt['step_p'])}) \u00b7 blue = after it",
        series=S["year_vals"], breakIdx=step_year + 1 - 2001,
        c3Text=(f"Soot follows fire. Season by season, fiercer fire seasons are sootier (\u03c1 = {sm['rho_year']:.2f}, p {eq(sm['p_year'])}, {sm['n_year']} seasons); month to month with the yearly cycle "
                f"removed the link {link} (\u03c1 = {sm['rho_anom']:.2f}). But soot's long-run {'apparent ' if mixed else ''}{dir_word} has no matching change in Aqua fire counts (p = {fp(ta['p'])}), so fire counts alone do not explain it."),
        cascade=["Dry-season burning", "\u2192", f"Soot peaks in {pkn}", "\u2192", f"Sootier when fires are fiercer (\u03c1 = {sm['rho_year']:.2f})"],
        actions=[
            f"Expect the sootiest air around {pkn} ({clim[pk]:.2f} \u00b5g/m\u00b3 on average, {ratio:.1f}\u00d7 the {lon_} level); plan outdoor work around it.",
            "Use the Fire tab to see which provinces burn most in the same months.",
            "Treat the long-run soot trend as a question, not a finding: it comes from a model (MERRA-2), averaged over a box that includes parts of Thailand and Vietnam.",
        ],
        hotspots=[dict(label=f"Peak month: {pkn}", count=f"{clim[pk]:.2f} \u00b5g/m\u00b3", color="bg-orange-500"),
                  dict(label=f"Lowest month: {lon_}", count=f"{clim[lo]:.2f} \u00b5g/m\u00b3", color="bg-sky-500"),
                  dict(label="Fire season (Nov\u2013Apr) average", count=f"{S['dry']:.2f} \u00b5g/m\u00b3", color="bg-amber-500"),
                  dict(label="Wet season (May\u2013Oct) average", count=f"{S['wet']:.2f} \u00b5g/m\u00b3", color="bg-slate-500")],
        qa=(f"Verified NASA MERRA-2 finding (BCSMASS, 2001\u20132024): black carbon averages {S['mean']:.2f} \u00b5g/m\u00b3, peaks in {pkn} ({clim[pk]:.2f}) and is lowest in {lon_} ({clim[lo]:.2f}). "
            f"Yearly trend {sg(bt['pct_per_decade'])}% per decade, Mann\u2013Kendall p = {fp(bt['p'])}; seasonal Mann\u2013Kendall on all months p = {fp(S['seasonal_p'])}. It follows NASA FIRMS fire: season by season \u03c1 = {sm['rho_year']:.2f} (p {eq(sm['p_year'])}). "
            f"MERRA-2 is a model product and the box includes parts of Thailand and Vietnam."),
    )



def build_water_case(P):
    """The 'water_heat' entry: five NASA series for the Cambodia box (GPM IMERG rain + four MERRA-2 fields). Every number comes from P."""
    W = P["water"]
    _, fp, eq = _fmt()
    sg = lambda x, d=1: ("+" if x >= 0 else "\u2212") + f"{abs(x):.{d}f}"
    st = W["stats"]
    order = ["imerg", "m2rain", "soil", "t2m", "wet"]
    sig = [k for k in order if st[k]["p_raw"] < 0.05]
    nosig = [k for k in order if k not in sig]
    stepped = [k for k in sig if st[k]["step_p"] < 0.05]
    two = lambda k: f"{INSTR[k]['label']}"
    rate = lambda k: (f"{sg(st[k]['pct_per_decade'])}%/dec" if INSTR[k]["unit"] in ("mm/day", "fraction") else f"{sg(st[k]['sen_per_decade'], 2)} \u00b0C/dec")
    step_txt = "; ".join(f"{INSTR[k]['label']} after {st[k]['step_after']} (p {eq(st[k]['step_p'])})" for k in stepped)
    all_stepped = bool(sig) and len(stepped) == len(sig) and all(st[k]["step_after"] in (2016, 2017) for k in stepped)
    hot = [dict(label=INSTR[k]["short"], count=f"{rate(k)} \u00b7 p {eq(st[k]['p_raw'])}", color=("bg-sky-500" if INSTR[k]["kind"].startswith("satellite") else "bg-amber-500")) for k in order]
    return dict(
        tag="RAIN, SOIL & HEAT \u00b7 GPM IMERG + NASA MERRA-2",
        headline=("Rain, soil and heat: the model series rise in steps, the satellite rain does not" if all_stepped and "imerg" in nosig else f"Rain, soil and heat: {len(sig)} of 5 series show a trend"),
        badge=f"GPM rain {rate('imerg')} (p {eq(st['imerg']['p_raw'])}) \u00b7 MERRA-2 rain {rate('m2rain')} (p {eq(st['m2rain']['p_raw'])}) \u00b7 wet-bulb {rate('wet')} (p {eq(st['wet']['p_raw'])})",
        c1Source="GPM IMERG (satellite) \u00b7 NASA MERRA-2 (model)",
        c1Text=(f"Five monthly NASA series for one box over Cambodia and parts of Thailand and Vietnam, 2001\u20132024: rain from the GPM satellites, and rain, soil wetness, air temperature and wet-bulb temperature from the MERRA-2 model. "
                f"Plain Mann\u2013Kendall on the yearly means: {len(sig)} of 5 reach p < 0.05 ({', '.join(two(k) for k in sig)}); "
                f"{', '.join(two(k) for k in nosig)} show no trend. (These cards show the whole record; the panel below lets you pick a series and a range of years.)"),
        c2Badge=f"Ratio break after {W['r_after']} \u00b7 p {eq(W['r_p'])}",
        c2Text=((f"Real, or a model step? {step_txt}. " if stepped else "") +
                f"The two rain records disagree on the long run: MERRA-2 \u00f7 GPM IMERG rises from {W['r_before']:.2f} to {W['r_after_mean']:.2f} after {W['r_after']} (Pettitt p {eq(W['r_p'])}), and GPM IMERG alone has no trend (p = {fp(W['imerg_p'])}). "
                f"A model series that drifts away from an independent record is a warning sign, not proof of an artefact."),
        chartUnit="MERRA-2 land rain \u00f7 GPM IMERG rain, yearly means (2001\u20132024)",
        pettittLabel=f"Pettitt: break after {W['r_after']} (p = {fp(W['r_p'])}) \u00b7 blue = after it",
        series=W["ratio"], breakIdx=W["r_after"] + 1 - 2001,
        c3Text=("A trend that only the model shows needs a second, independent record before it is called climate change. This box is also a single area-average, so it cannot say where in Cambodia anything changes; "
                "the next test is the same five series for sub-regions (north-east, Tonle Sap, south) and against a second source."),
        cascade=[f"GPM rain: {rate('imerg')}", "\u2192", f"MERRA-2 rain: {rate('m2rain')}", "\u2192", f"Gap = model step after {W['r_after']}"],
        actions=[
            f"Quote GPM IMERG for rain: it shows no trend (p {eq(st['imerg']['p_raw'])}).",
            f"Quote wet-bulb temperature as a step after {st['wet']['step_after']}, not a steady rise: {rate('wet')} overall, while air temperature is flat ({sg(st['t2m']['sen_per_decade'], 2)} \u00b0C/dec, p {eq(st['t2m']['p_raw'])}).",
            "Before calling any MERRA-2 trend climate change, repeat it in a second region and against a second data source.",
        ],
        hotspots=hot,
        qa=(f"Verified NASA finding (GPM IMERG and MERRA-2, 2001\u20132024 yearly means): " + "; ".join(f"{INSTR[k]['label']} {rate(k)} (p {eq(st[k]['p_raw'])})" for k in order) +
            f". {step_txt + '. ' if stepped else ''}MERRA-2 \u00f7 IMERG rain ratio {W['r_before']:.2f} \u2192 {W['r_after_mean']:.2f} after {W['r_after']}. MERRA-2 values are model output, not measurements."),
    )


def case_snippet(cases):
    out = []
    for key, case in cases:
        body = json.dumps(case, ensure_ascii=False, indent=2)
        body = "\n".join("      " + line for line in body.splitlines())
        out.append(f"      {key}: {body.lstrip()},")
    return f"      {BEGIN}\n" + "\n".join(out) + f"\n      {END}\n"


def replace_block(html, begin, end, snippet):
    a, b = html.find(begin), html.find(end)
    assert a != -1 and b != -1 and a < b, f"markers not found in climate-watch-cambodia.html: {begin[:30]}"
    line_start = html.rfind("\n", 0, a) + 1
    line_end = html.find("\n", b) + 1
    return html[:line_start] + snippet + html[line_end:]


def inject():
    """Idempotently rewrite the two marked blocks inside ../climate-watch-cambodia.html (the only place outside fire-watch/ this script writes):
    the `fire_firms` CASES entry and the full analysis panel."""
    target = REPO / "climate-watch-cambodia.html"
    html = target.read_text(encoding="utf-8")
    case = (DATA / "fire_firms_case.js").read_text(encoding="utf-8")
    panel = (DATA / "fire_panel.html").read_text(encoding="utf-8")
    html = replace_block(html, BEGIN, END, case)
    html = replace_block(html, PANEL_BEGIN, PANEL_END, panel)
    target.write_text(html, encoding="utf-8")
    print(f"updated both marked blocks in {target.name} (case {len(case):,} chars, panel {len(panel):,} chars)")


def read_giovanni(pattern):
    f = next((REPO / "data" / "giovanni").glob(pattern))
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next(i for i, l in enumerate(lines) if l.lower().startswith("time"))
    df = pd.read_csv(f, skiprows=start, skipinitialspace=True)
    df.columns = ["time", "v"]
    df = df[df["v"] < 1e10]                                   # drop Giovanni fill values
    df["date"] = pd.to_datetime(df["time"]).dt.to_period("M").dt.to_timestamp()
    return df.set_index("date")["v"], f.name


def build_page():
    mc = pd.read_csv(DATA / "fire_month_counts.csv")
    sc = pd.read_csv(DATA / "fire_season_counts.csv", index_col="season")
    ps = pd.read_csv(DATA / "fire_province_season.csv")
    cells = json.loads((DATA / "fire_cells_by_season.json").read_text(encoding="utf-8"))
    audit = json.loads((DATA / "raw_audit.json").read_text(encoding="utf-8"))
    vfile = DATA / "verification.json"
    verification = json.loads(vfile.read_text(encoding="utf-8")) if vfile.exists() else None

    # --- when: share of Aqua fire by calendar month over fire years (Nov of the year before ... Oct), 2003-2022
    mc["fy"] = mc.year + (mc.month >= 11).astype(int)
    aq = mc[(mc.satellite == "Aqua") & mc.fy.between(2003, 2022)]
    share = (100 * aq.groupby("month").detections.sum() / aq.detections.sum()).reindex(range(1, 13), fill_value=0)

    # --- trend: Aqua and Terra season counts, plus Earth Buddy's own fire series
    aqua = sc["aqua"].loc[2003:2022]
    terra = sc["terra"].loc[2003:2022]
    t_aqua, t_terra = run_tests(aqua.index, aqua.values), run_tests(terra.index, terra.values)
    eb = json.loads((REPO / "data" / "v" / "fire.json").read_text(encoding="utf-8"))
    eb_years = list(range(eb["years"][0], eb["years"][1] + 1))
    eb_khm = pd.Series(eb["regions"]["KHM"], index=eb_years, dtype=float)

    # like-for-like calendar years 2003-2024: Earth Buddy vs Terra vs Aqua (our cleaned counts)
    cal = mc.groupby(["year", "satellite"]).detections.sum().unstack()
    cmp_yrs = list(range(2003, 2025))
    comp = pd.DataFrame({"earth_buddy": eb_khm.loc[cmp_yrs], "terra": cal["Terra"].loc[cmp_yrs], "aqua": cal["Aqua"].loc[cmp_yrs]})
    compare = []
    for key, label in (("earth_buddy", "Earth Buddy's fire variable (data/v/fire.json)"), ("terra", "Our FIRMS, Terra only"),
                       ("aqua", "Our FIRMS, Aqua only")):
        r = run_tests(comp.index, comp[key].values)
        compare.append(dict(key=key, label=label, mean=r["mean"], pct=r["pct_per_decade"], p=r["p"], verdict=r["verdict"]))
    rho_terra = float(comp.earth_buddy.corr(comp.terra, method="spearman"))
    ratio_terra = float((comp.earth_buddy / comp.terra).median())

    # --- where: nearest province centre, Aqua seasons 2003-2022 (default view)
    pv = ps[(ps.satellite == "Aqua") & ps.season.between(2003, 2022)].groupby("province").detections.sum() / 20
    pv = pv.sort_values(ascending=False)
    top = [dict(name=k, avg=float(v), share=float(100 * v / pv.sum())) for k, v in pv.head(10).items()]
    top5_share = float(100 * pv.head(5).sum() / pv.sum())

    # --- smoke (default view): black carbon vs Aqua fire over fire years 2003-2022 = Nov 2002 .. Oct 2022
    bc_all, bc_file = read_giovanni("*BCSMASS*.csv")
    bc_all = bc_all * 1e9                                   # kg m-3 -> ug m-3
    w0, w1 = "2002-11-01", "2022-10-01"
    fire_m = (mc[mc.satellite == "Aqua"].assign(date=lambda x: pd.to_datetime(dict(year=x.year, month=x.month, day=1)))
              .set_index("date").detections)
    fire_m = fire_m.reindex(pd.date_range(w0, w1, freq="MS"), fill_value=0).astype(float)
    bc_w = bc_all.loc[w0:w1]
    raw = sps.spearmanr(fire_m, bc_w)
    des = lambda s: s - s.groupby(s.index.month).transform("mean")
    anom = sps.spearmanr(des(fire_m), des(bc_w))
    clim_fire = fire_m.groupby(fire_m.index.month).mean()
    clim_bc = bc_w.groupby(bc_w.index.month).mean()
    bs = bc_all.to_frame("v")
    bs["season"] = bs.index.year + (bs.index.month >= 11).astype(int)
    bs = bs[bs.index.month.isin([11, 12, 1, 2, 3, 4])]
    g = bs.groupby("season").v
    bc_season = g.mean()[g.count() == 6]
    seasons_ok = [y for y in range(2003, 2023) if y in bc_season.index and y in sc.index]
    ys = sps.spearmanr(bc_season.loc[seasons_ok], sc["aqua"].loc[seasons_ok])
    bc_year = bc_all.groupby(bc_all.index.year).mean().loc[2001:2024]
    t_bc = run_tests(bc_year.index, bc_year.values)

    # --- interactive data (everything the panel's sliders recompute from)
    c = gpw_centres()
    region_of = {p: (k, label) for k, label, members in REGIONS for p in members}
    prov = [dict(name=r.province, region=region_of[r.province][0], lat=float(r.lat), lon=float(r.lon)) for r in c.itertuples()]
    provdata, tot = {}, {}
    for sat in ("Aqua", "Terra"):
        q = ps[ps.satellite == sat].pivot_table(index="season", columns="province", values="detections", aggfunc="sum", fill_value=0)
        q = q.reindex(index=SEASONS, columns=c.province.tolist(), fill_value=0)
        provdata[sat.lower()] = q.values.astype(int).tolist()
        tot[sat.lower()] = [int(sc.loc[s, sat.lower()]) for s in SEASONS]
        assert q.values.sum(axis=1).tolist() == tot[sat.lower()], f"province totals do not add up to the season totals for {sat}"
        arrs = [np.frombuffer(base64.b64decode(b), dtype=np.uint8) for b in cells[sat.lower()]]
        assert [int(a.sum()) for a in arrs] == tot[sat.lower()], f"map squares do not add up to the season totals for {sat}"
    first_idx = (2001 * 12 + 10)                            # Nov 2001
    n_months = (2026 * 12 + 7) - first_idx + 1              # through Aug 2026
    monthly = {}
    for sat in ("Aqua", "Terra"):
        arr = [0] * n_months
        for r in mc[mc.satellite == sat].itertuples():
            arr[r.year * 12 + (r.month - 1) - first_idx] = int(r.detections)
        monthly[sat.lower()] = arr
    dyn = dict(
        seasons=SEASONS, cell=CELL, cx=cells["ix"], cy=cells["iy"], cells={"aqua": cells["aqua"], "terra": cells["terra"]},
        prov=prov, regions=[dict(key=k, label=lab, members=m) for k, lab, m in REGIONS],
        provdata=provdata, tot=tot, month_start=[2001, 11], monthly=monthly,
        audit=audit, verification=verification,
    )
    bc24 = bc_all.loc["2001-01-01":"2024-12-01"]
    soot = dict(
        clim_all=[float(bc24[bc24.index.month == m].mean()) for m in range(1, 13)], mean=float(bc24.mean()),
        dry=float(bc24[bc24.index.month.isin([11, 12, 1, 2, 3, 4])].mean()), wet=float(bc24[bc24.index.month.isin(range(5, 11))].mean()),
        year_vals=[round(float(v), 3) for v in bc_year.values],
    )
    vars_ = {}
    for key, label, unit, dec, pattern, scale in (("bc", "Black carbon", "\u00b5g/m\u00b3", 2, "*BCSMASS*.csv", 1e9),
                                                  ("pm25", "PM2.5", "\u00b5g/m\u00b3", 1, "*TOTSMASS25*.csv", 1e9),
                                                  ("aod", "Aerosol optical depth", "", 3, "*TOTEXTTAU*.csv", 1.0)):
        ser, fname = read_giovanni(pattern)
        ser = ser * scale
        yr = ser.groupby(ser.index.year).mean().loc[2001:2024]
        ty = run_tests(yr.index, yr.values)
        import pymannkendall as pmk                                  # seasonal tests: the yearly test alone can mislead when there is a step
        ty["seasonal_p"] = float(pmk.seasonal_test(ser.values, period=12).p)                                   # Hirsch-Slack seasonal Mann-Kendall, all 288 months
        ty["deseason_p"] = float(pmk.original_test((ser - ser.groupby(ser.index.month).transform("mean")).values).p)   # MK on month-by-month anomalies
        kind_, product_, title_, what_ = AEROSOL_WHAT[key]
        vars_[key] = dict(label=label, unit=unit, dec=dec, file=fname, t_year=ty, kind=kind_, product=product_, title=title_, what=what_, doi="10.5067/FH9A0MLJPC7N",
                          v=[round(float(v), 12) for v in ser.reindex(pd.date_range("2001-01-01", "2024-12-01", freq="MS")).values])
    import pymannkendall as pmk
    water_vars, water_series = {}, {}
    for key, ins_ in INSTR.items():
        ser, fname = read_giovanni(ins_["pattern"])
        ser = ser * ins_["scale"]
        water_series[key] = ser
        yv = ser.groupby(ser.index.year).mean().loc[2001:2024].values
        an_ = (ser - ser.groupby(ser.index.month).transform("mean")).values
        water_vars[key] = dict({k: v for k, v in ins_.items() if k not in ("pattern", "scale")}, file=fname,
                               v=[round(float(v), 10) for v in ser.reindex(pd.date_range("2001-01-01", "2024-12-01", freq="MS")).values],
                               robust=dict(plain=float(pmk.original_test(yv).p), tfpw=float(pmk.trend_free_pre_whitening_modification_test(yv).p), hamed_rao=float(pmk.hamed_rao_modification_test(yv).p),
                                           yue_wang=float(pmk.yue_wang_modification_test(yv).p), seasonal=float(pmk.seasonal_test(ser.values, period=12).p), deseason=float(pmk.original_test(an_).p)))
    im_y = water_series["imerg"].groupby(water_series["imerg"].index.year).mean().loc[2001:2024]
    m2_y = water_series["m2rain"].groupby(water_series["m2rain"].index.year).mean().loc[2001:2024]
    ratio = (m2_y / im_y)
    pw_ = sx.pettitt(ratio.values)
    water = dict(
        stats={k: run_tests(range(2001, 2025), water_series[k].groupby(water_series[k].index.year).mean().loc[2001:2024].values) for k in INSTR},
        ratio=[round(float(v), 3) for v in ratio.values], r_after=int(ratio.index[pw_["index"]]), r_p=float(pw_["p"]),
        r_before=float(ratio.values[:pw_["index"] + 1].mean()), r_after_mean=float(ratio.values[pw_["index"] + 1:].mean()),
        imerg_p=float(pmk.original_test(im_y.values).p), rain_r=float(np.corrcoef(water_series["imerg"].values, water_series["m2rain"].values)[0, 1]),
        robust={k: water_vars[k]["robust"] for k in INSTR},
    )
    water_dyn = dict(months=MONTHS, vars=water_vars, rain_r=water["rain_r"], imerg_p=water["imerg_p"])
    soot["seasonal_p"], soot["deseason_p"] = vars_["bc"]["t_year"]["seasonal_p"], vars_["bc"]["t_year"]["deseason_p"]
    soot_dyn = dict(months=MONTHS, seasons=SEASONS, tot=tot, month_start=[2001, 11], monthly=monthly, vars=vars_, fire_p=t_aqua["p"])

    payload = dict(
        months=MONTHS, share=[float(v) for v in share.values],
        dec_mar=float(share.loc[[12, 1, 2, 3]].sum()), peak_month=MONTHS[int(share.idxmax()) - 1],
        seasons=[dict(s=int(s), aqua=int(sc.loc[s, "aqua"]), terra=int(sc.loc[s, "terra"])) for s in SEASONS],
        t_aqua=t_aqua, t_terra=t_terra, busiest=int(aqua.idxmax()), quietest=int(aqua.idxmin()),
        busiest_n=int(aqua.max()), quietest_n=int(aqua.min()),
        provinces=top, top5_share=top5_share, top5=[p["name"] for p in top[:5]],
        smoke=dict(clim_fire=[float(clim_fire.loc[m]) for m in range(1, 13)], clim_bc=[float(clim_bc.loc[m]) for m in range(1, 13)],
                   rho_raw=float(raw.statistic), p_raw=float(raw.pvalue), rho_anom=float(anom.statistic), p_anom=float(anom.pvalue),
                   n_months=int(len(fire_m)), rho_year=float(ys.statistic), p_year=float(ys.pvalue), n_year=len(seasons_ok),
                   points=[dict(s=int(y), bc=float(bc_season.loc[y]), fire=int(sc["aqua"].loc[y])) for y in seasons_ok],
                   bc_trend=t_bc, bc_file=bc_file,
                   bc_peak=MONTHS[int(clim_bc.idxmax()) - 1], fire_peak=MONTHS[int(clim_fire.idxmax()) - 1]),
        method_check=json.loads((DATA / "province_method_check.json").read_text(encoding="utf-8")),
        compare=compare, rho_terra=rho_terra, ratio_terra=ratio_terra, cmp_years=[2003, 2024],
        dyn=dyn, soot=soot, water=water,
    )
    (DATA / "fire_firms_case.js").write_text(case_snippet([("fire_firms", build_fire_case(payload)), ("soot_bc", build_soot_case(payload)), ("water_heat", build_water_case(payload))]), encoding="utf-8")
    css = (HERE / "panel.css").read_text(encoding="utf-8")
    trend, rank = (HERE / "stats_trend.js").read_text(encoding="utf-8"), (HERE / "stats_rank.js").read_text(encoding="utf-8")

    def fill(tpl, data):
        data_json = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
        return (tpl.replace("__CSS__", css).replace("/*__STATS_TREND__*/", trend).replace("/*__STATS_RANK__*/", rank).replace("__DATA__", data_json))

    fire_data = {k: v for k, v in payload.items() if k not in ("smoke", "soot", "water")}
    fire_panel = fill((HERE / "panel_template.html").read_text(encoding="utf-8"), fire_data)
    soot_panel = fill((HERE / "soot_template.html").read_text(encoding="utf-8"), soot_dyn)
    water_panel = fill((HERE / "water_template.html").read_text(encoding="utf-8"), water_dyn)
    (DATA / "fire_panel.html").write_text(f"{PANEL_BEGIN}\n{fire_panel}{soot_panel}{water_panel}{PANEL_END}\n", encoding="utf-8")
    html = (HERE / "page_template.html").read_text(encoding="utf-8").replace("__PANEL__", fire_panel)
    panel = fire_panel + soot_panel + water_panel
    out = FW / "fire-watch-cambodia.html"
    out.write_text(html, encoding="utf-8")
    (DATA / "default_view.json").write_text(json.dumps(dict(
        note="Numbers for the default view (Aqua, seasons 2003-2022) computed in Python; the panel's JavaScript must reproduce them.",
        t_aqua=t_aqua, t_terra=t_terra, share=payload["share"], dec_mar=payload["dec_mar"], top=top, top5_share=top5_share,
        smoke={k: v for k, v in payload["smoke"].items() if k not in ("points", "bc_file")}), indent=1), encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)} ({len(html) / 1024:.0f} KB), panel fragment {len(panel) / 1024:.0f} KB")
    print(json.dumps({k: payload[k] for k in ("dec_mar", "peak_month", "t_aqua", "t_terra", "top5", "top5_share", "rho_terra", "ratio_terra")},
                     indent=1)[:1800])


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "tables":
        build_tables(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "verify":
        verify(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "page":
        build_page()
    elif len(sys.argv) >= 2 and sys.argv[1] == "inject":
        inject()
    else:
        print(__doc__)
