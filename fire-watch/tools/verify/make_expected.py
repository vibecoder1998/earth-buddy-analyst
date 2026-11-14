"""Independent reference numbers for the browser check (browser_check.js).

    python -I fire-watch/tools/verify/make_expected.py <output folder> <folder with fire_archive_*.csv> <folder with the 8 Giovanni CSVs>

Everything is recomputed from the RAW CSVs, not from the tabs' embedded tables and not from our own stats module: trends and p-values come from
pymannkendall, scipy and statsmodels, and the Pettitt test is written a second way (rank sums instead of pairwise signs). The only thing taken from the
build is the list of 25 province centre points and the five-region grouping (their nearest-centre assignment is checked separately, with a plain
distance matrix instead of a KD-tree, by `build_fire_watch.py verify`).

Writes _exp_fire.json, _exp_soot.json, _exp_province.json, _exp_water.json into the output folder (temporary: delete them after the check).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pymannkendall as pmk
from scipy import stats as sps
from scipy.stats import rankdata
from statsmodels.stats.multitest import multipletests

OUT, FIRMS, GIO = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_fire_watch as B  # noqa: E402  (only gpw_centres() and REGIONS)

SAT = {"aqua": ["Aqua"], "terra": ["Terra"], "both": ["Aqua", "Terra"]}


# ---------------------------------------------------------------- statistics, library versions
def lag1_detrended(y):
    n = len(y); t = np.arange(n, dtype=float)
    b = np.median([(y[j] - y[i]) / (j - i) for i in range(n - 1) for j in range(i + 1, n)])
    d = y - b * t; m = d.mean()
    return float(((d[:-1] - m) * (d[1:] - m)).sum() / ((d - m) ** 2).sum())


def pettitt_ranksum(x):
    n = len(x); r = rankdata(x)
    u = np.array([2 * r[:t + 1].sum() - (t + 1) * (n + 1) for t in range(n - 1)])
    k = np.abs(u).max()
    return int(np.abs(u).argmax()), float(min(1, 2 * np.exp(-6 * k ** 2 / (n ** 3 + n ** 2))))


def lib_trend(x, yrs):
    """what a tab shows for a yearly series: Sen slope, Mann-Kendall p (pre-whitened when the memory is large), Pettitt step."""
    x = np.asarray(x, float); n = len(x)
    if n < 4:
        return None
    mk = pmk.original_test(x); r1 = lag1_detrended(x); big = abs(r1) > 1.96 / np.sqrt(n)
    p = pmk.trend_free_pre_whitening_modification_test(x).p if big else mk.p
    idx, sp = pettitt_ranksum(x)
    return dict(p=float(p), pct_per_decade=float(100 * mk.slope * 10 / x.mean()), sen_per_decade=float(mk.slope * 10), memory_r1=r1, step_after=int(yrs[idx]), step_p=sp, mean=float(x.mean()))


def read_giovanni(token, scale=1.0):
    f = next(p for p in sorted(GIO.glob("*.csv")) if token in p.name)
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    st = next(i for i, l in enumerate(lines) if l.lower().startswith("time"))
    d = pd.read_csv(f, skiprows=st, skipinitialspace=True)
    d.columns = ["t", "v"]
    d = d[d.v.abs() < 1e10]
    d["t"] = pd.to_datetime(d.t)
    return d.set_index("t").v * scale


# ---------------------------------------------------------------- raw FIRMS, cleaned the documented way
archive = next(FIRMS.glob("fire_archive_*.csv"))
raw = pd.read_csv(archive, usecols=["latitude", "longitude", "acq_date", "satellite", "confidence", "type"])
d = raw[(raw.type == 0) & (raw.confidence >= 30)].copy()
dt = pd.to_datetime(d.acq_date)
d["y"], d["m"] = dt.dt.year.values, dt.dt.month.values
d["season"] = d.y + (d.m >= 11)
ins = d[d.m.isin([11, 12, 1, 2, 3, 4])].copy()
c = B.gpw_centres()
k = np.cos(np.radians(12.6))
d2 = (ins.latitude.values[:, None] - c.lat.values[None, :]) ** 2 + ((ins.longitude.values[:, None] - c.lon.values[None, :]) * k) ** 2
ins["prov"] = c.province.values[d2.argmin(axis=1)]
region_of = {p: key for key, _, members in B.REGIONS for p in members}
mon_counts = d.groupby(["satellite", "y", "m"]).size()
season_tot = ins.groupby(["satellite", "season"]).size()

# ---------------------------------------------------------------- fire tab
FIRE_CASES = [("aqua", 2003, 2022), ("terra", 2003, 2022), ("both", 2003, 2022), ("aqua", 2010, 2018), ("terra", 2005, 2026),
              ("both", 2003, 2026), ("aqua", 2015, 2015), ("both", 2018, 2024), ("aqua", 2003, 2008), ("terra", 2012, 2024),
              ("aqua", 2004, 2021), ("terra", 2008, 2019), ("both", 2011, 2025), ("aqua", 2019, 2026)]
fire = []
for sat, f, t in FIRE_CASES:
    seas = list(range(f, t + 1))
    ser = {key: [int(((ins.satellite.isin(SAT[key])) & (ins.season == s)).sum()) for s in seas] for key in ("aqua", "terra", "both")}
    sub = ins[ins.satellite.isin(SAT[sat]) & ins.season.between(f, t)]
    prov = {p: int((sub.prov == p).sum()) for p in c.province}
    reg = {key: 0 for key, _, _ in B.REGIONS}
    for p, v in prov.items():
        reg[region_of[p]] += v
    mon = [0] * 12
    sel = d[d.satellite.isin(SAT[sat])]
    for fy in [s for s in seas if s <= min(t, 2025)]:
        for kk in range(12):
            m = ((10 + kk) % 12) + 1
            y = fy - 1 if m >= 11 else fy
            mon[m - 1] += int(((sel.y == y) & (sel.m == m)).sum())
    fire.append(dict(sat=sat, f=f, t=t, total=int(sub.shape[0]), series=ser, prov=prov, reg=reg, mon=mon,
                     stats={key: lib_trend(ser[key], seas) for key in ("aqua", "terra", "both")}))
(OUT / "_exp_fire.json").write_text(json.dumps(fire, separators=(",", ":")), encoding="utf-8")

# ---------------------------------------------------------------- soot tab
VARS = {"bc": read_giovanni("BCSMASS", 1e9), "pm25": read_giovanni("TOTSMASS25", 1e9), "aod": read_giovanni("TOTEXTTAU", 1.0)}
SOOT_WINDOWS = [("aqua", 2003, 2022), ("terra", 2005, 2024), ("both", 2010, 2018), ("aqua", 2003, 2024), ("both", 2015, 2015), ("terra", 2003, 2012), ("aqua", 2008, 2020), ("both", 2004, 2023)]
soot = []
for meas, ser in VARS.items():
    for sat, f, t in SOOT_WINDOWS:
        names = SAT[sat]
        w0, w1 = (f - 1) * 12 + 10, min(t * 12 + 9, 2024 * 12 + 11)
        fm = np.array([sum(int(mon_counts.get((n, x // 12, x % 12 + 1), 0)) for n in names) for x in range(w0, w1 + 1)], float)
        cal = np.array([x % 12 + 1 for x in range(w0, w1 + 1)])
        bcw = np.array([ser.loc[pd.Timestamp(year=x // 12, month=x % 12 + 1, day=1)] for x in range(w0, w1 + 1)])
        rec = dict(meas=meas, sat=sat, f=f, t=t, nMonths=int(len(fm)), meanBC=float(bcw.mean()) if len(bcw) else None)
        climF = np.array([fm[cal == m].mean() if (cal == m).any() else 0 for m in range(1, 13)])
        climB = np.array([bcw[cal == m].mean() if (cal == m).any() else 0 for m in range(1, 13)])
        rec["climF"], rec["climB"] = climF.tolist(), climB.tolist()
        if len(fm) >= 36:
            rec["raw"] = list(map(float, sps.spearmanr(fm, bcw)))
            rec["anom"] = list(map(float, sps.spearmanr(fm - climF[cal - 1], bcw - climB[cal - 1])))
        seas, pts = [], []
        for s in range(f, min(t, 2024) + 1):
            vals = [ser.loc[pd.Timestamp(year=(s - 1 if m >= 11 else s), month=m, day=1)] for m in (11, 12, 1, 2, 3, 4)]
            seas.append(s); pts.append((float(np.mean(vals)), int(sum(season_tot.get((n, s), 0) for n in names))))
        if len(pts) >= 5:
            r = sps.spearmanr([p[0] for p in pts], [p[1] for p in pts])
            rec["year"] = [float(r.statistic), float(r.pvalue), len(pts)]
        if len(pts) >= 4:
            rec["dry"] = lib_trend([p[0] for p in pts], seas)
        soot.append(rec)
(OUT / "_exp_soot.json").write_text(json.dumps(soot, separators=(",", ":")), encoding="utf-8")

# ---------------------------------------------------------------- province trends
prov_out = []
for sat, f, t in [("aqua", 2003, 2022), ("terra", 2003, 2022), ("both", 2005, 2020), ("aqua", 2010, 2026), ("both", 2003, 2026), ("terra", 2012, 2024), ("aqua", 2018, 2024)]:
    seas = list(range(f, t + 1))
    sub = ins[ins.satellite.isin(SAT[sat]) & ins.season.between(f, t)]
    tab = sub.pivot_table(index="season", columns="prov", values="latitude", aggfunc="count", fill_value=0).reindex(index=seas, columns=c.province.tolist(), fill_value=0)
    rec, tested = dict(sat=sat, f=f, t=t, rows=[]), []
    for p in c.province:
        v = tab[p].values.astype(float)
        row = dict(name=p, sum=int(v.sum()), tested=False)
        if len(v) >= 10 and v.sum() >= 200 and len(set(v)) >= 4:
            r = pmk.original_test(v)
            row.update(tested=True, p=float(r.p), pct=float(100 * r.slope * 10 / v.mean())); tested.append(row)
        rec["rows"].append(row)
    if tested:
        for r, fl in zip(tested, multipletests([r["p"] for r in tested], alpha=0.05, method="fdr_bh")[0]):
            r["fdr"] = bool(fl)
    prov_out.append(rec)
(OUT / "_exp_province.json").write_text(json.dumps(prov_out, separators=(",", ":")), encoding="utf-8")

# ---------------------------------------------------------------- rain, soil & heat tab
W = {"imerg": read_giovanni("GPM_3IMERGM"), "m2rain": read_giovanni("PRECTOTLAND", 86400.0), "soil": read_giovanni("GWETROOT"), "t2m": read_giovanni("T2M."), "wet": read_giovanni("T2MWET")}
water = []
for key, s in W.items():
    for f, t in [(2001, 2024), (2003, 2020), (2010, 2024), (2001, 2015), (2016, 2024), (2005, 2022), (2007, 2018), (2012, 2023)]:
        years = np.arange(f, t + 1)
        sub = s[(s.index.year >= f) & (s.index.year <= t)]
        yr = sub.groupby(sub.index.year).mean().values
        n = len(yr); mean = yr.mean()
        mk = pmk.original_test(yr); th = sps.theilslopes(yr, years, 0.95); ols = sps.linregress(years, yr); tc = sps.t.ppf(0.975, n - 2)
        r1 = lag1_detrended(yr); big = abs(r1) > 1.96 / np.sqrt(n)
        p_an = pmk.trend_free_pre_whitening_modification_test(yr).p if big else mk.p
        piv = {m: sub[sub.index.month == m].values for m in range(1, 13)}
        anom = (sub - sub.groupby(sub.index.month).transform("mean")).values
        im = W["imerg"][(W["imerg"].index.year >= f) & (W["imerg"].index.year <= t)]
        m2 = W["m2rain"][(W["m2rain"].index.year >= f) & (W["m2rain"].index.year <= t)]
        ratio = (m2.groupby(m2.index.year).mean() / im.groupby(im.index.year).mean()).values
        idx, rp = pettitt_ranksum(ratio)
        water.append(dict(key=key, f=f, t=t, n=n, mean=float(mean), sen_perdec=float(mk.slope * 10), sen_pct=float(100 * mk.slope * 10 / mean), ci_lo=float(100 * th[2] * 10 / mean), ci_hi=float(100 * th[3] * 10 / mean),
                          mk_p=float(mk.p), an_p=float(p_an), r1=r1, ols_pct=float(100 * ols.slope * 10 / mean), ols_p=float(ols.pvalue),
                          ols_lo=float(100 * (ols.slope - tc * ols.stderr) * 10 / mean), ols_hi=float(100 * (ols.slope + tc * ols.stderr) * 10 / mean),
                          seasonal_p=float(pmk.seasonal_test(sub.values, period=12).p), deseason_p=float(pmk.original_test(anom).p),
                          clim=[float(piv[m].mean()) for m in range(1, 13)], lo=[float(piv[m].min()) for m in range(1, 13)], hi=[float(piv[m].max()) for m in range(1, 13)],
                          ratio=[float(v) for v in ratio], r_after=int(years[idx]), r_p=rp, r_before=float(ratio[:idx + 1].mean()), r_after_mean=float(ratio[idx + 1:].mean())))
(OUT / "_exp_water.json").write_text(json.dumps(water, separators=(",", ":")), encoding="utf-8")
print(f"fire {len(fire)} windows | soot {len(soot)} | province {len(prov_out)} windows | water {len(water)} | reference read from {archive.name} and {len(list(GIO.glob('*.csv')))} Giovanni files")
