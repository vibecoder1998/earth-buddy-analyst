"use strict";

const S = {
  lang: "en",
  region: null,
  clickedCountry: null,
  thread: [],
  editing: null,
  mapFor: null,
  linkFailed: false,
  pick: { text: "", busy: null, error: null, notice: null, seq: 0 },
  catalog: null,
  status: null,
  sources: null,
  audit: null,
};

const $thread = document.getElementById("thread");
const $side = document.getElementById("side");
const $picker = document.getElementById("picker");
const $mapWrap = document.getElementById("map-wrap");
const label = l => (l ? l[S.lang] ?? l.en ?? "" : "");
const byId = (list, id) => list.find(x => x.id === id);
const varName = id => label(byId(S.catalog.variables, id)?.label) || id;
const needsPoint = kind => Boolean(S.catalog.kinds[kind]?.fields.some(f => f.name === "point"));
const noPointData = id => Boolean(id) && !byId(S.catalog.variables, id)?.point_param;
const fieldsOf = e => S.catalog.kinds[e.read?.draft.fields.kind]?.fields.map(f => f.name) ?? [];
const entryOf = el => S.thread.find(e => e.id === +el.closest("[data-e]")?.dataset.e);
const editingEntry = () => S.thread.find(e => e.id === S.editing);

function regionName(r) {
  if (!r) return "";
  if (r.kind === "point") return r.name;
  if (r.kind === "place") return label(byId(S.catalog.places, r.id)?.name) || r.id;
  return label(S.catalog.countries[r.iso3]?.name) || r.iso3;
}

function regionChoices() {
  const c = S.catalog;
  return [
    ...c.places.map(p => [label(p.name), { kind: "place", id: p.id }]),
    ...Object.entries(c.countries).map(([iso3, k]) => [label(k.name), { kind: "country", iso3 }]),
  ];
}

function asPoint(r) {
  if (r.kind === "point") return r;
  const at = r.kind === "place" ? byId(S.catalog.places, r.id) : S.catalog.countries[r.iso3];
  return { kind: "point", lat: at.lat, lon: at.lon, name: regionName(r) };
}

const regionKinds = (kind, name) => S.catalog.kinds[kind]?.fields.find(f => f.name === name)?.regions ?? [];

function countryOf(p) {
  const tail = p.name.split(", ").pop().toLowerCase();
  const iso3 = Object.keys(S.catalog.countries).find(k => S.catalog.countries[k].name.en.toLowerCase() === tail);
  return iso3 ? { kind: "country", iso3 } : null;
}

function fitRegion(r, kinds, clickedCountry = null) {
  if (!r) return null;
  if (kinds.includes(r.kind)) return r;
  if (kinds.includes("point")) return asPoint(r);
  if (r.kind === "point" && kinds.includes("country")) return clickedCountry?.kind === "country" ? clickedCountry : countryOf(r);
  return null;
}

function needArea(e, r) {
  e.notice = { kind: "need_area", q: regionName(r) };
}

function withRegion(e) {
  const fields = e.read.draft.fields, name = ["region", "point"].find(f => e.read.missing.includes(f));
  if (!S.region || !name) return null;
  const r = fitRegion(S.region, regionKinds(fields.kind, name), S.clickedCountry);
  if (!r) needArea(e, S.region);
  else e.area = { r: S.region, clickedCountry: S.clickedCountry };
  return r && { ...fields, [name]: r };
}

function fillRegion(e, name, r, clickedCountry = null) {
  const fit = fitRegion(r, regionKinds(e.read.draft.fields.kind, name), clickedCountry);
  if (fit) {
    e.notice = null;
    e.area = { r, clickedCountry };
    return edit(e, name, fit);
  }
  needArea(e, r);
  render();
}

const fieldName = f => (`field.${f}` in EN ? t(`field.${f}`) : esc(f));

let nextId = 0;
function addEntry(text) {
  const e = {
    id: ++nextId, text, read: null, asked: null, question: null, revision: 0, ran: 0, shown: false,
    result: null, explanation: null, audience: "student", charts_open: false, more: false, tab: 0,
    busy: null, error: null, notice: null, seq: 0, explainSeq: 0, area: null,
  };
  S.thread.push(e);
  S.linkFailed = false;
  return e;
}

const live = h => h === S.pick || S.thread.includes(h);

async function call(h, busy, path, body) {
  if (!live(h)) return null;
  const n = ++h.seq;
  h.busy = busy;
  h.error = null;
  render();
  let out = null;
  try {
    const res = await fetch(path, body === undefined ? {} : {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw data;
    out = data;
  } catch (err) {
    if (n === h.seq) h.error = err?.kind ? err : { kind: "network" };
  }
  if (n !== h.seq || !live(h)) return null;
  h.busy = null;
  return out;
}

const b64 = s => btoa(String.fromCharCode(...new TextEncoder().encode(s))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64 = s => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), ch => ch.charCodeAt(0)));
const shareHash = e => `#q=${b64(JSON.stringify({ question: e.result.question, revision: e.ran }))}`;

function reveal(e) {
  render();
  document.getElementById(`entry-${e.id}`)?.scrollIntoView({ block: "start", behavior: "smooth" });
}

function focusAnswer(e) {
  document.getElementById(`ans-${e.id}`)?.focus();
}

async function ask(text) {
  text = text.trim();
  if (!text) return;
  const e = addEntry(text);
  reveal(e);
  const r = await call(e, "read", "/api/read", { text, lang: S.lang });
  if (!r) return render();
  setRead(e, r, r.ai_failed);
  e.asked = r.question;
  return proceed(e);
}

async function proceed(e) {
  const filled = e.question ? null : withRegion(e);
  if (filled) await reread(e, filled);
  if (e.question && !blocked(e)) return run(e);
  S.editing = e.id;
  render();
}

function blocked(e) {
  const fields = e.read?.draft.fields ?? {};
  return noPointData(fields.variable) && needsPoint(fields.kind);
}

function setRead(e, r, aiFailed) {
  e.read = { ...r, ai_failed: aiFailed };
  e.question = r.question;
  e.revision = r.draft.revision;
}

async function reread(e, fields) {
  const d = e.read?.draft;
  const draft = { fields, quote: d?.quote ?? "", leads: d?.leads ?? [], unmapped: d?.unmapped ?? [], revision: e.revision };
  const r = await call(e, "read", "/api/read", { draft, lang: S.lang });
  if (r) setRead(e, r, e.read?.ai_failed ?? false);
  render();
}

async function startWith(text, fields, revision = 0) {
  const e = addEntry(text);
  e.revision = revision;
  reveal(e);
  await reread(e, fields);
  if (e.read) return proceed(e);
}

function askAbout(variable, region) {
  const v = byId(S.catalog.variables, variable);
  const measure = label(v?.what) || varName(variable);
  const text = region ? t("topic.ask_at", { measure, place: regionName(region) }, String) : t("topic.ask", { measure }, String);
  return startWith(text, { kind: "trend", variable, ...(region ? { region } : {}) });
}

function switchArea(e, fields) {
  const had = e.read.draft.fields.region ?? e.read.draft.fields.point;
  if (!e.area && had) e.area = { r: had, clickedCountry: null };
  const target = ["region", "point"].find(f => regionKinds(fields.kind, f).length);
  if (e.notice?.kind === "need_area") e.notice = null;
  if (!e.area || !target) return;
  const fit = fitRegion(e.area.r, regionKinds(fields.kind, target), e.area.clickedCountry);
  if (fit) fields[target] = fit;
  else {
    needArea(e, e.area.r);
    delete fields[target];
  }
}

function edit(e, name, value) {
  const fields = { ...e.read.draft.fields };
  if (value == null) delete fields[name];
  else fields[name] = value;
  if (value == null && (name === "region" || name === "point")) e.area = null;
  if (name === "kind") switchArea(e, fields);
  if (e.shown) {
    e.revision += 1;
    e.shown = false;
  }
  return reread(e, fields);
}

async function run(e) {
  const r = await call(e, "run", "/api/run", { question: e.question, revision: e.revision, lang: S.lang });
  if (r) showResult(e, r);
  render();
  if (r) focusAnswer(e);
}

function showResult(e, r) {
  e.result = r;
  e.ran = e.revision;
  e.shown = true;
  e.tab = 0;
  e.notice = null;
  if (S.editing === e.id) S.editing = null;
  history.replaceState(null, "", shareHash(e));
  if (S.mapFor === e.id) mapShow(r);
  explain(e);
}

async function explain(e) {
  const n = ++e.explainSeq, r = e.result;
  e.explanation = null;
  const x = await fetch("/api/explain", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ result: r, audience: e.audience, lang: S.lang }),
  }).then(res => (res.ok ? res.json() : null), () => null);
  if (n !== e.explainSeq) return;
  e.explanation = x ?? false;
  render();
}

async function openLink(code) {
  let body;
  try {
    body = JSON.parse(unb64(code));
  } catch {
    return badLink();
  }
  S.thread = [];
  S.editing = null;
  const e = addEntry(null);
  const r = await call(e, "run", "/api/run", { ...body, lang: S.lang });
  if (!r) return badLink();
  e.revision = Number.isInteger(body.revision) ? body.revision : 0;
  showResult(e, r);
  render();
  focusAnswer(e);
}

function badLink() {
  S.thread = [];
  S.linkFailed = true;
  history.replaceState(null, "", location.pathname);
  render();
}

async function findRegion(h, text) {
  const q = text.trim();
  if (!q) return null;
  const hit = regionChoices().find(([name]) => name.toLowerCase() === q.toLowerCase());
  if (hit) return hit[1];
  const r = await call(h, "find", `/api/geocode?q=${encodeURIComponent(q)}`);
  h.error = null;
  if (r?.results?.length) return r.results[0];
  h.notice = { kind: "no_place", q };
  render();
  return undefined;
}

async function share(e) {
  const link = location.origin + location.pathname + shareHash(e);
  const copied = await navigator.clipboard.writeText(link).then(() => true, () => false);
  e.notice = { kind: "share", link, copied };
  render();
}

function route() {
  const h = location.hash;
  if (!h.startsWith("#q=")) return render();
  const e = S.thread.find(x => x.result && shareHash(x) === h);
  if (e) return focusAnswer(e);
  return openLink(h.slice(3));
}

function newAnalysis() {
  S.thread = [];
  S.editing = null;
  S.mapFor = null;
  S.linkFailed = false;
  mapShow(null);
  history.replaceState(null, "", location.pathname);
  setMenu(false);
  render();
  document.getElementById("ask-text").focus();
}

function errorBox(err) {
  if (!err) return "";
  const msg = err.kind === "request" ? `${t("error.request")} ${fieldName(err.field)}`
    : err.kind === "data_source" ? t("error.source", { url: err.url ?? "" })
    : err.kind === "link" ? t("error.link")
    : t("error.network");
  return `<p class="alert" role="alert">${msg}</p>`;
}

function busyLabel(h, kind, idle) {
  return h.busy === kind ? t(`busy.${kind}`) : idle;
}

function viewStart() {
  return `<section class="start">
    ${errorBox(S.linkFailed ? { kind: "link" } : null)}
    <h2 class="eyebrow">${t("ask.try")}</h2>
    <ul class="chips">${[1, 2, 3, 4, 5].map(n => `<li><button id="chip-${n}" class="chip" data-act="chip" data-n="${n}">${t(`demo.${n}`)}</button></li>`).join("")}</ul>
    <p><button id="by-hand" class="link" data-act="hand">${t("ask.by_hand")}</button></p>
    ${auditStrip()}
  </section>`;
}

function auditStrip() {
  const a = S.audit;
  if (!a) return "";
  return `<section class="audit" aria-labelledby="h-audit">
    <h2 id="h-audit" class="eyebrow">${t("audit.title")}</h2>
    <p class="hint">${t("audit.note", { date: a.frozen })}</p>
    <ul class="audit-list">${a.claims.map((c, i) => `<li>
      <button id="audit-${i}" class="audit-item lvl-${esc(c.verdict.level)}" data-act="audit" data-i="${i}">
        <span class="audit-quote">“${esc(label(c.quote))}”</span>
        <span class="badge"><span class="dot" aria-hidden="true"></span>${esc(c.verdict_word)}</span>
        ${c.known_before ? `<span class="small">${t("audit.known_before")}</span>` : ""}
      </button>
    </li>`).join("")}</ul>
  </section>`;
}

async function loadAudit() {
  const res = await fetch(`/api/audit?lang=${S.lang}`).catch(() => null);
  if (!res?.ok) return;
  S.audit = await res.json();
  if (!S.thread.length) render();
}

async function runAudit(c) {
  const e = addEntry(label(c.quote));
  e.read = { draft: { fields: c.question, quote: label(c.quote), via: "audit", leads: [], unmapped: [], revision: 0 },
    question: c.question, missing: [], ai_failed: false };
  e.question = e.asked = c.question;
  reveal(e);
  const r = await call(e, "run", "/api/run", { question: c.question, revision: 0, via: "audit", lang: S.lang });
  if (r) showResult(e, r);
  render();
  if (r) focusAnswer(e);
}

const opt = (value, text, selected) => `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${text}</option>`;
const select = (id, name, options, extra = "") => `<select id="${id}" data-field="${name}" ${extra}>${options}</select>`;

function variableOptions(blank, selected, pointOnly = false) {
  const c = S.catalog;
  const option = v => opt(v.id, esc(label(v.label)), selected).replace("<option", pointOnly && !v.point_param ? "<option disabled" : "<option");
  return opt("", blank, selected) + c.topics.map(tp =>
    `<optgroup label="${esc(label(tp.label))}">${c.variables.filter(v => v.topics[0] === tp.id).map(option).join("")}</optgroup>`).join("");
}

const regionEditor = {
  view: (v, f) => `<input id="f-${f.name}" data-field="${f.name}" list="eb-regions" autocomplete="off" value="${esc(regionName(v))}" placeholder="${t("card.place_hint")}">`,
  change: async (el, _v, e) => {
    const r = await findRegion(e, el.value);
    if (r) fillRegion(e, el.dataset.field, r);
    return r === null ? null : undefined;
  },
  text: regionName,
};

const variableEditor = {
  view: (v, f, fields) => select(`f-${f.name}`, f.name, variableOptions(t("card.choose"), v ?? "", needsPoint(fields.kind))),
  change: el => el.value || null,
  text: v => (v ? varName(v) : ""),
};

const testsEditor = {
  view: (tests = []) => `<ul class="tests">${tests.map((x, i) => `<li>
      <span class="test-name">${esc(varName(x.variable))}</span>
      <span class="seg" role="radiogroup" aria-label="${esc(varName(x.variable))}">${["up", "down", "any"].map(d => `<label><input type="radio" id="dir-${i}-${d}" name="dir-${i}" data-field="tests" data-i="${i}" value="${d}" ${x.direction === d ? "checked" : ""}><span>${t(`card.dir.${d}`)}</span></label>`).join("")}</span>
      <button id="rm-${i}" class="icon" data-act="rm" data-i="${i}" aria-label="${t("card.remove")} ${esc(varName(x.variable))}">×</button>
    </li>`).join("")}</ul>
    ${select("f-tests-add", "tests", variableOptions(t("card.add"), ""), 'data-i="add"')}`,
  change: (el, tests = []) => {
    if (el.dataset.i === "add") {
      return el.value && !tests.some(x => x.variable === el.value) ? [...tests, { variable: el.value, direction: "any" }] : undefined;
    }
    return tests.map((x, i) => (i === +el.dataset.i ? { ...x, direction: el.value } : x));
  },
  text: (tests = []) => tests.map(x => `${varName(x.variable)} ${t(`card.dir.${x.direction}`).toLowerCase()}`).join(" · "),
};

const yearsEditor = {
  view: (v, f) => `<span class="years">
      <input id="f-${f.name}-0" type="number" inputmode="numeric" data-field="${f.name}" data-i="0" value="${esc(v?.[0] ?? "")}" placeholder="${t("card.from")}" aria-label="${t("card.from")}">
      <span aria-hidden="true">–</span>
      <input id="f-${f.name}-1" type="number" inputmode="numeric" data-field="${f.name}" data-i="1" value="${esc(v?.[1] ?? "")}" placeholder="${t("card.to")}" aria-label="${t("card.to")}">
    </span>${v ? "" : `<span class="hint">${t("card.full_record")}</span>`}`,
  change: (el, v) => {
    const [a, b] = v ?? S.catalog.years;
    if (el.value === "") return null;
    const n = Number(el.value);
    return el.dataset.i === "0" ? [n, b] : [a, n];
  },
  text: v => (v ? `${v[0]}–${v[1]}` : ""),
};

const numberEditor = {
  view: (v, f) => `<input id="f-${f.name}" type="number" inputmode="numeric" data-field="${f.name}" value="${esc(v ?? "")}">`,
  change: el => (el.value === "" ? null : Number(el.value)),
  text: v => (v == null ? "" : String(v)),
};

const choiceEditor = opts => ({
  view: (v, f) => select(`f-${f.name}`, f.name, opts.map(o => opt(o, t(`card.opt.${o}`), v ?? opts[0])).join("")),
  change: el => el.value,
  text: v => (v ? t(`card.opt.${v}`) : ""),
});

const amongEditor = {
  view: (v, f) => select(`f-${f.name}`, f.name, S.catalog.groups.map(g => opt(g.id, esc(label(g.name)), v)).join("")),
  change: el => el.value || null,
  text: v => label(byId(S.catalog.groups, v)?.name),
};

// Read by tests/test_web_sync.py: one key per line between `const EDITORS = {` and `};`.
const EDITORS = {
  region: regionEditor,
  point: regionEditor,
  tests: testsEditor,
  variable: variableEditor,
  x: variableEditor,
  y: variableEditor,
  window: yearsEditor,
  baseline: yearsEditor,
  among: amongEditor,
  metric: choiceEditor(["change", "level"]),
  order: choiceEditor(["highest", "lowest"]),
  top_n: numberEditor,
  year: numberEditor,
};

function viewCard(e) {
  const r = e.read, fields = r.draft.fields, kind = fields.kind, meta = S.catalog.kinds[kind];
  const kinds = Object.keys(S.catalog.kinds);
  const unmappable = noPointData(fields.variable);
  const options = [...kinds, ...(meta ? [] : [kind])]
    .map(k => `<option value="${esc(k)}"${k === kind ? " selected" : ""}${unmappable && needsPoint(k) ? " disabled" : ""}>${t(`kind.${k}`)}${S.catalog.kinds[k] ? "" : ` (${t("card.not_built")})`}</option>`).join("");
  const controls = meta ? meta.fields.map(f => `<fieldset class="field">
      <legend>${fieldName(f.name)}${f.required ? "" : ` <span class="opt">${t("card.optional")}</span>`}</legend>
      ${EDITORS[f.name].view(fields[f.name], f, fields)}
    </fieldset>`).join("") : `<p class="note">${t("card.kind_later")}</p>`;
  const stop = blocked(e);
  const why = !meta ? t("card.kind_later") : r.missing.length ? `${t("card.missing")} ${r.missing.map(fieldName).join(", ")}`
    : stop ? t("card.no_point", { variable: varName(fields.variable) }) : "";
  const notice = ["no_place", "need_area"].includes(e.notice?.kind) ? `<p class="note" role="status">${t(`card.${e.notice.kind}`, { q: e.notice.q })}</p>` : "";
  return `<section class="card" aria-labelledby="h-card">
    <h3 id="h-card" tabindex="-1">${t("card.title")}</h3>
    <p class="hint">${t("card.lede")}</p>
    ${r.ai_failed ? `<p class="note">${t("card.ai_failed")}</p>` : ""}
    <fieldset class="field"><legend>${t("card.kind")}</legend>
      <select id="f-kind" data-field="kind">${options}</select>
    </fieldset>
    ${controls}
    ${notice}
    ${r.draft.leads.length ? `<p class="note">${t("card.leads")} ${r.draft.leads.map(esc).join(", ")}</p>` : ""}
    ${r.draft.unmapped.length ? `<p class="note">${t("card.unmapped")} ${r.draft.unmapped.map(esc).join(", ")}</p>` : ""}
    <div class="card-actions">
      <button id="run" class="primary" data-act="run" ${!e.question || e.busy || stop ? "disabled" : ""} ${why ? 'aria-describedby="run-why"' : ""}>${busyLabel(e, "run", t("card.run"))}</button>
      <button id="card-back" class="link" data-act="cancel">${t("card.back")}</button>
    </div>
    ${why ? `<p id="run-why" class="why">${why}</p>` : ""}
  </section>`;
}

function panelClaim(r) {
  const f = r.facts;
  return `<section class="panel">
    <h3>${t("claim.title")}</h3>
    <ul class="evidence">${r.detail.evidence.map(e => {
      const k = e.variable;
      return `<li class="ev out-${esc(e.final)}">
        <div class="ev-head"><strong>${esc(varName(k))}</strong><span class="claimed">${t(`claim.dir.${e.direction}`)}</span></div>
        <p class="outcome">${esc(f[`${k}_outcome`])}</p>
        ${f[`${k}_change_per_decade`] == null ? "" : `<dl class="facts">
          <div><dt>${t("claim.per_decade")}</dt><dd>${esc(f[`${k}_change_per_decade`])}</dd></div>
          <div><dt>${t("claim.range")}</dt><dd>${esc(f[`${k}_95pct_range`])}</dd></div>
          <div><dt>${t("claim.p")}</dt><dd>${esc(f[`${k}_p`])}</dd></div>
        </dl>`}
        ${e.break_year == null ? "" : `<p class="small">${t("claim.break", { year: e.break_year })}</p>`}
        ${e.outcome === e.final ? "" : `<p class="small">${t("claim.fdr")}</p>`}
      </li>`;
    }).join("")}</ul>
  </section>`;
}

function panelTrend(r) {
  const f = r.facts;
  const row = (name, value) => (value == null ? "" : `<div><dt>${name}</dt><dd>${esc(value)}</dd></div>`);
  return `<section class="panel">
    <h3>${t("trend.title")}</h3>
    <dl class="facts wide">
      ${row(t("trend.average"), f.average)}
      ${row(t("trend.total"), f.percent_change ? `${f.total_change} (${f.percent_change})` : f.total_change)}
      ${row(t("trend.swing"), f.typical_swing)}
      ${row(t("trend.size"), f.size_word)}
      ${row(t("trend.coin"), f.coin)}
      ${row(t("trend.test"), f.test)}
    </dl>
  </section>`;
}

function scanStatus(row) {
  if (row.constant) return t("scan.constant");
  if (row.survives) return t("scan.clear");
  return row.level === "clear" ? t("scan.fdr") : t(`level.${row.level}`);
}

function panelScan(r, e) {
  const f = r.facts, d = r.detail;
  return `<section class="panel">
    <h3>${t("scan.title")}</h3>
    <p class="hint">${t("scan.lede")}</p>
    <ul class="evidence">${d.rows.map(row => {
      const k = row.variable;
      return `<li class="ev ${row.survives ? "out-supported" : ""}">
        <div class="ev-head"><strong>${esc(varName(k))}</strong><span class="claimed">${scanStatus(row)}</span></div>
        ${row.constant ? "" : `<dl class="facts">
          <div><dt>${t("claim.per_decade")}</dt><dd>${esc(f[`${k}_change_per_decade`])}</dd></div>
          <div><dt>${t("claim.p")}</dt><dd>${esc(f[`${k}_p`])}</dd></div>
          <div><dt>${t("scan.q")}</dt><dd>${esc(f[`${k}_q`])}</dd></div>
        </dl>
        <button id="try-${e.id}-${esc(k)}" class="link" data-act="try" data-v="${esc(k)}" data-d="${esc(row.observed)}">${t("scan.try")}</button>`}
      </li>`;
    }).join("")}</ul>
    ${d.skipped.length ? `<h4>${t("scan.skipped")}</h4><ul class="notes">${d.skipped.map(x =>
      `<li>${esc(varName(x.variable))}: ${t(`scan.skip.${x.reason}`)}</li>`).join("")}</ul>` : ""}
  </section>`;
}

function panelWhere(r) {
  const c = r.detail.counts, f = r.facts;
  const row = (name, value) => `<div><dt>${name}</dt><dd>${esc(value)}</dd></div>`;
  return `<section class="panel">
    <h3>${t("where.title")}</h3>
    <dl class="facts wide">
      ${row(t("where.cells"), c.total)}
      ${row(t("where.rising"), c.rising)}
      ${row(t("where.falling"), c.falling)}
      ${row(t("where.clear"), c.clear)}
      ${row(t("where.chance"), f.by_chance)}
      ${row(t("where.strongest"), `${f.strongest_change}, ${f.bearing}`)}
      ${row(t("where.nearest"), f.nearest_change)}
      ${row(t("where.size"), f.cell_size)}
    </dl>
    <p class="small">${t("where.on_map")}</p>
  </section>`;
}

function rankStatus(row) {
  if (row.rank === 1) return t("rank.leader");
  return row.same_as_leader ? t("rank.same") : t("rank.behind");
}

function panelRank(r) {
  const d = r.detail;
  return `<section class="panel">
    <h3>${t("rank.title")}</h3>
    <p class="hint">${t("rank.lede")}</p>
    <ol class="evidence">${d.rows.map(row => `<li class="ev ${row.rank === 1 || row.same_as_leader ? "out-supported" : ""}">
        <div class="ev-head"><strong>${row.rank}. ${esc(row.name)}</strong><span class="claimed">${rankStatus(row)}</span></div>
        <p class="small">${esc(row.text)}</p>
        ${row.shares_grid_cell ? `<p class="small">${t("rank.cell")}</p>` : ""}
      </li>`).join("")}</ol>
    ${d.skipped.length ? `<h4>${t("rank.skipped")}</h4><ul class="notes">${d.skipped.map(x =>
      `<li>${esc(x.name)}: ${t(`rank.skip.${x.reason}`)}</li>`).join("")}</ul>` : ""}
  </section>`;
}

function panelBaseline(r) {
  const f = r.facts;
  const row = (name, value) => (value == null ? "" : `<div><dt>${name}</dt><dd>${esc(value)}</dd></div>`);
  return `<section class="panel">
    <h3>${t("baseline.title")}</h3>
    <dl class="facts wide">
      ${row(t("baseline.average", { period: f.baseline_period }), f.baseline_average)}
      ${row(t("baseline.average", { period: f.recent_period }), f.recent_average)}
      ${row(t("baseline.difference"), f.percent_difference ? `${f.difference} (${f.percent_difference})` : f.difference)}
      ${row(t("baseline.p"), f.p_value)}
      ${row(t("baseline.trend", { period: f.baseline_period }), f.baseline_change_per_decade)}
      ${row(t("baseline.trend", { period: f.recent_period }), f.recent_change_per_decade)}
    </dl>
    <p class="small">${esc(f.pace_test)}</p>
  </section>`;
}

function panelExtremes(r) {
  const f = r.facts, d = r.detail;
  const row = (name, value) => (value == null ? "" : `<div><dt>${name}</dt><dd>${esc(value)}</dd></div>`);
  const years = list => `<ol class="notes">${list.map(x => `<li${x.year === d.focus.year ? ' class="hl"' : ""}>${esc(x.year)}: ${esc(num(x.value))} ${esc(f.unit)}</li>`).join("")}</ol>`;
  return `<section class="panel">
    <h3>${t("extremes.title")}</h3>
    <div class="facts wide">
      <div><h4>${t("extremes.highest")}</h4>${years(d.highest)}</div>
      <div><h4>${t("extremes.lowest")}</h4>${years(d.lowest)}</div>
    </div>
    <dl class="facts wide">
      ${row(t("extremes.trend_value", { year: f.year }), f.trend_value)}
      ${row(t("extremes.deviation", { year: f.year }), f.deviation)}
      ${row(t("extremes.swing"), f.typical_swing)}
      ${row(t("extremes.cluster", { k: f.top_k, n: f.cluster_window }), `${f.low_count} (${f.low_chance})`)}
      ${row(t("extremes.months"), f.clear_months)}
      ${row(t("extremes.season"), f.season_centre)}
      ${row(t("extremes.shift"), f.season_shift && `${f.season_shift} (p ${f.season_p})`)}
    </dl>
  </section>`;
}

// Read by tests/test_web_sync.py: one key per line between `const PANELS = {` and `};`.
const PANELS = {
  claim: panelClaim,
  trend: panelTrend,
  scan: panelScan,
  where: panelWhere,
  rank: panelRank,
  baseline: panelBaseline,
  extremes: panelExtremes,
};

function chartsBlock(e) {
  const charts = e.result.charts;
  if (!charts.length) return "";
  const i = Math.min(e.tab, charts.length - 1), many = charts.length > 1;
  const tabs = many ? `<div class="tabs" role="tablist" aria-label="${t("result.charts")}">${charts.map((c, j) =>
    `<button role="tab" id="tab-${e.id}-${j}" aria-selected="${j === i}" aria-controls="tabpanel-${e.id}" tabindex="${j === i ? 0 : -1}" data-act="tab" data-i="${j}">${esc(c.title)}</button>`).join("")}</div>` : "";
  const chart = CHARTS[charts[i].type]?.(charts[i]) ?? "";
  return `<section class="panel">
    <h3>${t("result.charts")}</h3>
    ${tabs}
    <div id="tabpanel-${e.id}" ${many ? `role="tabpanel" aria-labelledby="tab-${e.id}-${i}"` : ""}>${chart}</div>
  </section>`;
}

function sourceItem(s, full) {
  const link = s.doi
    ? `<a href="https://doi.org/${esc(encodeURI(s.doi))}" rel="noopener" target="_blank">doi:${esc(s.doi)}</a>`
    : `<a href="${esc(s.url)}" rel="noopener" target="_blank">${t("src.landing")}</a>`;
  const meta = [
    link,
    s.via ? t("src.via", { via: s.via }) : "",
    s.accessed ? t("src.accessed", { date: s.accessed }) : "",
    s.cached ? t("src.cached") : "",
    full ? esc([s.agency, s.center, s.version].filter(Boolean).join(" · ")) : "",
  ].filter(Boolean);
  return `<li><p class="src-name">${esc(s.name)}</p><p class="cite">${esc(s.citation)}</p><p class="src-meta">${meta.join('<span aria-hidden="true"> · </span>')}</p></li>`;
}

const bold = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

function explanationBlock(e) {
  const x = e.explanation, notes = e.result.notes;
  const data = notes.length ? `<div class="about-data"><span class="eyebrow">${t("explain.data")}</span>${notes.map(n => `<p>${esc(n)}</p>`).join("")}</div>` : "";
  if (x === false) return data;
  if (!x) return `<p class="short busy" role="status">${t("explain.busy")}</p>${data}`;
  return `<div class="explain" aria-live="polite">
    <p class="short">${bold(x.short)}</p>
    ${data}
    <details id="more-${e.id}" data-more${e.more ? " open" : ""}><summary>${t("explain.more")}</summary><p>${bold(x.more)}</p></details>
    <p class="small">${t("explain.template")}</p>
  </div>`;
}

function builtText(q) {
  return S.catalog.kinds[q.kind].fields.map(f => EDITORS[f.name].text(q[f.name])).filter(Boolean).join(" · ");
}

function askedLine(e) {
  const q = e.result.question;
  if (e.text && e.ran === 0 && JSON.stringify(e.asked) === JSON.stringify(q)) return "";
  return `<p class="asked">${t("result.checked")} ${esc(builtText(q))}</p>`;
}

function viewCharts(e) {
  const r = e.result;
  return `<div id="charts-${e.id}" class="charts">
    <ul class="tiles">${r.tiles.map(x => `<li class="tile">
      <span class="tile-label">${esc(x.label)}</span>
      <span class="tile-value">${esc(x.value)}</span>
      ${x.note ? `<span class="tile-note">${esc(x.note)}</span>` : ""}
    </li>`).join("")}</ul>
    ${chartsBlock(e)}
    ${S.mapFor === e.id ? `<div class="map-slot" data-map-slot></div>` : ""}
    ${PANELS[r.kind]?.(r, e) ?? ""}
    <details class="panel method"><summary>${t("result.method")}</summary>
      <ol class="steps">${r.method.map(s => `<li><strong>${esc(s.title)}</strong><p>${esc(s.did)}</p><p class="why-step">${esc(s.why)}</p></li>`).join("")}</ol>
    </details>
    <section class="panel">
      <h3>${t("result.sources")}</h3>
      <ul class="sources">${r.sources.map(s => sourceItem(s, false)).join("")}</ul>
    </section>
  </div>`;
}

function viewResult(e) {
  const r = e.result;
  const n = e.notice?.kind === "share" ? `<div class="share" role="status">
      <span>${e.notice.copied ? t("result.copied") : t("result.copy_this")}</span>
      <input id="share-link-${e.id}" readonly value="${esc(e.notice.link)}" aria-label="${t("result.share")}">
    </div>` : "";
  return `<div class="verdict lvl-${esc(r.verdict.level)}">
      <p class="badge"><span class="dot" aria-hidden="true"></span>${t(`level.${r.verdict.level}`)}</p>
      <h2 id="ans-${e.id}" class="headline" tabindex="-1">${r.headline.map(s => (s.hl ? `<strong>${esc(s.t)}</strong>` : esc(s.t))).join("")}</h2>
      ${askedLine(e)}
    </div>
    ${explanationBlock(e)}
    <div class="actions">
      <button id="charts-btn-${e.id}" class="soft" data-act="charts" aria-expanded="${e.charts_open}" aria-controls="charts-${e.id}">${e.charts_open ? t("result.hide_charts") : t("result.show_charts")}</button>
      <button id="edit-${e.id}" class="soft" data-act="edit">${t("result.edit")}</button>
      <button id="share-${e.id}" class="soft" data-act="share">${t("result.share")}</button>
    </div>
    ${n}
    ${e.charts_open ? viewCharts(e) : ""}`;
}

function viewEntry(e) {
  const text = e.text ?? (e.result ? builtText(e.result.question) : "");
  const body = S.editing === e.id && e.read ? viewCard(e)
    : e.result ? viewResult(e)
    : e.busy ? `<p class="status" role="status">${t(`busy.${e.busy}`)}</p>`
    : e.read ? `<p class="note">${t("entry.unfinished")}</p><p><button id="edit-${e.id}" class="soft" data-act="edit">${t("entry.finish")}</button></p>`
    : "";
  return `<article id="entry-${e.id}" class="entry" data-e="${e.id}">
    ${text ? `<p class="bubble">${esc(text)}</p>` : ""}
    <section class="answer">
      <p class="who">${t("app.name")}</p>
      ${e.busy && (e.result || S.editing === e.id) ? `<p class="status" role="status">${t(`busy.${e.busy}`)}</p>` : ""}
      ${errorBox(e.error)}
      ${body}
    </section>
  </article>`;
}

function viewThread() {
  return `<section class="intro">
      <h1>${t("ask.title")}</h1>
      <p class="lede">${t("ask.lede")}</p>
    </section>
    ${S.thread.length ? S.thread.map(viewEntry).join("") : viewStart()}`;
}

function viewPicker() {
  const p = S.pick;
  const notice = p.notice?.kind === "no_place" ? `<p class="note" role="status">${t("card.no_place", { q: p.notice.q })}</p>` : "";
  return `<div class="picker-head">
      <h2 id="h-picker">${t("pick.title")}</h2>
      <button id="pick-close" class="icon" data-act="pick-close" aria-label="${t("pick.close")}">×</button>
    </div>
    <p class="hint">${t("pick.lede")}</p>
    <label for="pick-text">${t("pick.search")}</label>
    <div class="pick-row">
      <input id="pick-text" list="eb-regions" autocomplete="off" value="${esc(p.text)}" placeholder="${t("card.place_hint")}">
      <button id="pick-find" class="primary" data-act="pick-find">${busyLabel(p, "find", t("pick.find"))}</button>
    </div>
    ${notice}
    ${errorBox(p.error)}
    <div class="map-slot" data-map-slot></div>
    <p class="small">${t("pick.click")}</p>
    ${S.region ? `<p>${t("pick.current", { place: regionName(S.region) })} <button id="pick-clear" class="link" data-act="pick-clear">${t("pick.clear")}</button></p>` : ""}`;
}

function placeMap() {
  const slot = ($picker.open ? $picker : $thread).querySelector("[data-map-slot]");
  (slot ?? document.getElementById("map-park")).append($mapWrap);
  M.map?.resize();
}

function render() {
  const focused = document.activeElement?.id;
  document.getElementById("map-park").append($mapWrap);
  $thread.innerHTML = S.catalog ? viewThread() : `<p>${t("busy.load")}</p>`;
  if ($picker.open) $picker.innerHTML = viewPicker();
  placeMap();
  if (focused) document.getElementById(focused)?.focus({ preventScroll: true });
}

const PIN = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 21s-7-6.1-7-11.5a7 7 0 1 1 14 0C19 14.9 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.4"/></svg>`;
const GLOBE = `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="12" cy="12" r="9.2"/><path d="M2.8 12h18.4M12 2.8c2.6 2.5 3.9 5.6 3.9 9.2s-1.3 6.7-3.9 9.2c-2.6-2.5-3.9-5.6-3.9-9.2S9.4 5.3 12 2.8z"/></svg>`;

function renderTop() {
  document.getElementById("top").innerHTML = `<button id="menu-btn" class="menu-btn" data-act="menu" aria-controls="side" aria-expanded="${$side.classList.contains("open")}">${t("nav.menu")}</button>
    <button id="region-btn" class="region" data-act="pick" aria-haspopup="dialog">${PIN}<span>${S.region ? esc(regionName(S.region)) : t("pick.title")}</span></button>`;
}

function renderSide() {
  const c = S.catalog;
  const topics = c.topics.map(tp => {
    const vars = c.variables.filter(v => v.topics[0] === tp.id);
    return vars.length ? `<details class="topic"><summary><span>${esc(label(tp.label))}</span><span class="count">${vars.length}</span></summary>
      <ul>${vars.map(v => `<li><button id="var-${esc(v.id)}" class="var" data-act="topic" data-v="${esc(v.id)}"><strong>${esc(label(v.label))}</strong><span>${esc(label(v.what))}</span></button></li>`).join("")}</ul>
    </details>` : "";
  }).join("");
  $side.innerHTML = `<div class="side-head">
      <a class="brand" href="/" data-act="new">${GLOBE}<span>${t("app.name")}</span></a>
      <button id="menu-close" class="icon menu-close" data-act="menu" aria-label="${t("nav.close")}">×</button>
    </div>
    <button id="new" class="new" data-act="new">+ ${t("nav.new")}</button>
    <details class="group" open><summary>${t("side.topics")}</summary>
      <p class="small">${t("side.topics_note")}</p>
      ${topics}
    </details>
    <details id="sources-box" class="group"><summary>${t("side.sources")}</summary>
      <p class="small">${t("about.rule")}</p>
      ${S.sources ? `<ul class="sources src-cards">${S.sources.map(s => sourceItem(s, true)).join("")}</ul>` : ""}
      <p class="small">${t("about.places")}</p>
      <p class="small">${t("about.ai")}</p>
    </details>`;
}

function renderComposer() {
  document.getElementById("composer").innerHTML = `<div class="composer-row">
      <label class="sr-only" for="ask-text">${t("ask.label")}</label>
      <textarea id="ask-text" maxlength="600" rows="1" placeholder="${t("ask.placeholder")}"></textarea>
      <button id="ask-go" class="send" type="submit" aria-label="${t("ask.go")}"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>
    </div>
    <p class="foot">${t("foot.ai")} <button id="about-link" type="button" class="link" data-act="sources">${t("nav.about")}</button></p>`;
}

function setMenu(open) {
  $side.classList.toggle("open", open);
  document.body.classList.toggle("menu-open", open);
  document.getElementById("menu-btn")?.setAttribute("aria-expanded", String(open));
}

function openPicker() {
  S.pick.notice = null;
  S.pick.error = null;
  $picker.showModal();
  render();
  mapShow(S.region ? { charts: [], question: { region: S.region } } : null);
}

function setRegion(r, clickedCountry = null) {
  S.region = r;
  S.clickedCountry = clickedCountry?.kind === "country" ? clickedCountry : null;
  S.pick.text = "";
  try {
    if (r) localStorage.setItem("eb-region", JSON.stringify({ region: r, clickedCountry: S.clickedCountry }));
    else localStorage.removeItem("eb-region");
  } catch {}
  renderTop();
  $picker.close();
}

function knownRegion(r) {
  if (r?.kind === "point") return Number.isFinite(r.lat) && Number.isFinite(r.lon) && typeof r.name === "string";
  if (r?.kind === "place") return Boolean(byId(S.catalog.places, r.id));
  return r?.kind === "country" && Boolean(S.catalog.countries[r.iso3]);
}

function loadRegion() {
  try {
    const saved = JSON.parse(localStorage.getItem("eb-region"));
    if (!knownRegion(saved?.region)) return;
    S.region = saved.region;
    S.clickedCountry = knownRegion(saved.clickedCountry) ? saved.clickedCountry : null;
  } catch {}
}

function mapPicked(point, area) {
  if ($picker.open) return setRegion(point, area);
  const e = editingEntry(), field = e && ["point", "region"].find(f => fieldsOf(e).includes(f));
  if (field) return fillRegion(e, field, point, area);
  return askAbout(M.variable, area);
}

const ACTIONS = {
  chip: el => ask(t(`demo.${el.dataset.n}`)),
  hand: () => {
    const e = addEntry(null);
    S.editing = e.id;
    return reread(e, { kind: Object.keys(S.catalog.kinds)[0] });
  },
  run: (_, e) => run(e),
  cancel: () => {
    S.editing = null;
    render();
  },
  edit: (_, e) => {
    S.editing = e.id;
    e.notice = null;
    if (!e.result) return render();
    return reread(e, { ...e.result.question });
  },
  share: (_, e) => share(e),
  charts: (_, e) => {
    e.charts_open = !e.charts_open;
    if (e.charts_open) {
      S.mapFor = e.id;
      mapShow(e.result);
    }
    render();
  },
  new: newAnalysis,
  audit: el => runAudit(S.audit.claims[+el.dataset.i]),
  try: (el, e) => startWith(null, { kind: "claim", region: e.result.question.region, tests: [{ variable: el.dataset.v, direction: el.dataset.d }] }, 1),
  rm: (el, e) => edit(e, "tests", e.read.draft.fields.tests.filter((_, i) => i !== +el.dataset.i)),
  tab: (el, e) => {
    e.tab = +el.dataset.i;
    render();
  },
  topic: el => {
    setMenu(false);
    return askAbout(el.dataset.v, S.region);
  },
  menu: () => setMenu(!$side.classList.contains("open")),
  sources: () => {
    setMenu(true);
    const box = document.getElementById("sources-box");
    box.open = true;
    box.querySelector("summary").focus();
  },
  pick: openPicker,
  "pick-close": () => $picker.close(),
  "pick-clear": () => setRegion(null),
  "pick-find": async () => {
    const r = await findRegion(S.pick, S.pick.text);
    if (r) setRegion(r);
  },
};

document.body.addEventListener("click", e => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  e.preventDefault();
  ACTIONS[el.dataset.act]?.(el, entryOf(el));
});

document.body.addEventListener("change", async ev => {
  const el = ev.target;
  const e = entryOf(el);
  if (!e) return;
  const name = el.dataset.field;
  if (!name) return;
  if (name === "kind") return edit(e, "kind", el.value);
  const value = await EDITORS[name].change(el, e.read.draft.fields[name], e);
  if (value !== undefined) edit(e, name, value);
});

document.body.addEventListener("toggle", ev => {
  if (ev.target.hasAttribute("data-more")) entryOf(ev.target).more = ev.target.open;
}, true);

document.body.addEventListener("input", ev => {
  if (ev.target.id === "pick-text") S.pick.text = ev.target.value;
});

document.body.addEventListener("keydown", ev => {
  const el = ev.target;
  if (ev.key === "Escape" && $side.classList.contains("open")) {
    setMenu(false);
    document.getElementById("menu-btn").focus();
  }
  if (el.id === "ask-text" && ev.key === "Enter" && !ev.shiftKey) {
    ev.preventDefault();
    document.getElementById("composer").requestSubmit();
  }
  if (el.id === "pick-text" && ev.key === "Enter") {
    ev.preventDefault();
    ACTIONS["pick-find"]();
  }
  if (el.getAttribute("role") === "tab" && (ev.key === "ArrowRight" || ev.key === "ArrowLeft")) {
    const e = entryOf(el), n = e.result.charts.length;
    e.tab = (e.tab + (ev.key === "ArrowRight" ? 1 : n - 1)) % n;
    render();
    document.getElementById(`tab-${e.id}-${e.tab}`)?.focus();
  }
});

document.getElementById("composer").addEventListener("submit", ev => {
  ev.preventDefault();
  const box = document.getElementById("ask-text");
  const text = box.value;
  box.value = "";
  ask(text);
});

$picker.addEventListener("close", () => {
  render();
  mapShow(S.thread.find(e => e.id === S.mapFor)?.result ?? null);
});

async function boot() {
  document.documentElement.lang = S.lang;
  renderComposer();
  render();
  try {
    [S.catalog, S.status, S.sources] = await Promise.all(["/api/catalog", "/api/status", "/api/sources"].map(p => fetch(p).then(r => r.json())));
  } catch {
    $thread.innerHTML = `<p class="alert" role="alert">${t("error.network")}</p>`;
    return;
  }
  document.body.insertAdjacentHTML("beforeend", `<datalist id="eb-regions">${regionChoices().map(([n]) => `<option value="${esc(n)}"></option>`).join("")}</datalist>`);
  loadRegion();
  renderTop();
  renderSide();
  mapInit();
  window.addEventListener("hashchange", route);
  route();
  loadAudit();
}

boot();
