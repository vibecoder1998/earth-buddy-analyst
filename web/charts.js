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
  for (let v = a; v <= b + step / 2; v += step) ticks.push(+v.toFixed(10) || 0);
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

function frame(xs, ys, unit, months = false, ticks = xTicks) {
  const top = unit ? PAD.t + 12 : PAD.t;
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const yn = nice(Math.min(...ys), Math.max(...ys));
  const sx = scale(x0, x1, PAD.l, W - PAD.r), sy = scale(yn.lo, yn.hi, H - PAD.b, top);
  const grid = yn.ticks.map(v => `<line class="grid" x1="${PAD.l}" x2="${W - PAD.r}" y1="${sy(v)}" y2="${sy(v)}"/>`
    + `<text x="${PAD.l - 8}" y="${sy(v) + 4}" text-anchor="end">${num(v)}</text>`).join("");
  const xt = (months ? xs : ticks(x0, x1)).map(v => `<text x="${sx(v)}" y="${H - 8}" text-anchor="middle">${months ? esc(monthName(v)) : num(v)}</text>`).join("");
  const u = unit ? `<text x="4" y="11">${esc(unit)}</text>` : "";
  return { sx, sy, top, lo: yn.lo, hi: yn.hi, axes: grid + xt + u };
}

function points(xs, ys, sx, sy) {
  return xs.flatMap((x, i) => (ys[i] == null ? [] : [`${sx(x).toFixed(1)},${sy(ys[i]).toFixed(1)}`])).join(" ");
}

function svg(c, h, body, w = W) {
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(c.title)}">${body}</svg>`;
}

// The part of a segment whose y stays inside [lo, hi], in data units. The two ends must sit on opposite sides or inside.
function clipY([x1, y1], [x2, y2], lo, hi) {
  const at = y => x1 + ((y - y1) * (x2 - x1)) / (y2 - y1);
  const cut = (x, y) => (y < lo ? [at(lo), lo] : y > hi ? [at(hi), hi] : [x, y]);
  return [cut(x1, y1), cut(x2, y2)];
}

function endLabel(x, y, text, end, below, top) {
  const ly = Math.max(top + 12, Math.min(H - PAD.b - 6, y + (below ? 16 : -8)));
  return `<text class="lab" x="${x + (end ? -6 : 6)}" y="${ly}"${end ? ' text-anchor="end"' : ""}>${text}</text>`;
}

function markYear(c, sx, top) {
  if (c.mark_year == null) return "";
  const mx = sx(c.mark_year), edge = mx > W - PAD.r - 40;
  return `<line class="mark" x1="${mx}" x2="${mx}" y1="${top}" y2="${H - PAD.b}"/>`
    + `<text x="${mx + (edge ? -6 : 6)}" y="${top + 10}"${edge ? ' text-anchor="end"' : ""}>${esc(c.mark_year)}</text>`;
}

// Each span is inclusive, so it reaches half a step past both ends: a whole year, a whole month.
function spanRects(c, sx, top) {
  if (!c.spans?.length) return "";
  const xs = [...c.x].sort((a, b) => a - b);
  const half = Math.min(...xs.slice(1).map((x, i) => x - xs[i]).filter(d => d > 0), 1) / 2;
  return c.spans.map(([a, b]) => {
    const x0 = Math.max(PAD.l, sx(a - half)), x1 = Math.min(W - PAD.r, sx(b + half));
    return x1 > x0 ? `<rect class="span" x="${x0.toFixed(1)}" y="${top}" width="${(x1 - x0).toFixed(1)}" height="${H - PAD.b - top}"/>` : "";
  }).join("");
}

const spanKey = c => (c.spans?.length && c.span_label ? [["k-span", esc(c.span_label)]] : []);

// One bar per year, measured from the average of the years shown. opts.warm says whether a high year is the warm colour.
function anomaly(c, opts = {}) {
  const ys = known(c.y), m = ys.reduce((a, b) => a + b, 0) / ys.length;
  const { sx, sy, top, axes } = frame([c.x[0] - 0.5, c.x.at(-1) + 0.5], [...ys, m], "", false, (a, b) => xTicks(a, b).filter(Number.isInteger));
  const bw = ((W - PAD.l - PAD.r) / c.x.length) * 0.78;
  const bars = c.x.map((x, i) => {
    if (c.y[i] == null) return "";
    const y = sy(c.y[i]), up = c.y[i] >= m;
    return `<rect class="bar ${up === Boolean(opts.warm) ? "warm" : "cool"}" x="${(sx(x) - bw / 2).toFixed(1)}" y="${Math.min(y, sy(m)).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, Math.abs(y - sy(m))).toFixed(1)}" rx="2"><title>${esc(x)}: ${num(c.y[i])} ${esc(c.unit)}</title></rect>`;
  }).join("");
  const body = axes + spanRects(c, sx, top) + bars + markYear(c, sx, top) + `<line class="avg" x1="${PAD.l}" x2="${W - PAD.r}" y1="${sy(m)}" y2="${sy(m)}"/>`
    + `<text class="lab" x="${PAD.l + 6}" y="${top + 12}">↑ ${t("chart.above")}</text><text class="lab" x="${PAD.l + 6}" y="${H - PAD.b - 6}">↓ ${t("chart.below")}</text>`;
  const keys = [["k-avg", t("chart.average")], ...spanKey(c), ...(c.mark_year == null ? [] : [["k-mark", c.mark_label ? esc(c.mark_label) : t("chart.mark")]])];
  return { ...line(c), svg: svg(c, H, body), keys, each: t("chart.each_bar", { unit: c.unit }) };
}

// opts.view redraws a yearly record: "story" joins the years and labels the trend's two ends, "range" also draws
// the two edges of the trend's range as lines. Both fit the scale to the years, so a wide band cannot flatten them.
function line(c, opts = {}) {
  const dots = c.x.length <= 60 && !c.compare, view = dots ? opts.view : undefined;
  const ys = known([...c.y, ...(c.compare ?? []), ...(c.means ?? []).map(m => m[2]), ...(view ? [] : c.band ?? []).flatMap(b => [b[1], b[2]]), ...(c.trend ?? []).map(p => p[1])]);
  const { sx, sy, top, lo, hi, axes } = frame(c.x, ys, dots ? "" : c.unit, opts.months);
  let body = axes + spanRects(c, sx, top);
  if (view) body += `<polyline class="soft" points="${points(c.x, c.y, sx, sy)}"/>`;
  if (c.band && view === "range") {
    const first = c.band[0], last = c.band.at(-1);
    body += [[first[1], last[2], t("chart.high_end")], [first[2], last[1], t("chart.low_end")]].map(([y1, y2, label], i) => {
      const [[ax, ay], [bx, by]] = clipY([first[0], y1], [last[0], y2], lo, hi);
      return `<line class="maybe" x1="${sx(ax).toFixed(1)}" y1="${sy(ay).toFixed(1)}" x2="${sx(bx).toFixed(1)}" y2="${sy(by).toFixed(1)}"/>`
        + endLabel(sx(bx), sy(by), label, true, i === 1, top);
    }).join("");
  }
  if (c.band && !view) {
    const up = c.band.map(([x, , hi]) => `${sx(x).toFixed(1)},${sy(hi).toFixed(1)}`);
    const down = c.band.map(([x, lo]) => `${sx(x).toFixed(1)},${sy(lo).toFixed(1)}`).reverse();
    body += `<polygon class="band" points="${[...up, ...down].join(" ")}"/>`;
  }
  body += markYear(c, sx, top);
  if (c.compare) body += `<polyline class="series" points="${points(c.x, c.compare, sx, sy)}"/>`;
  if (dots) {
    body += c.x.map((x, i) => (c.y[i] == null ? "" : `<circle class="dot" cx="${sx(x).toFixed(1)}" cy="${sy(c.y[i]).toFixed(1)}" r="3.4"><title>${esc(yearMonth(x))}: ${num(c.y[i])} ${esc(c.unit)}</title></circle>`)).join("");
  } else {
    body += `<polyline class="series${c.compare ? " main" : " thin"}" points="${points(c.x, c.y, sx, sy)}"/>`;
  }
  if (c.means) body += c.means.map(([a, b, m]) => `<line class="mean" x1="${sx(a)}" y1="${sy(m)}" x2="${sx(b)}" y2="${sy(m)}"><title>${a}–${b}: ${num(m)} ${esc(c.unit)}</title></line>`).join("");
  if (c.trend) {
    const [[a, b], [p, q]] = c.trend;
    body += `<line class="trend" x1="${sx(a)}" y1="${sy(b)}" x2="${sx(p)}" y2="${sy(q)}"/>`;
    if (view === "story") body += endLabel(sx(a), sy(b), num(+b.toPrecision(3)), false, false, top) + endLabel(sx(p), sy(q), num(+q.toPrecision(3)), true, false, top);
    if (view === "range") body += endLabel(sx(a), sy(b), t("chart.trend"), false, false, top);
  }
  const [yName, compareName] = c.labels?.map(esc) ?? [];
  const keys = c.compare ? [["k-thin", compareName ?? t("chart.compare")], ["k-trend", yName ?? t("chart.recent")]]
    : [dots ? ["k-dot", yName ?? t("chart.each_year")] : ["k-thin", yName ?? t("chart.each_month")]];
  if (c.trend) keys.push(["k-trend", t("chart.trend")]);
  if (c.band && view !== "story") keys.push([view ? "k-maybe" : "k-band", opts.band ?? t("chart.band")]);
  keys.push(...spanKey(c));
  if (c.means) keys.push(["k-mean", t("chart.means")]);
  if (c.mark_year != null) keys.push(["k-mark", c.mark_label ? esc(c.mark_label) : t("chart.mark")]);
  return {
    svg: svg(c, H, body), keys, each: dots ? t("chart.each_dot", { unit: c.unit }) : "",
    head: [t("chart.x"), esc(c.unit), ...(c.compare ? [compareName ?? t("chart.compare")] : [])],
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
  const { sx, sy, axes } = frame(xs, ys, c.y_label, false, (a, b) => nice(a, b).ticks.filter(v => v >= a && v <= b));
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
  const max = Math.max(...c.cells.map(r => Math.abs(r[2]))) || 1, level = c.scale === "level";
  // A level is a count, and a few busy squares would wash out the rest on a straight scale, so it is shaded by the square root.
  const body = c.cells.map(([lat, lon, v, clear]) => {
    const s = Math.round((level ? Math.sqrt(Math.abs(v) / max) : Math.abs(v) / max) * 100);
    const tone = level || (v >= 0) === c.warm_up ? "warm" : "cool";
    return `<rect class="cell ${tone}${clear ? " clear" : ""}" style="--s:${s}%" x="${(lon - dlon / 2 - lo0) * side}" y="${(la1 - lat - dlat / 2) * side}" width="${dlon * side}" height="${dlat * side}"><title>${num(lat)}, ${num(lon)}: ${num(v)} ${esc(c.unit)}</title></rect>`;
  }).join("");
  return {
    svg: svg(c, h, body, w).replace('class="chart"', 'class="chart cells"'), each: "",
    keys: level ? [["k-warm", t("chart.cell_more", { unit: c.unit })]]
      : [["k-warm", t("chart.cell_up")], ["k-cool", t("chart.cell_down")], ["k-clear", t("chart.cell_clear")]],
    head: [t("chart.lat"), t("chart.lon"), esc(c.unit), ...(level ? [] : [t("chart.clear")])],
    rows: c.cells.map(([lat, lon, v, clear]) => [num(lat), num(lon), num(v), ...(level ? [] : [clear ? t("chart.yes") : t("chart.no")])]),
  };
}

function intervals(c) {
  const row = 28, left = Math.min(W / 2, 24 + 11 * Math.max(...c.rows.map(r => r[0].length))), h = PAD.t + 26 + c.rows.length * row + 12;
  const a0 = Math.min(...c.rows.map(r => r[2])), b0 = Math.max(...c.rows.map(r => r[3]));
  const zero = a0 <= 0 === b0 >= 0 || Math.min(Math.abs(a0), Math.abs(b0)) < Math.max(Math.abs(a0), Math.abs(b0)) / 2;
  const lo = zero ? Math.min(0, a0) : a0, hi = zero ? Math.max(0, b0) : b0;
  const sx = scale(lo, hi, left, W - PAD.r - 8);
  const axis = zero ? `<line class="axis" x1="${sx(0)}" x2="${sx(0)}" y1="${PAD.t + 26}" y2="${h - 8}"/>`
    : `<text x="${left}" y="${h - 2}">${num(lo)}</text><text x="${W - PAD.r - 8}" y="${h - 2}" text-anchor="end">${num(hi)}</text>`;
  const body = `<text x="${left}" y="${PAD.t + 8}">${esc(c.unit)}</text>${axis}`
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
