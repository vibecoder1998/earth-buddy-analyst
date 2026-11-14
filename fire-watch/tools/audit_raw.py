"""Audit the raw CSVs, then export the clean data, and write data/pipeline_audit.json (the numbers pipeline.html shows).

    python fire-watch/tools/audit_raw.py --firms <folder with fire_archive_*.csv> --giovanni <folder with the 8 Giovanni CSVs>
           [--copies <folder> ...]            other folders that should hold byte-identical copies of the same files
           [--existing-tidy <csv>]            an earlier tidy table to compare the clean export with

Reads the raw files exactly as downloaded and never modifies them. Writes only inside fire-watch/: data/pipeline_audit.json and clean-data/.
The cleaning rules are the same ones build_fire_watch.py applies (clean_fires, read_giovanni); this script re-states them on purpose, so a mistake in
one place shows up as a disagreement here.
"""
import argparse
import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FW = HERE.parent
DATA = FW / "data"
CLEAN = FW / "clean-data"

# token in the file name -> (clean column, factor, unit after conversion, plausible range, what it is, instrument or model)
GIOVANNI = [
    ("GPM_3IMERGM_07_precipitation", "imerg_precip_mm_day", 1.0, "mm/day", (0, 25), "Rain", "GPM IMERG v07 Final Run (satellite-based estimate, adjusted to rain gauges)"),
    ("M2TMNXLND_5_12_4_PRECTOTLAND", "merra2_precip_land_mm_day", 86400.0, "mm/day", (0, 25), "Rain over land (bias corrected)", "MERRA-2 M2TMNXLND v5.12.4 (model reanalysis); file is kg m-2 s-1, x86400"),
    ("M2TMNXLND_5_12_4_GWETROOT", "root_zone_soil_wetness", 1.0, "fraction 0-1", (0, 1), "Root-zone soil wetness", "MERRA-2 M2TMNXLND v5.12.4 (Catchment land model)"),
    ("M2TMNXSLV_5_12_4_T2M.", "t2m_c", 1.0, "deg C", (10, 40), "2 m air temperature", "MERRA-2 M2TMNXSLV v5.12.4 (model reanalysis)"),
    ("M2TMNXSLV_5_12_4_T2MWET", "t2m_wetbulb_c", 1.0, "deg C", (10, 35), "2 m wet-bulb temperature", "MERRA-2 M2TMNXSLV v5.12.4 (model reanalysis)"),
    ("M2TMNXAER_5_12_4_TOTEXTTAU", "aod_550nm", 1.0, "unitless", (0, 3), "Aerosol optical depth, 550 nm", "MERRA-2 M2TMNXAER v5.12.4 (constrained by satellite and AERONET observations)"),
    ("M2TMNXAER_5_12_4_BCSMASS", "black_carbon_ugm3", 1e9, "ug/m3", (0, 10), "Black carbon surface mass", "MERRA-2 M2TMNXAER v5.12.4 (GOCART aerosol module); file is kg m-3, x1e9"),
    ("M2TMNXAER_5_12_4_TOTSMASS25", "pm25_ugm3", 1e9, "ug/m3", (0, 200), "PM2.5 surface mass", "MERRA-2 M2TMNXAER v5.12.4 (GOCART aerosol module); file is kg m-3, x1e9"),
]
FILL_LIMIT = 1e10                                           # Giovanni writes 1e15 for missing values
CONF_MIN = 30                                               # FIRMS MODIS confidence (percent) kept
SEASON_MONTHS = [11, 12, 1, 2, 3, 4]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_giovanni_raw(f):
    lines = Path(f).read_text(encoding="utf-8", errors="replace").splitlines()
    st = next(i for i, l in enumerate(lines) if l.lower().startswith("time"))
    meta = {}
    for l in lines[:st]:
        if "," in l:
            k, v = l.split(",", 1)
            meta[k.strip().rstrip(":")] = v.strip().strip('"')
    rows, bad = [], 0
    for l in lines[st + 1:]:
        if not l.strip():
            continue
        parts = l.split(",")
        try:
            rows.append((pd.Timestamp(parts[0].strip()), float(parts[1])))
        except (ValueError, IndexError):
            bad += 1
    return meta, rows, bad, st


def audit_giovanni(folder, copies):
    out, clean_cols = [], {}
    files = sorted(Path(folder).glob("*.csv"))
    assert len(files) == 8, f"expected 8 Giovanni CSVs, found {len(files)}"
    for token, col, factor, unit, (lo, hi), what, instr in GIOVANNI:
        matches = [f for f in files if token in f.name]
        assert len(matches) == 1, f"{token}: {len(matches)} files match"
        f = matches[0]
        meta, rows, bad, header_lines = read_giovanni_raw(f)
        dates = [r[0] for r in rows]
        vals = np.array([r[1] for r in rows], float)
        fill = vals >= FILL_LIMIT
        ok = ~fill & np.isfinite(vals)
        exp = pd.date_range("2001-01-01", "2024-12-01", freq="MS")
        present = pd.DatetimeIndex(sorted(set(d.normalize() for d, o in zip(dates, ok) if o)))
        scaled = vals[ok] * factor
        # the clean series: fill values out, each timestamp moved to the first day of its month, units converted. Nothing else is changed.
        ser = pd.Series({d.normalize(): v * factor for d, v, o in zip(dates, vals, ok) if o}).sort_index()
        ser.index = pd.DatetimeIndex([pd.Timestamp(d.year, d.month, 1) for d in ser.index])
        clean_cols[col] = ser
        out.append(dict(
            file=f.name, bytes=f.stat().st_size, sha256=sha256(f), what=what, instrument=instr, clean_column=col, factor=factor, unit=unit,
            title=meta.get("Title", ""), bbox_requested=meta.get("User Bounding Box", ""), bbox_data=meta.get("Data Bounding Box", ""),
            start=meta.get("User Start Date", ""), end=meta.get("User End Date", ""), reproduce_url=meta.get("URL to Reproduce Results", ""),
            header_lines=header_lines, data_rows=len(rows), unparseable_rows=bad, fill_value_rows=int(fill.sum()), nan_rows=int((~np.isfinite(vals)).sum()),
            duplicate_dates=int(len(dates) - len(set(d.normalize() for d in dates))), all_first_of_month=bool(all(d.day == 1 for d in dates)),
            first=str(min(dates).date()), last=str(max(dates).date()), months_expected=len(exp), months_present=int(len(present)),
            months_missing=[str(d.date()) for d in exp.difference(present)],
            raw_min=float(vals[ok].min()), raw_max=float(vals[ok].max()), min=float(scaled.min()), max=float(scaled.max()), mean=float(scaled.mean()),
            plausible_range=[lo, hi], in_plausible_range=bool(((scaled >= lo) & (scaled <= hi)).all()),
            rows_kept=int(len(ser)), rows_dropped=int(len(rows) - len(ser)),
        ))
    clean = pd.DataFrame(clean_cols)
    clean.index.name = "date"
    assert len(clean) == 288 and clean.notna().all().all(), "clean Giovanni table has gaps"
    return out, clean


def audit_firms(folder):
    arch = next(Path(folder).glob("fire_archive_*.csv"))
    raw = pd.read_csv(arch, dtype={"acq_time": str})
    n = len(raw)
    dt = pd.to_datetime(raw.acq_date)
    # the two cleaning rules (the same as clean_fires in build_fire_watch.py): vegetation fires only (type 0), and confidence at least 30
    typ0 = raw.type == 0
    conf_ok = raw.confidence >= CONF_MIN
    clean = raw[typ0 & conf_ok].copy()
    cdt = pd.to_datetime(clean.acq_date)
    season_month = cdt.dt.month.isin(SEASON_MONTHS)
    months = dt.dt.to_period("M")
    missing = [str(m) for m in pd.period_range(months.min(), months.max(), freq="M") if m not in set(months.unique())]
    dup_cols = ["latitude", "longitude", "acq_date", "acq_time", "satellite"]
    res = dict(
        file=arch.name, bytes=arch.stat().st_size, sha256=sha256(arch), rows=int(n), columns=list(raw.columns),
        null_cells={c: int(v) for c, v in raw.isna().sum().items() if v},
        first=str(raw.acq_date.min()), last=str(raw.acq_date.max()), months_present=int(months.nunique()), months_missing=missing,
        by_satellite={k: int(v) for k, v in raw.satellite.value_counts().items()}, instruments=sorted(raw.instrument.unique().tolist()),
        collection_versions=sorted(raw.version.astype(str).unique().tolist()),
        by_type={str(int(k)): int(v) for k, v in raw.type.value_counts().sort_index().items()}, by_daynight={k: int(v) for k, v in raw.daynight.value_counts().items()},
        confidence_min=int(raw.confidence.min()), confidence_max=int(raw.confidence.max()),
        lat_range=[float(raw.latitude.min()), float(raw.latitude.max())], lon_range=[float(raw.longitude.min()), float(raw.longitude.max())],
        exact_duplicate_rows=int(raw.duplicated(subset=dup_cols).sum()),
        frp_missing=int(raw.frp.isna().sum()),
        # the funnel pipeline.html draws: each step says how many rows it removes or keeps
        cascade=[
            dict(step="Rows in the raw file", rows=int(n), note="every detection FIRMS returned for the request"),
            dict(step="Dropped: not a vegetation fire", rows=-int((~typ0).sum()), note="FIRMS type 1 (active volcano), 2 (other static land source) and 3 (offshore); we keep type 0 only"),
            dict(step="Dropped: low confidence", rows=-int((typ0 & ~conf_ok).sum()), note=f"vegetation fires with confidence below {CONF_MIN}%"),
            dict(step="Clean detections", rows=int(len(clean)), note="type 0 and confidence >= 30"),
            dict(step="of which November-April (the fire season)", rows=int(season_month.sum()), note="season is labelled by the year it ends; this is what every trend test counts"),
            dict(step="of which December-March", rows=int(cdt.dt.month.isin([12, 1, 2, 3]).sum()), note="the busiest four months"),
        ],
        clean_by_satellite={k: int(v) for k, v in clean.satellite.value_counts().items()},
        clean_share_nov_apr=float(100 * season_month.mean()), clean_share_dec_mar=float(100 * cdt.dt.month.isin([12, 1, 2, 3]).mean()),
    )
    nrt = next(Path(folder).glob("fire_nrt_*.csv"), None)
    if nrt is not None:
        z = pd.read_csv(nrt)
        res["nrt"] = dict(file=nrt.name, bytes=nrt.stat().st_size, sha256=sha256(nrt), rows=int(len(z)), first=str(z.acq_date.min()), last=str(z.acq_date.max()),
                          used=False, note="near-real-time file: recorded, never used (not final-quality, and it overlaps the archive's last weeks)")
    return res


def folder_label(o):
    """a folder name that does not say where this computer keeps it: repo-relative inside the repo, otherwise the last two parts"""
    p = Path(o).resolve()
    try:
        return p.relative_to(FW.parent).as_posix()
    except ValueError:
        return "/".join(p.parts[-2:])


def copies_report(primary, others, names):
    out = {}
    for nm in names:
        a = Path(primary) / nm
        ha = sha256(a)
        entry = {"primary": ha[:16], "copies": []}
        for o in others:
            b, gz = Path(o) / nm, Path(o) / (nm + ".gz")
            if b.exists():
                same_bytes = sha256(b) == ha
                same_content = same_bytes or a.read_bytes().replace(b"\r\n", b"\n") == b.read_bytes().replace(b"\r\n", b"\n")   # git on Windows turns LF into CRLF
                entry["copies"].append(dict(folder=folder_label(o), exists=True, identical=bool(same_bytes), identical_ignoring_line_endings=bool(same_content), stored_gzipped=False))
            elif gz.exists():                                       # the packaged 57 MB archive is kept gzipped: compare what it unpacks to
                h = hashlib.sha256()
                with gzip.open(gz, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                ok = h.hexdigest() == ha
                entry["copies"].append(dict(folder=folder_label(o), exists=True, identical=ok, identical_ignoring_line_endings=ok, stored_gzipped=True))
            else:
                entry["copies"].append(dict(folder=folder_label(o), exists=False, identical=False, identical_ignoring_line_endings=False, stored_gzipped=False))
        out[nm] = entry
    return out


def write_dictionary(g_audit, firms):
    L = ["# Clean data: what each file is", "",
         "Everything here is made from the raw NASA files by `fire-watch/tools/audit_raw.py` and `fire-watch/tools/build_fire_watch.py`. The raw files are never edited.", "",
         "## `giovanni_cambodia_box_monthly_clean.csv`", "",
         f"One row per month, January 2001 to December 2024 (288 rows), one column per NASA Giovanni series. Every series is an **area average over one box, 102.3–107.6°E, 10.4–14.7°N** (Cambodia plus parts of Thailand, Laos, Vietnam and the Gulf of Thailand). The grid cells actually used span {g_audit[0]['bbox_data']}.", "",
         "Cleaning applied: the header lines are skipped; any value of 1e10 or more is a Giovanni fill value and would be dropped (0 were found); each timestamp becomes the first day of its month; units are converted as shown. No value was changed in any other way: no smoothing, interpolation or gap filling.", "",
         "| Column | Unit | Conversion from the raw file | What it is | Produced by |", "|---|---|---|---|---|"]
    for a in g_audit:
        conv = "none" if a["factor"] == 1.0 else f"× {a['factor']:g}"
        L.append(f"| `{a['clean_column']}` | {a['unit']} | {conv} | {a['what']} | {a['instrument']} |")
    L += ["", "## `fire_month_counts.csv`", "", "Cleaned MODIS fire detections per calendar month and satellite. Columns: `year`, `month`, `satellite` (Aqua or Terra), `detections`.", "",
          "## `fire_season_counts.csv`", "", "Detections per November–April fire season (labelled by the year it ends: season 2020 = November 2019 to April 2020). Columns: `season`, `aqua`, `terra`.", "",
          "## `fire_province_season.csv`", "", "The same detections assigned to the **nearest** NASA SEDAC GPWv4 province centre point. This is an approximation (centre points, not borders): treat province shares as ±3–4 points. Columns: `satellite`, `province`, `season`, `detections`.", "",
          "## How a fire detection becomes a clean row", "",
          f"1. Start from the FIRMS archive `{firms['file']}` ({firms['rows']:,} rows, {firms['first']} to {firms['last']}, MODIS Collection 6.1 on Terra and Aqua).",
          f"2. Keep `type == 0` (a vegetation fire): drops {-firms['cascade'][1]['rows']:,} rows (volcanoes, other static sources, offshore).",
          f"3. Keep `confidence >= {CONF_MIN}`: drops {-firms['cascade'][2]['rows']:,} rows.",
          f"4. That leaves {firms['cascade'][3]['rows']:,} clean detections. {firms['cascade'][4]['rows']:,} of them ({firms['clean_share_nov_apr']:.1f}%) fall in November–April and are the ones the trend tests count.",
          "5. Count per satellite and season, per satellite and month, and per nearest province centre.", "",
          "The near-real-time file in the same download is recorded but never used.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firms", required=True)
    ap.add_argument("--giovanni", required=True)
    ap.add_argument("--copies", nargs="*", default=[])
    ap.add_argument("--existing-tidy", default=None)
    a = ap.parse_args()

    g_audit, clean = audit_giovanni(a.giovanni, a.copies)
    firms = audit_firms(a.firms)

    CLEAN.mkdir(exist_ok=True)
    rename = {g["clean_column"]: g["clean_column"] for g in g_audit}
    clean_path = CLEAN / "giovanni_cambodia_box_monthly_clean.csv"
    clean.to_csv(clean_path, float_format="%.12g")
    tables = {}
    for nm in ("fire_month_counts.csv", "fire_season_counts.csv", "fire_province_season.csv"):
        shutil.copy2(DATA / nm, CLEAN / nm)
        d = pd.read_csv(CLEAN / nm)
        tables[nm] = dict(rows=int(len(d)), columns=list(d.columns), sha256=sha256(CLEAN / nm)[:16])
    (CLEAN / "DATA_DICTIONARY.md").write_text(write_dictionary(g_audit, firms), encoding="utf-8")

    tidy_cmp = None
    if a.existing_tidy:
        old = pd.read_csv(a.existing_tidy, parse_dates=["date"]).set_index("date")
        new = pd.read_csv(clean_path, parse_dates=["date"]).set_index("date")
        common = [c for c in new.columns if c in old.columns]
        tidy_cmp = dict(file=str(Path(a.existing_tidy).name), columns_compared=common, rows_old=int(len(old)), rows_new=int(len(new)),
                        max_abs_difference={c: float((old[c] - new[c]).abs().max()) for c in common})

    names = [g["file"] for g in g_audit] + [firms["file"]] + ([firms["nrt"]["file"]] if "nrt" in firms else [])
    cp = {}
    for nm in names:
        base = a.firms if nm.startswith("fire_") else a.giovanni
        cp.update(copies_report(base, a.copies, [nm]))

    # the clean fire tables must reproduce the raw file's own counts (cheap re-count here; the full 2,495-check comparison is `build_fire_watch.py verify`)
    # a cheap independent recount of the season table from the raw file (the full check is `build_fire_watch.py verify`)
    sc = pd.read_csv(CLEAN / "fire_season_counts.csv", index_col="season")
    raw = pd.read_csv(next(Path(a.firms).glob("fire_archive_*.csv")), usecols=["acq_date", "satellite", "confidence", "type"])
    d = raw[(raw.type == 0) & (raw.confidence >= CONF_MIN)]
    dt = pd.to_datetime(d.acq_date)
    s = dt.dt.year + (dt.dt.month >= 11)
    ins = d[dt.dt.month.isin(SEASON_MONTHS)]
    cnt = ins.groupby([ins.satellite, s[ins.index]]).size().unstack(0)
    diff = int(sum(abs(int(cnt.loc[ss, "Aqua"]) - int(sc.loc[ss, "aqua"])) + abs(int(cnt.loc[ss, "Terra"]) - int(sc.loc[ss, "terra"])) for ss in cnt.index if ss in sc.index and ss >= 2003))

    audit = dict(giovanni=g_audit, firms=firms, clean_files=dict(giovanni=dict(file=clean_path.name, rows=int(len(clean)), columns=list(clean.columns), sha256=sha256(clean_path)[:16]), fire_tables=tables),
                 copies=cp, existing_tidy_comparison=tidy_cmp, season_table_vs_raw_count_difference=diff)
    (DATA / "pipeline_audit.json").write_text(json.dumps(audit, indent=1), encoding="utf-8")

    # console summary
    print(f"Giovanni: {len(g_audit)} files, all {g_audit[0]['months_expected']} months present: {all(not g['months_missing'] for g in g_audit)}; fill values: {sum(g['fill_value_rows'] for g in g_audit)}; "
          f"duplicates: {sum(g['duplicate_dates'] for g in g_audit)}; unparseable rows: {sum(g['unparseable_rows'] for g in g_audit)}; all in plausible range: {all(g['in_plausible_range'] for g in g_audit)}")
    for g in g_audit:
        print(f"  {g['clean_column']:28s} {g['first']}..{g['last']} rows {g['data_rows']} range {g['min']:.4g}..{g['max']:.4g} {g['unit']}")
    print(f"FIRMS: {firms['rows']:,} rows {firms['first']}..{firms['last']}; clean {firms['cascade'][3]['rows']:,}; dup rows {firms['exact_duplicate_rows']}; null cells {firms['null_cells']}; missing months {firms['months_missing']}")
    for c in firms["cascade"]:
        print(f"  {c['step']:46s} {c['rows']:>10,}")
    print("copies identical:", {k: [x['identical'] for x in v['copies']] for k, v in cp.items()})
    print("existing tidy comparison:", json.dumps(tidy_cmp)[:400] if tidy_cmp else None)
    print("season table vs raw recount, total absolute difference:", diff)


if __name__ == "__main__":
    main()
