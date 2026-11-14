// ===================================================================== statistics (ported from fire-watch/tools/stats_tests.py)
// Complementary error function (Numerical Recipes, fractional error < 1.2e-7). It is the only reason this page's p-values differ from scipy's:
// the largest difference we measured is 8e-8.
function erfc(x){ const z = Math.abs(x), t = 1 / (1 + 0.5 * z);
  const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277))))))))); return x >= 0 ? r : 2 - r; }
// upper tail of the standard normal curve, P(Z > z)
const normSf = z => 0.5 * erfc(z / Math.SQRT2);
// Mann-Kendall trend test, same as pymannkendall.original_test: S = pairs that go up minus pairs that go down; ties lower the variance;
// z uses the usual continuity correction (S moved one step towards zero); p is two-sided.
function mannKendall(x){
  const n = x.length; let s = 0;
  for (let i = 0; i < n - 1; i++) for (let j = i + 1; j < n; j++) s += Math.sign(x[j] - x[i]);
  const counts = new Map(); x.forEach(v => counts.set(v, (counts.get(v) || 0) + 1));
  let tie = 0; counts.forEach(t => { if (t > 1) tie += t * (t - 1) * (2 * t + 5); });
  const v = (n * (n - 1) * (2 * n + 5) - tie) / 18, z = s > 0 ? (s - 1) / Math.sqrt(v) : s < 0 ? (s + 1) / Math.sqrt(v) : 0;
  return {s, z, p: 2 * normSf(Math.abs(z)), n};
}
// Sen slope: the median of all pairwise slopes, so one odd value cannot drag it. The intercept is the median of x - b*t,
// which is how the dashed trend line is placed.
function senSlope(x, t){
  const n = x.length, sl = [];
  for (let i = 0; i < n - 1; i++) for (let j = i + 1; j < n; j++) sl.push((x[j] - x[i]) / (t[j] - t[i]));
  const b = median(sl); return {b, a: median(x.map((v, i) => v - b * t[i]))};
}
// lag-1 autocorrelation: how strongly one value predicts the next (year-to-year memory). Positive memory makes plain Mann-Kendall over-confident.
function lag1(x){ const m = mean(x); let den = 0, num = 0; for (let i = 0; i < x.length; i++) den += (x[i] - m) ** 2; if (den === 0) return 0;
  for (let i = 0; i < x.length - 1; i++) num += (x[i] - m) * (x[i + 1] - m); return num / den; }
// Trend-free pre-whitening (Yue et al. 2002): remove the Sen trend, remove the lag-1 memory from what is left, put the trend back,
// then run Mann-Kendall. Returns that test and the memory r1 that was removed.
function tfpw(x){
  const n = x.length, t = x.map((_, i) => i), b = senSlope(x, t).b, det = x.map((v, i) => v - b * i), r1 = lag1(det);
  const y = []; for (let i = 1; i < n; i++) y.push(det[i] - r1 * det[i - 1] + b * i);
  return {mk: mannKendall(y), r1, b};
}
// Pettitt change-point test: finds the single split after which the series jumps to a new level. index = the last point before the jump;
// p uses Pettitt's approximation 2*exp(-6K^2/(n^3+n^2)).
function pettitt(x){
  const n = x.length; let best = -1, bi = 0;
  for (let t = 0; t < n - 1; t++) { let u = 0; for (let i = 0; i <= t; i++) for (let j = t + 1; j < n; j++) u += Math.sign(x[i] - x[j]); if (Math.abs(u) > best) { best = Math.abs(u); bi = t; } }
  return {index: bi, k: best, p: Math.min(1, 2 * Math.exp(-6 * best * best / (n ** 3 + n ** 2)))};
}
// What every tab shows for a yearly series: plain Mann-Kendall, or the pre-whitened version when |lag-1| > 1.96/sqrt(n) (the usual 95% bound
// for memory), plus the Sen rate (also as % of the mean per decade) and the Pettitt step.
// Verdict: p < 0.05 a trend, p < 0.10 borderline, otherwise no significant trend.
function analyse(vals, yrs){                         // same as run_tests() in build_fire_watch.py
  const n = vals.length; if (n < 4) return null;
  const mk = mannKendall(vals), b = senSlope(vals, yrs).b, tf = tfpw(vals), sig = Math.abs(tf.r1) > 1.96 / Math.sqrt(n), p = sig ? tf.mk.p : mk.p, pet = pettitt(vals), m = mean(vals);
  const sd = Math.sqrt(vals.reduce((a, v) => a + (v - m) ** 2, 0) / (n - 1));
  const verdict = p < 0.05 ? (b > 0 ? "increasing" : "decreasing") : p < 0.10 ? "borderline" : "no significant trend";
  return {n, mean: m, sd, sen_per_decade: b * 10, pct_per_decade: m ? 100 * b * 10 / m : null, p, p_raw: mk.p, memory_r1: tf.r1, prewhitened: sig, verdict, step_after: yrs[pet.index], step_p: pet.p, slope: b};
}
