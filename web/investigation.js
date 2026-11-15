"use strict";

// The investigation layout (docs/19-investigation.md). Each component returns an HTML string from one Result.
// app.js owns state and actions. This file reads S, t, esc and the tables app.js and charts.js define.

const LEVELS = ["discover", "explore", "investigate"];
const MODES = {
  public: { audience: "student", level: 0 },
  science: { audience: "researcher", level: 2 },
};

const LEVEL_ICON = {
  clear: '<circle cx="8" cy="8" r="7" fill="currentColor"/><path d="M4.6 8.3l2.2 2.2 4.6-4.9" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  likely: '<circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 1.8a6.2 6.2 0 0 1 0 12.4z" fill="currentColor"/>',
  unclear: '<circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6"/>',
  too_short: '<circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-dasharray="2.6 2.6"/>',
};
const BASIS_ICON = { measured: "●", interpretation: "◐", hypothesis: "○", guidance: "➜" };

const levelIcon = level => `<svg viewBox="0 0 16 16" aria-hidden="true">${LEVEL_ICON[level] ?? LEVEL_ICON.unclear}</svg>`;
const badge = level => `<span class="badge lvl-${esc(level)}">${levelIcon(level)}${t(`level.${level}`)}</span>`;
const disclose = (e, key, title, body, start = false) => `<details class="stats ${key}" data-open="${key}"${e.open[key] ?? start ? " open" : ""}><summary>${title}</summary>${body}</details>`;
const tip = (e, id, help) => (help ? `<details class="tip" data-open="tip-${esc(id)}"${e.open[`tip-${id}`] ? " open" : ""}><summary aria-label="${t("inv.what")}" title="${t("inv.what")}">?</summary><p>${esc(help)}</p></details>` : "");

function statements(list) {
  return `<ul class="stmts">${list.map(s => `<li class="stmt b-${esc(s.basis)}">
      <span class="basis"><i aria-hidden="true">${BASIS_ICON[s.basis] ?? ""}</i>${t(`basis.${s.basis}`)}</span>
      <p>${esc(s.text)}</p>
    </li>`).join("")}</ul>`;
}

function InvestigationHeader(e) {
  const r = e.result, f = r.facts;
  const bits = [r.investigation.scope?.name, f.period ?? f.years].filter(Boolean).map(esc);
  return `<p class="inv-head">${badge(r.verdict.level)}${[...bits, t(`kind.${r.kind}`)].map(b => `<span>${b}</span>`).join("")}</p>`;
}

function FindingSummary(e) {
  return `<p class="sec-h"><b>1</b>${t("inv.sec.answer")}</p>
    <h2 id="ans-${e.id}" class="headline" tabindex="-1">${headline(e.result)}</h2>
    ${askedLine(e)}
    ${explanationBlock(e)}`;
}

const MetricCard = x => `<li class="tile">
    <span class="k">${esc(x.label)}</span><span class="v">${esc(x.value)}</span>${x.note ? `<span class="n">${esc(x.note)}</span>` : ""}
  </li>`;

// One wrapper per analytical task. Each returns the chart parts plus `why`: the reason this picture fits the question.
// How a yearly record is drawn at each depth: the amounts first, then the path, then the uncertainty.
const YEARLY = [
  ["anomaly", anomaly],
  ["story", (c, o) => CHARTS.line(c, { ...o, view: "story" })],
  ["range", (c, o) => CHARTS.line(c, { ...o, view: "range" })],
];

function TimeSeriesChart(c, o) {
  if (c.compare || c.x.length > 60) return { ...CHARTS.line(c, o), why: c.compare ? "seasonal" : "series" };
  const [why, draw] = YEARLY[c.band ? o.level : Math.min(o.level, 1)];
  return { ...draw(c, o), why };
}
const BeforeAfterComparison = (c, o) => ({ ...CHARTS.line(c, o), why: "before_after" });
const TrendComparisonChart = (c, o) => ({ ...CHARTS[c.type](c, o), why: "comparison" });
const MultiVariableChart = (c, o) => ({ ...CHARTS.scatter(c, o), why: "relation" });
const GeographicCells = (c, o) => ({ ...CHARTS.cells(c, o), why: "map" });

function visual(c) {
  if (c.type === "line") return c.means ? BeforeAfterComparison : TimeSeriesChart;
  return { scatter: MultiVariableChart, cells: GeographicCells }[c.type] ?? TrendComparisonChart;
}

function GeographicTrendMap(e, result) {
  const c = result.charts.find(x => x.type === "cells");
  const parts = GeographicCells(c);
  return `${result === e.result ? "" : `<p class="where-line">${headline(result)}</p>`}
    ${S.mapFor === e.id ? '<div class="map-slot" data-map-slot></div>' : parts.svg}
    ${legend(parts.keys)}
    <p class="small">${t("where.on_map")}</p>`;
}

function StatisticalSignificance(e, full) {
  const r = e.result, [status, ...rows] = r.investigation.validation;
  const brief = [rows.find(x => x.id === "method"), rows.find(x => x.id === "p_value" || x.id.endsWith("_p")), rows.find(x => x.id === "sample")];
  return `<div class="sig lvl-${esc(r.verdict.level)}">${levelIcon(r.verdict.level)}
    <div>
      <p class="k">${esc(status.label)}</p>
      <p class="sig-v">${esc(status.value)}</p>
      <p class="hint">${esc(status.help)}</p>
      ${full ? "" : `<p class="sig-meta">${brief.filter(Boolean).map(x => `<span><b>${esc(x.label)}</b> ${esc(x.value)}</span>`).join("")}</p>`}
    </div>
  </div>`;
}

function ConfidenceInterval(r) {
  const fit = r.detail.fit, f = r.facts;
  if (!fit || fit.constant) return "";
  const c = { type: "intervals", title: t("inv.ci"), unit: t("inv.ci.unit", { unit: f.unit }, String),
    rows: [[f.variable, fit.slope_per_decade, fit.lo_per_decade, fit.hi_per_decade, r.verdict.level === "clear"]] };
  return `<h4>${t("inv.ci")}</h4>${CHARTS.intervals(c).svg}<p class="why-pic">${t("inv.ci.say", { pct: f.ci_pct })}</p>`;
}

const ImpactCard = list => `<div class="impact">${statements(list)}</div>`;

function MethodologyPanel(e) {
  const steps = e.result.method.map(s => `<li><strong>${esc(s.title)}</strong><p>${esc(s.did)}</p><p class="why"><span>${t("result.why")}</span>${esc(s.why)}</p></li>`).join("");
  return disclose(e, "method", t("result.method"), `<ol class="steps">${steps}</ol>`, whole());
}

function DataSourcePanel(e) {
  const r = e.result, cited = Object.fromEntries(r.sources.map(s => [s.id, s]));
  const row = (name, value) => `<div><dt>${name}</dt><dd>${esc(value)}</dd></div>`;
  const provider = id => `${cited[id].short_name ?? cited[id].name} (${cited[id].center})`;
  const sets = r.investigation.datasets.map(d => `<li class="dset">
      <p class="src-name">${esc(d.label)} <code>${esc(d.parameter)}</code></p>
      <dl class="facts wide">
        ${row(t("data.kind"), d.kind)}
        ${row(t("data.resolution"), d.resolution)}
        ${row(t("data.coverage"), d.coverage)}
        ${row(t("data.processing"), d.processing)}
        ${row(t("data.providers"), d.sources.filter(id => cited[id]).map(provider).join(" · "))}
      </dl>
    </li>`).join("");
  return `${sets ? `<ul class="sources">${sets}</ul>` : ""}
    <h4>${t("result.sources")}</h4>
    <ul class="sources">${r.sources.map(sourceItem).join("")}</ul>
    <h4>${t("inv.reproduce")}</h4>
    <p class="hint">${t("inv.reproduce.say")}</p>
    <p class="entry-actions">
      <button id="json-${e.id}" class="link" data-act="download" data-what="json">${t("inv.json")}</button>
      <button id="share2-${e.id}" class="link" data-act="share">${t("result.share")}</button>
    </p>`;
}

function secProvenance(e, lvl) {
  const r = e.result;
  if (lvl >= 2) return DataSourcePanel(e);
  const sets = r.investigation.datasets.map(d => `<li><b>${esc(d.label)}</b> <code>${esc(d.parameter)}</code> · ${esc(d.kind)} · ${esc(d.coverage)}</li>`).join("");
  return `${sets ? `<ul class="notes">${sets}</ul>` : ""}
    <ul class="src-cards">${r.sources.map(sourceTitle).join("")}</ul>
    <p><button id="prov-${e.id}" class="link" data-act="level" data-i="2">${t("inv.full_provenance")}</button></p>`;
}

function FollowUpInvestigation(e) {
  const inv = e.result.investigation;
  const asks = inv.next.map((n, i) => `<li><button id="next-${e.id}-${i}" class="chip" data-act="next" data-i="${i}">${esc(n.label)}</button></li>`).join("");
  return `${asks ? `<ul class="chips next" aria-label="${t("inv.follow")}">${asks}</ul>` : ""}
    <p class="k">${t("inv.guidance")}</p>
    ${statements(inv.guidance)}
    <p class="hint">${t("inv.guidance.say")}</p>`;
}

function secEvidence(e, lvl, pic) {
  const r = e.result;
  if (!pic.html) return panelOf(r)?.(r, e) ?? "";
  const table = lvl < 2 || !pic.table ? "" : disclose(e, "table", t("inv.table"),
    `${pic.table}<p><button id="csv-${e.id}" class="link" data-act="download" data-what="csv">${t("inv.csv")}</button></p>`);
  return `${pic.html}${pic.why ? `<p class="why-pic">${t(`visual.${pic.why}`)}</p>` : ""}${table}`;
}

function secWhere(e, lvl) {
  const r = e.result, scope = r.investigation.scope;
  if (!scope) return "";
  const place = r.question.region ?? r.question.point;
  const can = lvl >= 1 && place && mappable(r) && !r.charts.some(c => c.type === "cells");
  if (can && e.map && !e.fallbacks.where) runFallback(e, "where");
  const src = e.fallbacks.where;
  const map = !can ? ""
    : !e.map ? `<p><button id="map-btn-${e.id}" class="chip small" data-act="map">${t("inv.map")}</button></p>`
    : src?.result ? GeographicTrendMap(e, src.result)
    : src?.error ? errorBox({ kind: "network" })
    : `<p class="status" role="status">${t("busy.where")}</p>`;
  return `<p class="scope">${esc(scope.text)}</p>${lvl >= 1 ? `<p class="hint">${esc(scope.limit)}</p>` : ""}${map}`;
}

function secHowMuch(e, lvl, pic) {
  const r = e.result, top = insightOf(r);
  const panel = lvl >= 1 && pic.html ? panelOf(r)?.(r, e) ?? "" : "";
  return `${top ? top(r) : ""}
    ${!top || lvl >= 2 ? `<ul class="tiles">${r.tiles.map(MetricCard).join("")}</ul>` : ""}
    ${panel ? disclose(e, "numbers", t("result.numbers"), panel, whole()) : ""}`;
}

function secValidation(e, lvl) {
  const r = e.result, inv = r.investigation;
  if (lvl < 2) return `${StatisticalSignificance(e, false)}<p><button id="stats-${e.id}" class="link" data-act="level" data-i="2">${t("inv.full_stats")}</button></p>`;
  const rows = inv.validation.slice(1).map(x => `<div><dt>${esc(x.label)}${tip(e, x.id, x.help)}</dt><dd>${esc(x.value)}</dd></div>`).join("");
  return `${StatisticalSignificance(e, true)}
    <dl class="vrows">${rows}</dl>
    ${ConfidenceInterval(r)}
    ${inv.limits.length ? `<h4>${t("inv.limits")}</h4><ul class="notes">${inv.limits.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${MethodologyPanel(e)}`;
}

// The investigation order, after the answer. Every level shows every section. A deeper level shows more inside each.
const SECTIONS = {
  evidence: secEvidence,
  where: secWhere,
  how_much: secHowMuch,
  why: (e, lvl) => statements(e.result.investigation.why.filter(s => lvl >= 1 || s.basis !== "hypothesis")),
  impact: e => ImpactCard(e.result.investigation.impact),
  validation: secValidation,
  provenance: secProvenance,
  next: FollowUpInvestigation,
};

function section(e, n, id, view, lvl, pic) {
  let body;
  try {
    body = view(e, lvl, pic);
  } catch (err) {
    console.error(`section ${id} failed`, err);
    body = `<p class="note">${t("inv.failed")}</p>`;
  }
  return body.trim() ? `<section class="inv-sec" aria-labelledby="sec-${e.id}-${id}">
    <h3 id="sec-${e.id}-${id}" class="sec-h"><b>${n}</b>${t(`inv.sec.${id}`)}</h3>
    ${body}
  </section>` : "";
}

function LevelSwitch(e) {
  return `<div class="levels">
    <div class="tabs" role="group" aria-label="${t("inv.levels")}">${LEVELS.map((k, i) =>
      `<button id="lvl-${e.id}-${i}" data-act="level" data-i="${i}" aria-pressed="${i === e.level}">${t(`inv.level.${k}`)}</button>`).join("")}</div>
    <p class="hint">${t(`inv.say.${LEVELS[e.level]}`)}</p>
  </div>`;
}

function investigationCard(e) {
  const all = whole(), lvl = all ? 2 : e.level;
  let pic = { html: "", table: "" };
  try {
    pic = all ? pictures(e) : picture(e);
  } catch (err) {
    console.error("picture failed", err);
  }
  const body = Object.entries(SECTIONS).map(([id, view], i) => section(e, i + 2, id, view, lvl, pic)).join("");
  const deeper = !all && lvl < 2 ? `<p class="inv-more">
      <button id="deeper-${e.id}" class="chip" data-act="level" data-i="${lvl + 1}">${t("inv.deeper", { level: t(`inv.level.${LEVELS[lvl + 1]}`) })}</button>
      <span class="hint">${t(`inv.adds.${LEVELS[lvl + 1]}`)}</span>
    </p>` : "";
  return `<section id="charts-${e.id}" class="card answer-card inv">${all ? "" : LevelSwitch(e)}${body}${deeper}</section>`;
}

function saveFile(name, type, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function downloadEvidence(e, what) {
  const r = e.result;
  if (what === "json") {
    const link = location.origin + location.pathname + shareHash(e);
    const evidence = { app: "Earth Buddy", generated: new Date().toISOString(), link, lang: S.lang, revision: e.ran, question: r.question, result: r };
    return saveFile(`earth-buddy-${r.kind}.json`, "application/json", JSON.stringify(evidence, null, 2));
  }
  const pic = picture(e);
  const plain = s => new DOMParser().parseFromString(String(s), "text/html").body.textContent;
  const cell = v => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  const lines = [pic.head, ...pic.rows].map(row => row.map(v => cell(plain(v))).join(","));
  saveFile(`earth-buddy-${r.kind}.csv`, "text/csv", `${lines.join("\n")}\n`);
}
