"use strict";

const W = 640, PAD = { l: 64, r: 16, t: 40, b: 34 };
const NUM = new Intl.NumberFormat("en", { maximumSignificantDigits: 4, useGrouping: false });
const num = v => (v == null ? "–" : NUM.format(v));
const known = vs => vs.filter(v => v != null && Number.isFinite(v));

function nice(lo, hi, n = 5) {
  if (lo === hi) { lo -= 1; hi += 1; }
  const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw)), f = raw / mag;
  const step = mag * (f >= 7.5 ? 10 : f >= 3.5 ? 5 : f >= 1.5 ? 2 : 1);
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

function frame(xs, ys, h, unit) {
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const yn = nice(Math.min(...ys), Math.max(...ys));
  const sx = scale(x0, x1, PAD.l, W - PAD.r), sy = scale(yn.lo, yn.hi, h - PAD.b, PAD.t);
  const grid = yn.ticks.map(v => `<line class="grid" x1="${PAD.l}" x2="${W - PAD.r}" y1="${sy(v)}" y2="${sy(v)}"/>`
    + `<text class="tick" x="${PAD.l - 8}" y="${sy(v) + 4}" text-anchor="end">${num(v)}</text>`).join("");
  const xt = nice(x0, x1, 6).ticks.filter(v => v >= x0 && v <= x1).map(v => `<text class="tick" x="${sx(v)}" y="${h - PAD.b + 20}" text-anchor="middle">${num(v)}</text>`).join("");
  const u = unit ? `<text class="unit" x="0" y="${PAD.t - 18}">${esc(unit)}</text>` : "";
  return { sx, sy, axes: grid + xt + u + `<line class="axis" x1="${PAD.l}" x2="${W - PAD.r}" y1="${h - PAD.b}" y2="${h - PAD.b}"/>` };
}

function path(xs, ys, sx, sy) {
  let d = "", pen = false;
  xs.forEach((x, i) => {
    if (ys[i] == null) { pen = false; return; }
    d += `${pen ? "L" : "M"}${sx(x).toFixed(1)},${sy(ys[i]).toFixed(1)}`;
    pen = true;
  });
  return d;
}

function svg(c, h, body) {
  return `<svg class="chart" viewBox="0 0 ${W} ${h}" role="img" aria-label="${esc(c.title)}">${body}</svg>`;
}

function legend(items) {
  return items.length ? `<ul class="legend">${items.map(([cls, text]) => `<li><span class="key ${cls}"></span>${text}</li>`).join("")}</ul>` : "";
}

function alt(head, rows) {
  return `<details class="alt"><summary>${t("chart.values")}</summary><div class="scroll"><table>`
    + `<thead><tr>${head.map(h => `<th scope="col">${h}</th>`).join("")}</tr></thead>`
    + `<tbody>${rows.map(r => `<tr>${r.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
}

function figure(c, body, keys, table) {
  return `<figure class="figure"><figcaption>${esc(c.title)}</figcaption>${body}${legend(keys)}${table}</figure>`;
}

function line(c) {
  const h = 300;
  const ys = known([...c.y, ...(c.compare ?? []), ...(c.means ?? []).map(m => m[2]), ...(c.band ?? []).flatMap(b => [b[1], b[2]]), ...(c.trend ?? []).map(p => p[1])]);
  const { sx, sy, axes } = frame(c.x, ys, h, c.unit);
  const dots = c.x.length <= 60;
  let body = axes;
  if (c.band) {
    const top = c.band.map(([x, , hi]) => `${sx(x).toFixed(1)},${sy(hi).toFixed(1)}`);
    const bottom = c.band.map(([x, lo]) => `${sx(x).toFixed(1)},${sy(lo).toFixed(1)}`).reverse();
    body += `<polygon class="band" points="${[...top, ...bottom].join(" ")}"/>`;
  }
  if (c.mark_year != null) {
    body += `<line class="mark" x1="${sx(c.mark_year)}" x2="${sx(c.mark_year)}" y1="${PAD.t}" y2="${h - PAD.b}"/>`
      + `<text class="tick" x="${sx(c.mark_year) + 4}" y="${PAD.t + 10}">${esc(c.mark_year)}</text>`;
  }
  if (c.compare) {
    body += `<path class="series compare" d="${path(c.x, c.compare, sx, sy)}"/>`;
    if (dots) body += c.x.map((x, i) => c.compare[i] == null ? "" : `<circle class="dot compare" cx="${sx(x)}" cy="${sy(c.compare[i])}" r="3"/>`).join("");
  }
  body += `<path class="series${dots ? " faint" : ""}" d="${path(c.x, c.y, sx, sy)}"/>`;
  if (dots) {
    body += c.x.map((x, i) => c.y[i] == null ? "" : `<circle class="dot" cx="${sx(x)}" cy="${sy(c.y[i])}" r="3.5"><title>${esc(yearMonth(x))}: ${num(c.y[i])} ${esc(c.unit)}</title></circle>`).join("");
  }
  if (c.means) body += c.means.map(([a, b, m]) => `<line class="mean" x1="${sx(a)}" y1="${sy(m)}" x2="${sx(b)}" y2="${sy(m)}"><title>${a}–${b}: ${num(m)} ${esc(c.unit)}</title></line>`).join("");
  if (c.trend) {
    const [[a, b], [p, q]] = c.trend;
    body += `<line class="trend" x1="${sx(a)}" y1="${sy(b)}" x2="${sx(p)}" y2="${sy(q)}"/>`;
  }
  const keys = [c.compare ? ["k-main", t("chart.recent")] : dots ? ["k-main", t("chart.each_year")] : ["k-line", t("chart.each_month")]];
  if (c.compare) keys.push(["k-compare", t("chart.compare")]);
  if (c.trend) keys.push(["k-trend", t("chart.trend")]);
  if (c.band) keys.push(["k-band", t("chart.band")]);
  if (c.means) keys.push(["k-mean", t("chart.means")]);
  if (c.mark_year != null) keys.push(["k-mark", t("chart.mark")]);
  const head = [t("chart.x"), esc(c.unit), ...(c.compare ? [t("chart.compare")] : [])];
  const rows = c.x.map((x, i) => [yearMonth(x), num(c.y[i]), ...(c.compare ? [num(c.compare[i])] : [])]);
  return figure(c, svg(c, h, body), keys, alt(head, rows));
}

function bars(c) {
  const row = 26, h = PAD.t + c.labels.length * row + 12, left = 168;
  const vs = c.values, lo = Math.min(0, ...vs), hi = Math.max(0, ...vs);
  const sx = scale(lo, hi, left, W - PAD.r - 56);
  const body = c.labels.map((label, i) => {
    const y = PAD.t + i * row, x0 = sx(Math.min(0, vs[i])), x1 = sx(Math.max(0, vs[i]));
    return `<text class="tick label" x="${left - 8}" y="${y + 16}" text-anchor="end">${esc(label)}</text>`
      + `<rect class="bar${c.highlight[i] ? " hl" : ""}" x="${x0}" y="${y + 4}" width="${Math.max(1, x1 - x0)}" height="${row - 8}"/>`
      + `<text class="tick" x="${x1 + 6}" y="${y + 16}">${num(vs[i])}</text>`;
  }).join("");
  const u = `<text class="unit" x="${left}" y="${PAD.t - 18}">${esc(c.unit)}</text><line class="axis" x1="${sx(0)}" x2="${sx(0)}" y1="${PAD.t}" y2="${h - 8}"/>`;
  return figure(c, svg(c, h, u + body), [], alt([t("chart.label"), esc(c.unit)], c.labels.map((l, i) => [l, num(vs[i])])));
}

function scatter(c) {
  const h = 320, xs = c.points.map(p => p[0]), ys = c.points.map(p => p[1]);
  const { sx, sy, axes } = frame(xs, ys, h, c.y_label);
  const body = axes + c.points.map(([x, y, label]) => `<circle class="dot" cx="${sx(x)}" cy="${sy(y)}" r="4"><title>${esc(label)}: ${num(x)}, ${num(y)}</title></circle>`).join("")
    + `<text class="unit" x="${W - PAD.r}" y="${h - 4}" text-anchor="end">${esc(c.x_label)}</text>`;
  return figure(c, svg(c, h, body), [], alt([t("chart.label"), esc(c.x_label), esc(c.y_label)], c.points.map(([x, y, l]) => [l, num(x), num(y)])));
}

function cells(c) {
  const [dlat, dlon] = c.cell_size;
  const lats = c.cells.map(r => r[0]), lons = c.cells.map(r => r[1]);
  const la0 = Math.min(...lats) - dlat / 2, la1 = Math.max(...lats) + dlat / 2, lo0 = Math.min(...lons) - dlon / 2, lo1 = Math.max(...lons) + dlon / 2;
  const side = Math.min((W - 32) / (lo1 - lo0), 360 / (la1 - la0));
  const w = (lo1 - lo0) * side, h = (la1 - la0) * side + 16;
  const max = Math.max(...c.cells.map(r => Math.abs(r[2]))) || 1;
  const body = c.cells.map(([lat, lon, v, clear]) => {
    const s = Math.round(Math.abs(v) / max * 100);
    const tone = (v >= 0) === c.warm_up ? "warm" : "cool";
    return `<rect class="cell ${tone}${clear ? " clear" : ""}" style="--s:${s}%" x="${(lon - dlon / 2 - lo0) * side}" y="${(la1 - lat - dlat / 2) * side}" width="${dlon * side}" height="${dlat * side}"><title>${num(lat)}, ${num(lon)}: ${num(v)} ${esc(c.unit)}</title></rect>`;
  }).join("");
  const keys = [["k-warm", t("chart.cell_up")], ["k-cool", t("chart.cell_down")], ["k-clear", t("chart.cell_clear")]];
  const rows = c.cells.map(([lat, lon, v, clear]) => [num(lat), num(lon), num(v), clear ? t("chart.yes") : t("chart.no")]);
  return figure(c, `<svg class="chart cells" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(c.title)}">${body}</svg>`,
    keys, alt([t("chart.lat"), t("chart.lon"), esc(c.unit), t("chart.clear")], rows));
}

function intervals(c) {
  const row = 28, left = Math.min(W / 2, 24 + 11 * Math.max(...c.rows.map(r => r[0].length))), h = PAD.t + c.rows.length * row + 12;
  const a0 = Math.min(...c.rows.map(r => r[2])), b0 = Math.max(...c.rows.map(r => r[3]));
  const zero = a0 <= 0 === b0 >= 0 || Math.min(Math.abs(a0), Math.abs(b0)) < Math.max(Math.abs(a0), Math.abs(b0)) / 2;
  const lo = zero ? Math.min(0, a0) : a0, hi = zero ? Math.max(0, b0) : b0;
  const sx = scale(lo, hi, left, W - PAD.r - 8);
  const axis = zero ? `<line class="axis" x1="${sx(0)}" x2="${sx(0)}" y1="${PAD.t}" y2="${h - 8}"/>`
    : `<text class="tick" x="${left}" y="${h - 2}">${num(lo)}</text><text class="tick" x="${W - PAD.r - 8}" y="${h - 2}" text-anchor="end">${num(hi)}</text>`;
  const body = `<text class="unit" x="${left}" y="${PAD.t - 18}">${esc(c.unit)}</text>${axis}`
    + c.rows.map(([label, v, a, b, hl], i) => {
      const y = PAD.t + i * row + row / 2;
      return `<text class="tick label" x="${left - 8}" y="${y + 4}" text-anchor="end">${esc(label)}</text>`
        + `<line class="whisker${hl ? " hl" : ""}" x1="${sx(a)}" x2="${sx(b)}" y1="${y}" y2="${y}"/>`
        + `<circle class="dot${hl ? " hl" : ""}" cx="${sx(v)}" cy="${y}" r="4.5"><title>${esc(label)}: ${num(v)} (${num(a)} to ${num(b)})</title></circle>`;
    }).join("");
  const rows = c.rows.map(([l, v, a, b]) => [l, num(v), num(a), num(b)]);
  return figure(c, svg(c, h, body), [], alt([t("chart.label"), esc(c.unit), t("chart.low"), t("chart.high")], rows));
}

// Read by tests/test_web_sync.py: one key per line between `const CHARTS = {` and `};`.
const CHARTS = {
  line,
  bars,
  scatter,
  cells,
  intervals,
};
