"""Error audit of the where map and the claim check (docs/03, docs/05, docs/07). usage: python tools/error_audit.py
Every verdict comes from earthbuddy.stats itself. The seed is fixed, so a rerun prints the same numbers."""
import math
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from earthbuddy import stats  # noqa: E402

SEED = 20261115
PARTS = 10           # each row runs as this many jobs, each with its own seed, so the pool uses every core
MAPS = 1200
CLAIMS = 4000
SINGLES = 4000
MAP_ROWS = [  # (rows, cols, years, memory, spatial length in cells)
    (8, 6, 24, 0.17, 0), (8, 6, 24, 0.17, 1.5), (8, 6, 24, 0.17, 3),
    (9, 7, 45, 0.24, 19),   # the real map: neighbour correlation exp(-1/19) = 0.95 on the cached NASA T2M grid
]
MAP_TREND = 0.6      # standard deviations per decade
CLAIM_ROWS = [("both null", 0.0, 0.0), ("heat true 1.0, rain null", 1.0, 0.0), ("both 0.6", 0.6, 0.6), ("both 1.0", 1.0, 1.0)]
HEAT_MEMORY, RAIN_MEMORY, CLAIM_YEARS = 0.17, 0.04, 24
SINGLE_MEMORY = [0, 0.04, 0.17, 0.33, 0.5]
VERDICTS = ("claim.supported", "claim.step", "claim.mixed", "claim.opposed", "claim.unsupported", "claim.nothing")


def years(n: int) -> list[int]:
    return list(range(2001, 2001 + n))


def ar1(rng: np.random.Generator, phi: float, runs: int, n: int) -> np.ndarray:
    """AR(1) rows with marginal standard deviation 1, after a burn-in."""
    s, x, out = math.sqrt(1 - phi * phi), rng.standard_normal(runs), np.empty((runs, n))
    for t in range(-60, n):
        x = phi * x + s * rng.standard_normal(runs)
        if t >= 0:
            out[:, t] = x
    return out


def field(job: tuple) -> list[tuple[bool, float]]:
    """(the map reads where.clear, the largest |cell slope| per decade) for each map."""
    rows, cols, n, phi, length, trend, maps, seed = job
    rng, ys = np.random.default_rng(seed), years(n)
    ij = np.array([(i, j) for i in range(rows) for j in range(cols)], float)
    d = np.hypot(*(ij[:, None, :] - ij[None, :, :]).transpose(2, 0, 1))
    corr = np.eye(len(ij)) if length == 0 else np.exp(-d / length)
    chol = np.linalg.cholesky(corr + 1e-10 * np.eye(len(ij)))
    s, out = math.sqrt(1 - phi * phi), []
    for _ in range(maps):
        x, cells = chol @ rng.standard_normal(len(ij)), np.empty((n, len(ij)))
        for t in range(-60, n):
            x = phi * x + s * (chol @ rng.standard_normal(len(ij)))
            if t >= 0:
                cells[t] = x + trend / 10 * t
        fits = [stats.trend_test(ys, list(cells[:, c])) for c in range(len(ij))]
        out.append((any(stats.field_test(fits)[0]), max(abs(f.slope_per_decade) for f in fits)))
    return out


def claim(job: tuple) -> list[str]:
    """The verdict key of "hotter and drier" for each run, scored as earthbuddy/analyses/claim.py scores it."""
    heat, rain, runs, seed = job
    rng, ys = np.random.default_rng(seed), years(CLAIM_YEARS)
    h = ar1(rng, HEAT_MEMORY, runs, CLAIM_YEARS) + heat / 10 * np.arange(CLAIM_YEARS)
    r = ar1(rng, RAIN_MEMORY, runs, CLAIM_YEARS) - rain / 10 * np.arange(CLAIM_YEARS)
    keys = []
    for a, b in zip(h, r):
        tests = []
        for y, direction in ((list(a), "up"), (list(b), "down")):
            fit = stats.trend_test(ys, y)
            tests.append((stats.test_claim(fit, direction, ys, y), stats.claim_p(fit, direction)))
        keys.append(stats.claim_verdict(tests).verdict.key)
    return keys


def single(job: tuple) -> list[bool]:
    """A one-part claim "rising" on a series with no trend: does it read supported or step?"""
    phi, runs, seed = job
    ys = years(24)
    out = []
    for y in ar1(np.random.default_rng(seed), phi, runs, 24):
        y = list(y)
        out.append(stats.test_claim(stats.trend_test(ys, y), "up", ys, y) in ("supported", "step"))
    return out


def run(pool: Pool, fn, rows: list[tuple], runs: int, offset: int) -> list[list]:
    """Each row split into PARTS jobs; returns the joined results per row."""
    jobs = [(*row, runs // PARTS, SEED + offset + 100 * i + k) for i, row in enumerate(rows) for k in range(PARTS)]
    got = pool.map(fn, jobs)
    return [[x for part in got[i * PARTS:(i + 1) * PARTS] for x in part] for i in range(len(rows))]


def pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def main() -> None:
    with Pool() as pool:
        null = run(pool, field, [(*r, 0.0) for r in MAP_ROWS], MAPS, 1000)
        trend = run(pool, field, [(*r, MAP_TREND) for r in MAP_ROWS], MAPS, 2000)
        claims = run(pool, claim, [(h, r) for _, h, r in CLAIM_ROWS], CLAIMS, 3000)
        singles = run(pool, single, [(phi,) for phi in SINGLE_MEMORY], SINGLES, 4000)

    print(f"(1) Where map: share of maps that read where.clear (stats.field_test, q < {stats.T.field_q})")
    print(f"    {'map':<46} {'no trend':>9} {'maps':>5}   {f'{MAP_TREND} sd/decade':>14} {'maps':>5}  largest cell slope, mean")
    for (rows, cols, n, phi, length), a, b in zip(MAP_ROWS, null, trend):
        name = f"{rows}x{cols} cells, {n} years, memory {phi}, length {length:g}"
        print(f"    {name:<46} {pct(np.mean([c for c, _ in a])):>9} {len(a):>5}   "
              f"{pct(np.mean([c for c, _ in b])):>14} {len(b):>5}  {np.mean([s for _, s in b]):.2f} sd/decade")

    print(f"\n(2) Claim \"hotter and drier\": heat memory {HEAT_MEMORY} up, rain memory {RAIN_MEMORY} down, "
          f"{CLAIM_YEARS} years, share of each verdict key")
    print(f"    {'truth':<26}" + "".join(f"{k.removeprefix('claim.'):>12}" for k in VERDICTS) + f"{'runs':>7}")
    shares = {}
    for (name, _, _), keys in zip(CLAIM_ROWS, claims):
        c = Counter(keys)
        shares[name] = {k: c[k] / len(keys) for k in VERDICTS}
        print(f"    {name:<26}" + "".join(f"{pct(shares[name][k]):>12}" for k in VERDICTS) + f"{len(keys):>7}")

    print("\n(3) One series, no trend, 24 years: share where test_claim(..., \"up\") is supported or step")
    for phi, hits in zip(SINGLE_MEMORY, singles):
        print(f"    memory {phi:<5} {pct(np.mean(hits))}  of {len(hits)}")

    bad = [f"map {r}: no-trend {np.mean([c for c, _ in a]):.3f} > 0.06" for r, a in zip(MAP_ROWS, null)
           if np.mean([c for c, _ in a]) > 0.06]
    bad += [f"claim {k}: supported {shares[k]['claim.supported']:.3f} > 0.05"
            for k in ("both null", "heat true 1.0, rain null") if shares[k]["claim.supported"] > 0.05]
    if shares["both 1.0"]["claim.supported"] < 0.52:
        bad.append(f"claim both 1.0: supported {shares['both 1.0']['claim.supported']:.3f} < 0.52")
    print("\nacceptance:", "FAILED\n    " + "\n    ".join(bad) if bad else "all lines hold")
    assert not bad, bad


if __name__ == "__main__":
    main()
