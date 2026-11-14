"use strict";

const W = 788, H = 270, PAD = { l: 52, r: 16, t: 14, b: 28 };
const NUM = new Intl.NumberFormat("en", { maximumSignificantDigits: 4, useGrouping: false });
const num = v => (v == null ? "–" : NUM.format(v));
const known = vs => vs.filter(v => v != null && Number.isFinite(v));

function nice(lo, hi, n = 4) {
  if (lo === hi) { lo -= 1; hi += 1; }
  const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw)), f = raw / mag;
  const step = mag * (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10);
  const a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step;
  const ticks = [];
  for (let v = a; v <= b + step / 2; v += step) ticks.push(+v.toFixed(10));
  return { lo: a, hi: b, ticks };
}

function scale(d0, d1, r0, r1) {
  return v => (d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) / (d1 - d0)) * (r1 - r0));
}

function yearMonth(x) {
  if (Number.isInteger(x)) return String(x);
  const y = Math.floor(x);
  return `${y}-${String(Math.min(12, Math.floor((x - y) * 12) + 1)).padStart(2, "0")}`;
}

function xTicks(x0, x1) {
  const span = x1 - x0, step = span > 90 ? 20 : span > 45 ? 10 : span > 18 ? 5 : span > 8 ? 2 : 1;
  const out = [];
  for (let v = Math.ceil(x0 / step) * step; v <= x1; v += step) out.push(v);
  return out;
}

const monthName = m => new Date(2000, m - 1, 1).toLocaleString(S.lang, { month: "short" });

function frame(xs, ys, unit, months = false) {
  const top = unit ? PAD.t + 12 : PAD.t;
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const yn = nice(Math.min(...ys), Math.max(...ys));
  const sx = scale(x0, x1, PAD.l, W - PAD.r), sy = scale(yn.lo, yn.hi, H - PAD.b, top);
  const grid = yn.ticks.map(v => `<line class="grid" x1="${PAD.l}" x2="${W - PAD.r}" y1="${sy(v)}" y2="${sy(v)}"/>`
    + `<text x="${PAD.l - 8}" y="${sy(v) + 4}" text-anchor="end">${num(v)}</text>`).join("");
  const xt = (months ? xs : xTicks(x0, x1)).map(v => `<text x="${sx(v)}" y="${H - 8}" text-anchor="middle">${months ? esc(monthName(v)) : num(v)}</text>`).join("");
  const u = unit ? `<text x="4" y="11">${esc(unit)}</text>` : "";
  return { sx, sy, top, axes: grid + xt + u };
}

function points(xs, ys, sx, sy) {
  return xs.flatMap((x, i) => (ys[i] == null ? [] : [`${sx(x).toFixed(1)},${sy(ys[i]).toFixed(1)}`])).join(" ");
}

function svg(c, h, body, w = W) {
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(c.title)}">${body}</svg>`;
}

function line(c, opts = {}) {
  const dots = c.x.length <= 60 && !c.compare;
  const ys = known([...c.y, ...(c.compare ?? []), ...(c.band ?? []).flatMap(b => [b[1], b[2]]), ...(c.trend ?? []).map(p => p[1])]);
  const { sx, sy, top, axes } = frame(c.x, ys, dots ? "" : c.unit, opts.months);
  let body = axes;
  if (c.band) {
    const up = c.band.map(([x, , hi]) => `${sx(x).toFixed(1)},${sy(hi).toFixed(1)}`);
    const down = c.band.map(([x, lo]) => `${sx(x).toFixed(1)},${sy(lo).toFixed(1)}`).reverse();
    body += `<polygon class="band" points="${[...up, ...down].join(" ")}"/>`;
  }
  if (c.mark_year != null) {
    body += `<line class="mark" x1="${sx(c.mark_year)}" x2="${sx(c.mark_year)}" y1="${top}" y2="${H - PAD.b}"/>`
      + `<text x="${sx(c.mark_year) + 6}" y="${top + 10}">${esc(c.mark_year)}</text>`;
  }
  if (c.compare) body += `<polyline class="series" points="${points(c.x, c.compare, sx, sy)}"/>`;
  if (dots) {
    body += c.x.map((x, i) => (c.y[i] == null ? "" : `<circle class="dot" cx="${sx(x).toFixed(1)}" cy="${sy(c.y[i]).toFixed(1)}" r="3.4"><title>${esc(yearMonth(x))}: ${num(c.y[i])} ${esc(c.unit)}</title></circle>`)).join("");
  } else {
    body += `<polyline class="series${c.compare ? " main" : " thin"}" points="${points(c.x, c.y, sx, sy)}"/>`;
  }
  if (c.trend) {
    const [[a, b], [p, q]] = c.trend;
    body += `<line class="trend" x1="${sx(a)}" y1="${sy(b)}" x2="${sx(p)}" y2="${sy(q)}"/>`;
  }
  const keys = c.compare ? [["k-thin", t("chart.compare")], ["k-trend", t("chart.recent")]]
    : [dots ? ["k-dot", t("chart.each_year")] : ["k-thin", t("chart.each_month")]];
  if (c.trend) keys.push(["k-trend", t("chart.trend")]);
  if (c.band) keys.push(["k-band", opts.band ?? t("chart.band")]);
  if (c.mark_year != null) keys.push(["k-mark", t("chart.mark")]);
  return {
    svg: svg(c, H, body), keys, each: dots ? t("chart.each_dot", { unit: c.unit }) : "",
    head: [t("chart.x"), esc(c.unit), ...(c.compare ? [t("chart.compare")] : [])],
    rows: c.x.map((x, i) => [yearMonth(x), num(c.y[i]), ...(c.compare ? [num(c.compare[i])] : [])]),
  };
}

function bars(c) {
  const row = 26, h = PAD.t + 26 + c.labels.length * row + 12, left = 168;
  const vs = c.values, lo = Math.min(0, ...vs), hi = Math.max(0, ...vs);
  const sx = scale(lo, hi, left, W - PAD.r - 56);
  const body = c.labels.map((label, i) => {
    const y = PAD.t + 26 + i * row, x0 = sx(Math.min(0, vs[i])), x1 = sx(Math.max(0, vs[i]));
    return `<text x="${left - 8}" y="${y + 16}" text-anchor="end">${esc(label)}</text>`
      + `<rect class="bar${c.highlight[i] ? " hl" : ""}" x="${x0}" y="${y + 4}" width="${Math.max(1, x1 - x0)}" height="${row - 8}" rx="3"/>`
      + `<text x="${x1 + 6}" y="${y + 16}">${num(vs[i])}</text>`;
  }).join("");
  const u = `<text x="${left}" y="${PAD.t + 8}">${esc(c.unit)}</text><line class="axis" x1="${sx(0)}" x2="${sx(0)}" y1="${PAD.t + 26}" y2="${h - 8}"/>`;
  return { svg: svg(c, h, u + body), keys: [], each: "", head: [t("chart.label"), esc(c.unit)], rows: c.labels.map((l, i) => [l, num(vs[i])]) };
}

function scatter(c) {
  const xs = c.points.map(p => p[0]), ys = c.points.map(p => p[1]);
  const { sx, sy, axes } = frame(xs, ys, c.y_label);
  const body = axes + c.points.map(([x, y, label]) => `<circle class="dot" cx="${sx(x)}" cy="${sy(y)}" r="4"><title>${esc(label)}: ${num(x)}, ${num(y)}</title></circle>`).join("")
    + `<text x="${W - PAD.r}" y="${H - PAD.b - 6}" text-anchor="end">${esc(c.x_label)}</text>`;
  return { svg: svg(c, H, body), keys: [], each: "", head: [t("chart.label"), esc(c.x_label), esc(c.y_label)], rows: c.points.map(([x, y, l]) => [l, num(x), num(y)]) };
}

function cells(c) {
  const [dlat, dlon] = c.cell_size;
  const lats = c.cells.map(r => r[0]), lons = c.cells.map(r => r[1]);
  const la0 = Math.min(...lats) - dlat / 2, la1 = Math.max(...lats) + dlat / 2, lo0 = Math.min(...lons) - dlon / 2, lo1 = Math.max(...lons) + dlon / 2;
  const side = Math.min((W - 32) / (lo1 - lo0), 360 / (la1 - la0));
  const w = (lo1 - lo0) * side, h = (la1 - la0) * side;
  const max = Math.max(...c.cells.map(r => Math.abs(r[2]))) || 1;
  const body = c.cells.map(([lat, lon, v, clear]) => {
    const s = Math.round(Math.abs(v) / max * 100);
    const tone = (v >= 0) === c.warm_up ? "warm" : "cool";
    return `<rect class="cell ${tone}${clear ? " clear" : ""}" style="--s:${s}%" x="${(lon - dlon / 2 - lo0) * side}" y="${(la1 - lat - dlat / 2) * side}" width="${dlon * side}" height="${dlat * side}"><title>${num(lat)}, ${num(lon)}: ${num(v)} ${esc(c.unit)}</title></rect>`;
  }).join("");
  return {
    svg: svg(c, h, body, w).replace('class="chart"', 'class="chart cells"'), each: "",
    keys: [["k-warm", t("chart.cell_up")], ["k-cool", t("chart.cell_down")], ["k-clear", t("chart.cell_clear")]],
    head: [t("chart.lat"), t("chart.lon"), esc(c.unit), t("chart.clear")],
    rows: c.cells.map(([lat, lon, v, clear]) => [num(lat), num(lon), num(v), clear ? t("chart.yes") : t("chart.no")]),
  };
}

function intervals(c) {
  const row = 28, left = 168, h = PAD.t + 26 + c.rows.length * row + 12;
  const lo = Math.min(0, ...c.rows.map(r => r[2])), hi = Math.max(0, ...c.rows.map(r => r[3]));
  const sx = scale(lo, hi, left, W - PAD.r - 8);
  const body = `<text x="${left}" y="${PAD.t + 8}">${esc(c.unit)}</text><line class="axis" x1="${sx(0)}" x2="${sx(0)}" y1="${PAD.t + 26}" y2="${h - 8}"/>`
    + c.rows.map(([label, v, a, b, hl], i) => {
      const y = PAD.t + 26 + i * row + row / 2;
      return `<text x="${left - 8}" y="${y + 4}" text-anchor="end">${esc(label)}</text>`
        + `<line class="whisker${hl ? " hl" : ""}" x1="${sx(a)}" x2="${sx(b)}" y1="${y}" y2="${y}"/>`
        + `<circle class="dot${hl ? " hl" : ""}" cx="${sx(v)}" cy="${y}" r="4.5"><title>${esc(label)}: ${num(v)} (${num(a)} to ${num(b)})</title></circle>`;
    }).join("");
  return { svg: svg(c, h, body), keys: [], each: "", head: [t("chart.label"), esc(c.unit), t("chart.low"), t("chart.high")], rows: c.rows.map(([l, v, a, b]) => [l, num(v), num(a), num(b)]) };
}

function legend(keys, note = "") {
  const items = keys.map(([cls, text]) => `<span><i class="${cls}" aria-hidden="true"></i>${text}</span>`).join("");
  return items || note ? `<div class="legend">${items}${note ? `<span class="legend-note">${note}</span>` : ""}</div>` : "";
}

function valuesTable(head, rows) {
  return `<div class="scroll"><table class="values"><thead><tr>${head.map(h => `<th scope="col">${h}</th>`).join("")}</tr></thead>`
    + `<tbody>${rows.map(r => `<tr>${r.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

// Read by tests/test_web_sync.py: one key per line between `const CHARTS = {` and `};`.
const CHARTS = {
  line,
  bars,
  scatter,
  cells,
  intervals,
};
