"use strict";

const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg";
const WARM = [194, 65, 12], COOL = [37, 99, 235], GREY = "#8a918d";
const EMPTY = { type: "FeatureCollection", features: [] };
const M = { map: null, ready: null, variable: "heat", summary: null, countries: null, cells: false };

function tone(v, max, warmUp) {
  const c = (v >= 0) === warmUp ? WARM : COOL, s = 0.25 + 0.75 * Math.min(1, Math.abs(v) / (max || 1));
  return `rgb(${c.map(x => Math.round(255 + (x - 255) * s)).join(",")})`;
}

const warmUp = id => Boolean(byId(S.catalog.variables, id)?.warm_up);
const swatch = rgb => `<span class="key" style="background:rgb(${rgb.join(",")})"></span>`;

function countryColours() {
  const rows = Object.entries(M.summary[M.variable] ?? {}).filter(([, r]) => r.clear);
  const max = Math.max(0, ...rows.map(([, r]) => Math.abs(r.trend_per_decade)));
  const pairs = rows.flatMap(([iso, r]) => [iso, tone(r.trend_per_decade, max, warmUp(M.variable))]);
  return pairs.length ? ["match", ["get", "id"], ...pairs, GREY] : GREY;
}

function mapKey() {
  const [from, to] = S.catalog.years, up = warmUp(M.variable);
  const options = Object.keys(M.summary).filter(id => byId(S.catalog.variables, id))
    .map(id => opt(id, esc(varName(id)), M.variable)).join("");
  document.getElementById("map-key").innerHTML = `<label for="map-var">${t("map.variable", { from, to })}</label>
    <select id="map-var">${options}</select>
    <ul class="map-legend">
      <li>${swatch(up ? WARM : COOL)}${t("map.rising")}</li>
      <li>${swatch(up ? COOL : WARM)}${t("map.falling")}</li>
      <li><span class="key k-grey"></span>${t("map.grey")}</li>
      ${M.cells ? `<li><span class="key k-clear"></span>${t("map.cells")}</li>` : ""}
    </ul>
    <p class="small">${t("map.click")}</p>`;
}

function rect([s, w, n, e], properties = {}) {
  return { type: "Feature", properties, geometry: { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } };
}

function overlay(r) {
  const cells = r?.charts.find(c => c.type === "cells");
  if (cells) {
    const max = Math.max(...cells.cells.map(c => Math.abs(c[2])));
    const [dlat, dlon] = cells.cell_size;
    return cells.cells.map(([lat, lon, v, clear]) => rect([lat - dlat / 2, lon - dlon / 2, lat + dlat / 2, lon + dlon / 2],
      { colour: tone(v, max, cells.warm_up), clear }));
  }
  const region = r?.question.region ?? r?.question.point;
  if (!region) return [];
  if (region.kind === "point") return [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [region.lon, region.lat] } }];
  if (region.kind === "place") return [rect(byId(S.catalog.places, region.id).bbox)];
  return M.countries.features.filter(f => f.properties.id === region.iso3);
}

function bounds(features) {
  const pts = features.flatMap(f => (f.geometry.type === "Point" ? [f.geometry.coordinates] : f.geometry.coordinates.flat(f.geometry.type === "Polygon" ? 1 : 2)));
  const lons = pts.map(p => p[0]), lats = pts.map(p => p[1]);
  return [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]];
}

async function mapShow(r) {
  if (!(await M.ready)) return;
  const features = overlay(r);
  M.cells = features.some(f => f.properties.colour);
  M.map.getSource("result").setData({ type: "FeatureCollection", features });
  mapKey();
  if (!features.length) return;
  const top = document.getElementById("map-key").offsetHeight + 24;
  M.map.fitBounds(bounds(features), { padding: { top, bottom: 48, left: 24, right: 24 }, maxZoom: 7, duration: 1200 });
}

function mapClick(e) {
  const at = e.lngLat.wrap(), [lat, lon] = [+at.lat.toFixed(2), +at.lng.toFixed(2)];
  const point = { kind: "point", lat, lon, name: `${lat}, ${lon}` };
  const iso3 = M.map.queryRenderedFeatures(e.point, { layers: ["countries"] })[0]?.properties.id;
  mapPicked(point, S.catalog.countries[iso3] ? { kind: "country", iso3 } : point);
}

function mapInit() {
  M.ready = loadMap();
}

async function loadMap() {
  const el = document.getElementById("map");
  if (!window.maplibregl) return false;
  el.setAttribute("aria-label", t("map.label"));
  let sources;
  try {
    [M.countries, M.summary, sources] = await Promise.all(["/data/countries.geojson", "/data/summary.json", "/api/sources"]
      .map(p => fetch(p).then(r => (r.ok ? r.json() : Promise.reject(r)))));
  } catch {
    return false;
  }
  M.map = new maplibregl.Map({
    container: el,
    style: {
      version: 8,
      sources: { gibs: { type: "raster", tiles: [GIBS], tileSize: 256, maxzoom: 8,
        attribution: esc(sources.find(s => s.id === "gibs-bluemarble")?.citation) } },
      layers: [{ id: "gibs", type: "raster", source: "gibs" }],
    },
    center: [104.9, 12.6],
    zoom: 3,
    maxZoom: 9,
    attributionControl: { compact: false },
    dragRotate: false,
  });
  M.map.addControl(new maplibregl.NavigationControl({ showCompass: false }));
  await new Promise(resolve => M.map.on("load", resolve));
  M.map.addSource("countries", { type: "geojson", data: M.countries });
  M.map.addSource("result", { type: "geojson", data: EMPTY });
  M.map.addLayer({ id: "countries", type: "fill", source: "countries", paint: { "fill-color": countryColours(), "fill-opacity": 0.6 } });
  M.map.addLayer({ id: "borders", type: "line", source: "countries", paint: { "line-color": "#fff", "line-width": 0.4, "line-opacity": 0.6 } });
  M.map.addLayer({ id: "cells", type: "fill", source: "result", filter: ["has", "colour"], paint: { "fill-color": ["get", "colour"], "fill-opacity": 0.9 } });
  M.map.addLayer({ id: "outline", type: "line", source: "result", filter: ["!=", ["geometry-type"], "Point"],
    paint: { "line-color": ["case", ["==", ["get", "clear"], true], "#17201c", ["has", "colour"], "rgba(255,255,255,0.7)", "#fff"],
      "line-width": ["case", ["==", ["get", "clear"], true], 2, ["has", "colour"], 0.5, 2.5] } });
  M.map.addLayer({ id: "point", type: "circle", source: "result", filter: ["==", ["geometry-type"], "Point"],
    paint: { "circle-radius": 7, "circle-color": "#0d6b4f", "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
  M.map.on("click", mapClick);
  M.map.on("mouseenter", "countries", () => { M.map.getCanvas().style.cursor = "pointer"; });
  M.map.on("mouseleave", "countries", () => { M.map.getCanvas().style.cursor = ""; });
  mapKey();
  document.getElementById("map-key").addEventListener("change", e => {
    if (e.target.id !== "map-var") return;
    M.variable = e.target.value;
    M.map.setPaintProperty("countries", "fill-color", countryColours());
    mapKey();
  });
  return true;
}
