"use strict";

const S = {
  view: "ask",
  lang: "en",
  ai: false,
  audience: "student",
  text: "",
  read: null,
  question: null,
  revision: 0,
  shown: false,
  result: null,
  explanation: null,
  more: false,
  busy: null,
  error: null,
  notice: null,
  tab: 0,
  catalog: null,
  status: null,
  sources: null,
};

const $panel = document.getElementById("panel");
const label = l => (l ? l[S.lang] ?? l.en ?? "" : "");
const byId = (list, id) => list.find(x => x.id === id);
const varName = id => label(byId(S.catalog.variables, id)?.label) || id;
const aiAvailable = () => Boolean(S.status?.ai_available);

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

const fieldName = f => (`field.${f}` in EN ? t(`field.${f}`) : esc(f));

let seq = 0;
async function call(busy, path, body) {
  const n = ++seq;
  S.busy = busy;
  S.error = null;
  render();
  let out = null;
  try {
    const res = await fetch(path, body === undefined ? {} : {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw data;
    out = data;
  } catch (e) {
    if (n === seq) S.error = e?.kind ? e : { kind: "network" };
  }
  if (n !== seq) return null;
  S.busy = null;
  return out;
}

const b64 = s => btoa(String.fromCharCode(...new TextEncoder().encode(s))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64 = s => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), ch => ch.charCodeAt(0)));
const shareHash = r => `#q=${b64(JSON.stringify({ question: r.question, revision: S.revision }))}`;

async function ask() {
  const text = S.text.trim();
  if (!text) return;
  S.revision = 0;
  S.shown = false;
  S.notice = null;
  const r = await call("read", "/api/read", { text, lang: S.lang, ai: S.ai && aiAvailable() });
  if (r) setRead(r, r.ai_failed);
  render();
}

function setRead(r, aiFailed) {
  S.read = { ...r, ai_failed: aiFailed };
  S.question = r.question;
  S.revision = r.draft.revision;
  S.view = "card";
}

async function reread(fields) {
  const d = S.read?.draft;
  const draft = { fields, quote: d?.quote ?? "", leads: d?.leads ?? [], unmapped: d?.unmapped ?? [], revision: S.revision };
  const r = await call("read", "/api/read", { draft, lang: S.lang });
  if (r) setRead(r, S.read?.ai_failed ?? false);
  render();
}

function edit(name, value) {
  const fields = { ...S.read.draft.fields };
  if (value == null) delete fields[name];
  else fields[name] = value;
  if (S.shown) {
    S.revision += 1;
    S.shown = false;
  }
  return reread(fields);
}

async function run() {
  const r = await call("run", "/api/run", { question: S.question, revision: S.revision, lang: S.lang });
  if (r) showResult(r);
  render();
}

function showResult(r) {
  S.result = r;
  S.shown = true;
  S.tab = 0;
  S.notice = null;
  S.view = "result";
  history.replaceState(null, "", shareHash(r));
  explain();
}

let explainSeq = 0;
async function explain() {
  const n = ++explainSeq, r = S.result;
  const get = ai => fetch("/api/explain", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ result: r, audience: S.audience, lang: S.lang, ai }),
  }).then(res => (res.ok ? res.json() : null), () => null);
  const apply = e => {
    if (n !== explainSeq) return;
    S.explanation = e;
    render();
  };
  S.explanation = null;
  const template = get(false).then(e => apply(e ?? false));
  if (!(S.ai && aiAvailable())) return;
  const e = await get(true);
  await template;
  if (e?.via === "ai") apply(e);
}

async function openLink(code) {
  let body;
  try {
    body = JSON.parse(unb64(code));
  } catch {
    return badLink();
  }
  const r = await call("run", "/api/run", { ...body, lang: S.lang });
  if (!r) return badLink();
  S.read = null;
  S.revision = Number.isInteger(body.revision) ? body.revision : 0;
  showResult(r);
  render();
}

function badLink() {
  S.view = "ask";
  S.busy = null;
  S.error = { kind: "link" };
  history.replaceState(null, "", location.pathname);
  render();
}

async function findRegion(text) {
  const q = text.trim();
  if (!q) return null;
  const hit = regionChoices().find(([name]) => name.toLowerCase() === q.toLowerCase());
  if (hit) return hit[1];
  const r = await call("find", `/api/geocode?q=${encodeURIComponent(q)}`);
  S.error = null;
  if (r?.results?.length) return r.results[0];
  S.notice = { kind: "no_place", q };
  render();
  return undefined;
}

async function share() {
  const link = location.origin + location.pathname + shareHash(S.result);
  const copied = await navigator.clipboard.writeText(link).then(() => true, () => false);
  S.notice = { kind: "share", link, copied };
  render();
}

async function showAbout() {
  S.view = "about";
  if (!S.sources) {
    const r = await call("about", "/api/sources");
    if (r) S.sources = r;
  }
  render();
}

function route() {
  const h = location.hash;
  if (h === "#about") return showAbout();
  if (h.startsWith("#q=")) {
    if (S.result && h === shareHash(S.result)) {
      S.view = "result";
      return render();
    }
    return openLink(h.slice(3));
  }
  if (S.view === "about") S.view = S.result ? "result" : "ask";
  render();
}

function goHome() {
  S.view = "ask";
  S.error = null;
  S.notice = null;
  history.replaceState(null, "", location.pathname);
  render();
}

function leaveAbout() {
  location.hash = S.result ? shareHash(S.result) : "";
}

function errorBox() {
  const e = S.error;
  if (!e) return "";
  const msg = e.kind === "request" ? `${t("error.request")} ${fieldName(e.field)}`
    : e.kind === "data_source" ? t("error.source", { url: e.url ?? "" })
    : e.kind === "link" ? t("error.link")
    : t("error.network");
  return `<p class="alert" role="alert">${msg}</p>`;
}

function busyLabel(kind, idle) {
  return S.busy === kind ? t(`busy.${kind}`) : idle;
}

function viewAsk() {
  const on = S.ai && aiAvailable();
  return `<section class="ask">
    <h2 id="h-view" tabindex="-1">${t("ask.title")}</h2>
    <p class="lede">${t("ask.lede")}</p>
    ${errorBox()}
    <label class="sr-only" for="ask-text">${t("ask.label")}</label>
    <textarea id="ask-text" maxlength="600" rows="3" placeholder="${t("ask.placeholder")}">${esc(S.text)}</textarea>
    <div class="ask-row">
      <label class="switch${aiAvailable() ? "" : " off"}">
        <input id="ai" type="checkbox" role="switch" ${on ? "checked" : ""} ${aiAvailable() ? "" : "disabled"} aria-describedby="ai-note">
        <span><strong>${t("ask.ai")}</strong> <span id="ai-note">${t("ask.ai_note")}${aiAvailable() ? "" : ` ${t("ask.ai_unavailable")}`}</span></span>
      </label>
      <button id="ask-go" class="primary" data-act="ask" ${S.busy ? "disabled" : ""}>${busyLabel("read", t("ask.go"))}</button>
    </div>
    <p class="hint">${t("ask.hint")}</p>
    <h3 class="eyebrow">${t("ask.try")}</h3>
    <ul class="chips">${[1, 2, 3, 4, 5].map(n => `<li><button id="chip-${n}" class="chip" data-act="chip" data-n="${n}">${t(`demo.${n}`)}</button></li>`).join("")}</ul>
    <p><button id="by-hand" class="link" data-act="hand">${t("ask.by_hand")}</button></p>
  </section>`;
}

const opt = (value, text, selected) => `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${text}</option>`;
const select = (id, name, options, extra = "") => `<select id="${id}" data-field="${name}" ${extra}>${options}</select>`;

function variableOptions(blank, selected) {
  const c = S.catalog;
  return opt("", blank, selected) + c.topics.map(tp =>
    `<optgroup label="${esc(label(tp.label))}">${c.variables.filter(v => v.topics[0] === tp.id)
      .map(v => opt(v.id, esc(label(v.label)), selected)).join("")}</optgroup>`).join("");
}

const regionEditor = {
  view: (v, f) => `<input id="f-${f.name}" data-field="${f.name}" list="eb-regions" autocomplete="off" value="${esc(regionName(v))}" placeholder="${t("card.place_hint")}">
    <datalist id="eb-regions">${regionChoices().map(([n]) => `<option value="${esc(n)}"></option>`).join("")}</datalist>`,
  change: el => findRegion(el.value),
};

const variableEditor = {
  view: (v, f) => select(`f-${f.name}`, f.name, variableOptions(t("card.choose"), v ?? "")),
  change: el => el.value || null,
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
};

const numberEditor = {
  view: (v, f) => `<input id="f-${f.name}" type="number" inputmode="numeric" data-field="${f.name}" value="${esc(v ?? "")}">`,
  change: el => (el.value === "" ? null : Number(el.value)),
};

const choiceEditor = opts => ({
  view: (v, f) => select(`f-${f.name}`, f.name, opts.map(o => opt(o, t(`card.opt.${o}`), v ?? opts[0])).join("")),
  change: el => el.value,
});

const amongEditor = {
  view: (v, f) => select(`f-${f.name}`, f.name, S.catalog.groups.map(g => opt(g.id, esc(label(g.name)), v)).join("")),
  change: el => el.value || null,
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

function viewCard() {
  const r = S.read, fields = r.draft.fields, kind = fields.kind, meta = S.catalog.kinds[kind];
  const kinds = Object.keys(S.catalog.kinds);
  const options = [...kinds, ...(meta ? [] : [kind])]
    .map(k => `<option value="${esc(k)}"${k === kind ? " selected" : ""}>${t(`kind.${k}`)}${S.catalog.kinds[k] ? "" : ` (${t("card.not_built")})`}</option>`).join("");
  const controls = meta ? meta.fields.map(f => `<fieldset class="field">
      <legend>${fieldName(f.name)}${f.required ? "" : ` <span class="opt">${t("card.optional")}</span>`}</legend>
      ${EDITORS[f.name].view(fields[f.name], f)}
    </fieldset>`).join("") : `<p class="note">${t("card.kind_later")}</p>`;
  const why = !meta ? t("card.kind_later") : r.missing.length ? `${t("card.missing")} ${r.missing.map(fieldName).join(", ")}` : "";
  const notice = S.notice?.kind === "no_place" ? `<p class="note" role="status">${t("card.no_place", { q: S.notice.q })}</p>` : "";
  return `<section class="card">
    <h2 id="h-view" tabindex="-1">${t("card.title")}</h2>
    <p class="lede">${t("card.lede")}</p>
    ${r.draft.quote ? `<blockquote class="quote"><span class="eyebrow">${t("card.you_wrote")}</span>${esc(r.draft.quote)}</blockquote>` : ""}
    ${r.ai_failed ? `<p class="note">${t("card.ai_failed")}</p>` : ""}
    ${errorBox()}
    <fieldset class="field"><legend>${t("card.kind")}</legend>
      <select id="f-kind" data-field="kind">${options}</select>
    </fieldset>
    ${controls}
    ${notice}
    ${r.draft.leads.length ? `<p class="note">${t("card.leads")} ${r.draft.leads.map(esc).join(", ")}</p>` : ""}
    ${r.draft.unmapped.length ? `<p class="note">${t("card.unmapped")} ${r.draft.unmapped.map(esc).join(", ")}</p>` : ""}
    <div class="card-actions">
      <button id="run" class="primary" data-act="run" ${!S.question || S.busy ? "disabled" : ""} ${why ? 'aria-describedby="run-why"' : ""}>${busyLabel("run", t("card.run"))}</button>
      <button id="card-back" class="link" data-act="home">${t("card.back")}</button>
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

// Read by tests/test_web_sync.py: one key per line between `const PANELS = {` and `};`.
const PANELS = {
  claim: panelClaim,
  trend: panelTrend,
};

function chartsBlock(charts) {
  if (!charts.length) return "";
  const i = Math.min(S.tab, charts.length - 1), many = charts.length > 1;
  const tabs = many ? `<div class="tabs" role="tablist" aria-label="${t("result.charts")}">${charts.map((c, j) =>
    `<button role="tab" id="tab-${j}" aria-selected="${j === i}" aria-controls="tabpanel" tabindex="${j === i ? 0 : -1}" data-act="tab" data-i="${j}">${esc(c.title)}</button>`).join("")}</div>` : "";
  const chart = CHARTS[charts[i].type]?.(charts[i]) ?? "";
  return `<section class="panel">
    <h3>${t("result.charts")}</h3>
    ${tabs}
    <div id="tabpanel" ${many ? `role="tabpanel" aria-labelledby="tab-${i}"` : ""}>${chart}</div>
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

const AUDIENCES = ["student", "policymaker", "researcher"];
const bold = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

function explanationBlock() {
  const e = S.explanation;
  if (e === false) return "";
  const body = e ? `<p class="short">${bold(e.short)}</p>
      <details id="more"${S.more ? " open" : ""}><summary>${t("explain.more")}</summary><p>${bold(e.more)}</p></details>
      ${e.via === "ai" ? `<p class="small">${t("explain.ai")}</p>` : ""}`
    : `<p class="short busy" role="status">${t("explain.busy")}</p>`;
  return `<section class="panel explain" aria-live="polite">
    <h3>${t("explain.title")}</h3>
    ${body}
    <div class="audience"><span id="aud-label" class="small">${t("explain.for")}</span>
      <span class="seg" role="radiogroup" aria-labelledby="aud-label">${AUDIENCES.map(a => `<label><input type="radio" id="aud-${a}" name="audience" value="${a}" ${S.audience === a ? "checked" : ""}><span>${t(`explain.audience.${a}`)}</span></label>`).join("")}</span>
    </div>
  </section>`;
}

function viewResult() {
  const r = S.result, quote = S.read?.draft.quote;
  const n = S.notice?.kind === "share" ? `<div class="share" role="status">
      <span>${S.notice.copied ? t("result.copied") : t("result.copy_this")}</span>
      <input id="share-link" readonly value="${esc(S.notice.link)}" aria-label="${t("result.share")}">
    </div>` : "";
  return `<article class="result">
    <section class="verdict lvl-${esc(r.verdict.level)}">
      <p class="badge"><span class="dot" aria-hidden="true"></span>${t(`level.${r.verdict.level}`)}</p>
      <h2 id="h-view" tabindex="-1">${r.headline.map(s => (s.hl ? `<strong>${esc(s.t)}</strong>` : esc(s.t))).join("")}</h2>
      ${quote ? `<p class="asked">${t("result.asked")} “${esc(quote)}”</p>` : ""}
      <div class="actions">
        <button id="edit" data-act="edit">${t("result.edit")}</button>
        <button id="share" data-act="share">${t("result.share")}</button>
        <button id="again" class="link" data-act="home">${t("result.new")}</button>
      </div>
      ${n}
    </section>
    ${explanationBlock()}
    ${errorBox()}
    ${r.notes.length ? `<ul class="notes">${r.notes.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    <ul class="tiles">${r.tiles.map(x => `<li class="tile">
      <span class="tile-label">${esc(x.label)}</span>
      <span class="tile-value">${esc(x.value)}</span>
      ${x.note ? `<span class="tile-note">${esc(x.note)}</span>` : ""}
    </li>`).join("")}</ul>
    ${chartsBlock(r.charts)}
    ${PANELS[r.kind]?.(r) ?? ""}
    <section class="panel">
      <h3>${t("result.method")}</h3>
      <ol class="steps">${r.method.map(s => `<li><strong>${esc(s.title)}</strong><p>${esc(s.did)}</p><p class="why-step">${esc(s.why)}</p></li>`).join("")}</ol>
    </section>
    <section class="panel">
      <h3>${t("result.sources")}</h3>
      <ul class="sources">${r.sources.map(s => sourceItem(s, false)).join("")}</ul>
    </section>
  </article>`;
}

function viewAbout() {
  return `<section class="about">
    <h2 id="h-view" tabindex="-1">${t("about.title")}</h2>
    <p class="lede">${t("about.rule")}</p>
    <p>${t("about.places")}</p>
    <p>${t("about.ai")}</p>
    ${errorBox()}
    <h3>${t("about.registry")}</h3>
    ${S.sources ? `<ul class="sources">${S.sources.map(s => sourceItem(s, true)).join("")}</ul>` : `<p>${t("busy.about")}</p>`}
    <p><button id="about-back" class="link" data-act="back">${t("about.back")}</button></p>
  </section>`;
}

const VIEWS = { ask: viewAsk, card: viewCard, result: viewResult, about: viewAbout };

let lastView = null;
function render() {
  const focused = document.activeElement?.id;
  $panel.innerHTML = S.catalog ? VIEWS[S.view]() : `<p>${t("busy.load")}</p>`;
  if (S.view !== lastView) {
    lastView = S.view;
    document.getElementById("h-view")?.focus();
    window.scrollTo(0, 0);
  } else if (focused) {
    document.getElementById(focused)?.focus();
  }
}

const ACTIONS = {
  ask,
  chip: el => {
    S.text = t(`demo.${el.dataset.n}`);
    return ask();
  },
  hand: () => {
    S.read = null;
    S.revision = 0;
    S.shown = false;
    return reread({ kind: Object.keys(S.catalog.kinds)[0] });
  },
  run,
  edit: () => {
    S.notice = null;
    return reread({ ...S.result.question });
  },
  share,
  home: goHome,
  back: leaveAbout,
  rm: el => edit("tests", S.read.draft.fields.tests.filter((_, i) => i !== +el.dataset.i)),
  tab: el => {
    S.tab = +el.dataset.i;
    render();
  },
};

$panel.addEventListener("click", e => {
  const el = e.target.closest("[data-act]");
  if (el) ACTIONS[el.dataset.act]?.(el);
});

$panel.addEventListener("change", async e => {
  const el = e.target;
  if (el.id === "ai") {
    S.ai = el.checked;
    try {
      localStorage.setItem("eb-ai", S.ai ? "1" : "0");
    } catch {}
    return;
  }
  if (el.name === "audience") {
    S.audience = el.value;
    return explain();
  }
  const name = el.dataset.field;
  if (!name) return;
  if (name === "kind") return reread({ ...S.read.draft.fields, kind: el.value });
  const value = await EDITORS[name].change(el, S.read.draft.fields[name]);
  if (value !== undefined) edit(name, value);
});

$panel.addEventListener("toggle", e => {
  if (e.target.id === "more") S.more = e.target.open;
}, true);

$panel.addEventListener("input", e => {
  if (e.target.id === "ask-text") S.text = e.target.value;
});

$panel.addEventListener("keydown", e => {
  if (e.target.id === "ask-text" && e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    ask();
  }
  if (e.target.getAttribute("role") === "tab" && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
    const n = S.result.charts.length;
    S.tab = (S.tab + (e.key === "ArrowRight" ? 1 : n - 1)) % n;
    render();
    document.getElementById(`tab-${S.tab}`)?.focus();
  }
});

function shell() {
  document.getElementById("top").innerHTML = `<a class="brand" href="#" data-home>${t("app.name")}</a>
    <nav><a href="#about">${t("nav.about")}</a></nav>`;
  document.getElementById("foot").innerHTML = `<p>${t("foot.ai")}</p><p><a href="#about">${t("nav.about")}</a></p>`;
  document.querySelector("[data-home]").addEventListener("click", e => {
    e.preventDefault();
    goHome();
  });
}

async function boot() {
  try { S.ai = localStorage.getItem("eb-ai") === "1"; } catch { S.ai = false; }
  document.documentElement.lang = S.lang;
  shell();
  render();
  try {
    [S.catalog, S.status] = await Promise.all(["/api/catalog", "/api/status"].map(p => fetch(p).then(r => r.json())));
  } catch {
    $panel.innerHTML = `<p class="alert" role="alert">${t("error.network")}</p>`;
    return;
  }
  window.addEventListener("hashchange", route);
  route();
}

boot();
