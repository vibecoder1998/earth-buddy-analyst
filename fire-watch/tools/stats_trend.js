// ===================================================================== statistics (ported from fire-watch/tools/stats_tests.py)
function erfc(x){ const z = Math.abs(x), t = 1 / (1 + 0.5 * z);
  const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277))))))))); return x >= 0 ? r : 2 - r; }
const normSf = z => 0.5 * erfc(z / Math.SQRT2);
function mannKendall(x){
  const n = x.length; let s = 0;
  for (let i = 0; i < n - 1; i++) for (let j = i + 1; j < n; j++) s += Math.sign(x[j] - x[i]);
  const counts = new Map(); x.forEach(v => counts.set(v, (counts.get(v) || 0) + 1));
  let tie = 0; counts.forEach(t => { if (t > 1) tie += t * (t - 1) * (2 * t + 5); });
  const v = (n * (n - 1) * (2 * n + 5) - tie) / 18, z = s > 0 ? (s - 1) / Math.sqrt(v) : s < 0 ? (s + 1) / Math.sqrt(v) : 0;
  return {s, z, p: 2 * normSf(Math.abs(z)), n};
}
function senSlope(x, t){
  const n = x.length, sl = [];
  for (let i = 0; i < n - 1; i++) for (let j = i + 1; j < n; j++) sl.push((x[j] - x[i]) / (t[j] - t[i]));
  const b = median(sl); return {b, a: median(x.map((v, i) => v - b * t[i]))};
}
function lag1(x){ const m = mean(x); let den = 0, num = 0; for (let i = 0; i < x.length; i++) den += (x[i] - m) ** 2; if (den === 0) return 0;
  for (let i = 0; i < x.length - 1; i++) num += (x[i] - m) * (x[i + 1] - m); return num / den; }
function tfpw(x){
  const n = x.length, t = x.map((_, i) => i), b = senSlope(x, t).b, det = x.map((v, i) => v - b * i), r1 = lag1(det);
  const y = []; for (let i = 1; i < n; i++) y.push(det[i] - r1 * det[i - 1] + b * i);
  return {mk: mannKendall(y), r1, b};
}
function pettitt(x){
  const n = x.length; let best = -1, bi = 0;
  for (let t = 0; t < n - 1; t++) { let u = 0; for (let i = 0; i <= t; i++) for (let j = t + 1; j < n; j++) u += Math.sign(x[i] - x[j]); if (Math.abs(u) > best) { best = Math.abs(u); bi = t; } }
  return {index: bi, k: best, p: Math.min(1, 2 * Math.exp(-6 * best * best / (n ** 3 + n ** 2)))};
}
function analyse(vals, yrs){                         // same as run_tests() in build_fire_watch.py
  const n = vals.length; if (n < 4) return null;
  const mk = mannKendall(vals), b = senSlope(vals, yrs).b, tf = tfpw(vals), sig = Math.abs(tf.r1) > 1.96 / Math.sqrt(n), p = sig ? tf.mk.p : mk.p, pet = pettitt(vals), m = mean(vals);
  const sd = Math.sqrt(vals.reduce((a, v) => a + (v - m) ** 2, 0) / (n - 1));
  const verdict = p < 0.05 ? (b > 0 ? "increasing" : "decreasing") : p < 0.10 ? "borderline" : "no significant trend";
  return {n, mean: m, sd, sen_per_decade: b * 10, pct_per_decade: m ? 100 * b * 10 / m : null, p, p_raw: mk.p, memory_r1: tf.r1, prewhitened: sig, verdict, step_after: yrs[pet.index], step_p: pet.p, slope: b};
}
