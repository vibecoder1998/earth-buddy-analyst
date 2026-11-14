/* Browser half of the check: compares what each tab's own JavaScript computes with the independent reference made by make_expected.py.
   Run it in the console of climate-watch-cambodia.html served over http (python -m http.server from the repo root), after copying the _exp_*.json files
   into fire-watch/data/. It prints one summary per tab. Tolerances: p-values 1e-6 (the page uses a normal-tail approximation accurate to ~1e-7),
   everything else 1e-9 absolute + 1e-7 relative. */
(async () => {
  const get = n => fetch('/fire-watch/data/_exp_' + n + '.json', {cache: 'no-store'}).then(r => r.json());
  const [fireE, sootE, provE, waterE] = await Promise.all(['fire', 'soot', 'province', 'water'].map(get));
  const out = {};
  const sec = n => (out[n] = {cases: 0, checks: 0, fails: [], maxPdiff: 0, maxDiff: 0});
  const T = (A, label, got, want, kind) => {
    A.checks++;
    let ok;
    if (want === null || want === undefined) ok = (got === null || got === undefined);
    else if (typeof want === 'boolean') ok = got === want;
    else if (kind === 'i') ok = got === want;
    else if (!Number.isFinite(got)) ok = false;
    else if (kind === 'p') { const e = Math.abs(got - want); A.maxPdiff = Math.max(A.maxPdiff, e); ok = e <= 1e-6 + 1e-6 * Math.abs(want); }
    else { const e = Math.abs(got - want); A.maxDiff = Math.max(A.maxDiff, e / (1 + Math.abs(want))); ok = e <= 1e-9 + 1e-7 * Math.abs(want); }
    if (!ok && A.fails.length < 8) A.fails.push(`${label}: page ${got} vs reference ${want}`);
  };
  const stat = (A, tag, g, s) => {
    if (s === null || s === undefined) { T(A, tag + ' (should be none)', g, null); return; }
    if (!g) { T(A, tag + ' missing', NaN, s.p); return; }
    T(A, tag + ' p', g.p, s.p, 'p'); T(A, tag + ' pct/dec', g.pct_per_decade, s.pct_per_decade); T(A, tag + ' sen/dec', g.sen_per_decade, s.sen_per_decade);
    T(A, tag + ' lag1', g.memory_r1, s.memory_r1); T(A, tag + ' step year', g.step_after, s.step_after, 'i'); T(A, tag + ' step p', g.step_p, s.step_p, 'p'); T(A, tag + ' mean', g.mean, s.mean);
  };

  // ---- fire tab
  { const A = sec('fire');
    for (const e of fireE) { A.cases++; const tag = `${e.sat} ${e.f}-${e.t}`, r = FireWatch.compute({sat: e.sat, from: e.f, to: e.t});
      T(A, tag + ' total', r.total, e.total, 'i'); T(A, tag + ' seasons', r.n, e.t - e.f + 1, 'i'); T(A, tag + ' map squares sum', r.cellSum, e.total, 'i');
      for (const k of ['aqua', 'terra', 'both']) { e.series[k].forEach((v, i) => T(A, `${tag} ${k} season ${e.f + i}`, r.series[k][i], v, 'i')); stat(A, `${tag} ${k}`, r.stats[k], e.stats[k]); }
      for (const [nm, v] of Object.entries(e.prov)) T(A, `${tag} province ${nm}`, r.prov[nm], v, 'i');
      for (const [k, v] of Object.entries(e.reg)) T(A, `${tag} region ${k}`, r.regions[k], v, 'i');
      e.mon.forEach((v, i) => T(A, `${tag} month ${i + 1}`, r.mon[i], v, 'i')); } }

  // ---- soot & haze tab
  { const A = sec('soot');
    for (const e of sootE) { A.cases++; const tag = `${e.meas} ${e.sat} ${e.f}-${e.t}`, r = SootWatch.compute({meas: e.meas, sat: e.sat, from: e.f, to: e.t});
      T(A, tag + ' months', r.nMonths, e.nMonths, 'i'); T(A, tag + ' mean', r.meanBC, e.meanBC);
      e.climF.forEach((v, i) => T(A, `${tag} fire clim ${i + 1}`, r.climF[i], v)); e.climB.forEach((v, i) => T(A, `${tag} measure clim ${i + 1}`, r.climB[i], v));
      if (e.raw) { T(A, tag + ' rho (months)', r.raw.rho, e.raw[0]); T(A, tag + ' p (months)', r.raw.p, e.raw[1], 'p'); } else T(A, tag + ' no monthly test', r.raw, null);
      if (e.anom) { T(A, tag + ' rho (anomalies)', r.anom.rho, e.anom[0]); T(A, tag + ' p (anomalies)', r.anom.p, e.anom[1], 'p'); } else T(A, tag + ' no anomaly test', r.anom, null);
      if (e.year) { T(A, tag + ' rho (seasons)', r.year.rho, e.year[0]); T(A, tag + ' p (seasons)', r.year.p, e.year[1], 'p'); T(A, tag + ' n (seasons)', r.year.n, e.year[2], 'i'); } else T(A, tag + ' no season test', r.year, null);
      stat(A, tag + ' dry-season trend', r.dry, e.dry); } }

  // ---- province trends
  { const A = sec('province');
    for (const e of provE) { A.cases++; const tag = `${e.sat} ${e.f}-${e.t}`, r = FireWatch.compute({sat: e.sat, from: e.f, to: e.t}).provTrend;
      for (const w of e.rows) { const g = r.find(x => x.name === w.name); T(A, `${tag} ${w.name} sum`, g.sum, w.sum, 'i'); T(A, `${tag} ${w.name} tested`, g.tested, w.tested);
        if (w.tested) { T(A, `${tag} ${w.name} p`, g.p, w.p, 'p'); T(A, `${tag} ${w.name} pct/dec`, g.pct, w.pct); T(A, `${tag} ${w.name} FDR flag`, g.fdr, w.fdr); } } } }

  // ---- rain, soil & heat tab
  { const A = sec('water');
    for (const e of waterE) { A.cases++; const tag = `${e.key} ${e.f}-${e.t}`, r = WaterWatch.compute({meas: e.key, from: e.f, to: e.t});
      T(A, tag + ' years', r.n, e.n, 'i'); T(A, tag + ' mean', r.mean, e.mean); T(A, tag + ' Sen/dec', r.sen.perDec, e.sen_perdec); T(A, tag + ' Sen %', r.sen.pct, e.sen_pct);
      T(A, tag + ' Sen CI low %', r.sen.pctLo, e.ci_lo); T(A, tag + ' Sen CI high %', r.sen.pctHi, e.ci_hi); T(A, tag + ' MK p', r.mkPlain, e.mk_p, 'p'); T(A, tag + ' tab p', r.an.p, e.an_p, 'p');
      T(A, tag + ' lag1', r.an.memory_r1, e.r1); T(A, tag + ' OLS %', r.olsPct, e.ols_pct); T(A, tag + ' OLS p', r.ols.p, e.ols_p, 'p');
      T(A, tag + ' OLS CI low %', 100 * r.ols.lo * 10 / r.mean, e.ols_lo); T(A, tag + ' OLS CI high %', 100 * r.ols.hi * 10 / r.mean, e.ols_hi);
      T(A, tag + ' seasonal MK p', r.seasonal, e.seasonal_p, 'p'); T(A, tag + ' anomaly MK p', r.deseason, e.deseason_p, 'p');
      e.clim.forEach((v, i) => { T(A, `${tag} clim ${i + 1}`, r.climMean[i], v); T(A, `${tag} lowest ${i + 1}`, r.climLo[i], e.lo[i]); T(A, `${tag} highest ${i + 1}`, r.climHi[i], e.hi[i]); });
      e.ratio.forEach((v, i) => T(A, `${tag} ratio ${e.f + i}`, r.ratio[i], v)); T(A, tag + ' ratio break', r.rAfter, e.r_after, 'i'); T(A, tag + ' ratio break p', r.rP, e.r_p, 'p');
      T(A, tag + ' ratio before', r.rBefore, e.r_before); T(A, tag + ' ratio after', r.rAfterMean, e.r_after_mean); } }

  const total = Object.values(out).reduce((a, s) => a + s.checks, 0), bad = Object.values(out).reduce((a, s) => a + s.fails.length, 0);
  return JSON.stringify({total_checks: total, mismatches: bad, sections: Object.fromEntries(Object.entries(out).map(([k, s]) => [k, {cases: s.cases, checks: s.checks, mismatches: s.fails.length, largest_p_difference: s.maxPdiff, largest_relative_difference: s.maxDiff, first_failures: s.fails}]))});
})()
