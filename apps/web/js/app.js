const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const t = (key) => window.FloorI18n?.t(key) || key;
const tf = (key, params) => window.FloorI18n?.format?.(key, params) || t(key);
const activeLocale = () => window.FloorI18n?.locale() || "en";

function slugKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
}

function hasKey(key) {
  const dict = window.FloorI18n?.STRINGS?.en || {};
  return Boolean(dict[key]);
}

function labelStatus(value, fallback = "") {
  const raw = String(value || "").trim();
  if (!raw) return fallback ? t(fallback) : "";
  const full = `status.${slugKey(raw)}`;
  if (hasKey(full)) return t(full);
  const first = slugKey(raw.split(/[\s/·,|]+/)[0] || "");
  if (first && hasKey(`status.${first}`)) return t(`status.${first}`);
  return raw;
}

function labelKind(value, fallback = "kind.event") {
  const raw = String(value || "").trim();
  if (!raw) return t(fallback);
  const key = `kind.${slugKey(raw)}`;
  return hasKey(key) ? t(key) : raw;
}

function labelChange(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const key = `change.${slugKey(raw)}`;
  return hasKey(key) ? t(key) : raw;
}

function releaseStatusLabel(rs) {
  if (!rs) return "";
  if (rs.code === "announced_tba" || rs.is_tba) return t("release.announcedTba");
  if (rs.code === "announced_days" || (rs.days_until != null && rs.days_until >= 0 && !rs.is_tba)) {
    return tf("release.announcedDays", { n: rs.days_until });
  }
  if (rs.code === "announced_not_catalog" || rs.is_announced) return t("release.announcedNotCatalog");
  if (rs.code === "in_catalog") return t("release.inCatalog");
  return rs.label || "";
}

function translateLine(row) {
  if (!row?.key) return row?.text || "";
  const params = { ...(row.params || {}) };
  if (params.status) params.status = labelStatus(params.status);
  if (params.kind) params.kind = labelKind(params.kind, "") || params.kind;
  if (params.related === "not specified") params.related = t("short.notSpecified");
  if (params.status === "planning window") params.status = t("short.planningWindow");
  return tf(row.key, params);
}

function renderShortList(i18nRows, fallbackRows) {
  const rows = Array.isArray(i18nRows) && i18nRows.length
    ? i18nRows.map((row) => translateLine(row))
    : (fallbackRows || []);
  return rows.map((line) => `<li>${escapeHtml(line)}</li>`).join("");
}

const TACTIC_MAP = {
  "Do not homepage this SKU unless a matching trend or event appears": "action.tacticNoHomepage",
  "If a related movie, match, or showcase breaks, re-run this lookup": "action.tacticRerun",
  "Feature the equivalent catalog SKUs for the full event runtime": "action.tacticFeatureRuntime",
  "Do not treat this as a year-round homepage default": "action.tacticNotYearRound",
  "Feature this IP on the storefront homepage for the next 24 hours while search interest is elevated": "action.tacticTrendHome",
  "Reuse the trending headline/movie/news creative rather than generic key-art": "action.tacticTrendCreative",
  "Hold current-edition price; attach DLC/currency underneath the hero SKU": "action.tacticHoldPrice",
  "Raise merchandising rank while Wikipedia attention is above baseline": "action.tacticWikiRank",
  "Pair the game with the related show/movie/IP landing module": "action.tacticWikiPair",
};

function translateTactic(text) {
  const key = TACTIC_MAP[String(text || "").trim()];
  return key ? t(key) : text;
}

function actionHeadline(action) {
  const i18n = action?.i18n;
  if (i18n?.headline_key) return tf(i18n.headline_key, i18n.headline_params || {});
  return action?.headline || "";
}

function actionDetail(action) {
  const i18n = action?.i18n;
  if (i18n?.detail_key) return t(i18n.detail_key);
  return action?.detail || "";
}

function actionTactics(action) {
  const i18n = action?.i18n;
  if (Array.isArray(i18n?.tactic_keys) && i18n.tactic_keys.length) {
    return i18n.tactic_keys.map((key) => t(key));
  }
  return (action?.tactics || []).map(translateTactic);
}

function boolLabel(value) {
  return t(value ? "bool.true" : "bool.false");
}

async function getJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || t("common.requestFailed"));
  }
  return res.json();
}

function money(value) {
  const n = Number(value) || 0;
  const abs = Math.abs(n);
  if (abs >= 1e6) {
    const compact = n / 1e6;
    const digits = compact >= 10 ? 1 : 2;
    return `$${compact.toLocaleString(activeLocale(), { maximumFractionDigits: digits, minimumFractionDigits: digits })}M`;
  }
  if (abs >= 1000) {
    return `$${Math.round(n).toLocaleString(activeLocale())}`;
  }
  return `$${n.toLocaleString(activeLocale(), { maximumFractionDigits: 0 })}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function niceDate(value) {
  if (!value || String(value).length < 10) return value || "—";
  const [year, month, day] = String(value).slice(0, 10).split("-");
  const parsed = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  return new Intl.DateTimeFormat(activeLocale(), {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

function leaderProductTable(rows, gmvKey = "lifetime_gmv") {
  const gmvLabel = gmvKey === "year_gmv" ? t("dash.observedGmv") : t("dash.kpis.lifetimeGmv");
  const body = (rows || []).map((row, i) => `<tr>
    <td>${i + 1}</td>
    <td><button type="button" class="linkish" data-open="${escapeHtml(row.canonical_title)}">${escapeHtml(row.canonical_title)}</button>
      <div class="meta">${Number(row.sku_count || 0).toLocaleString(activeLocale())} ${t("dash.skus")} · ${t("dash.peakWeek")} ${escapeHtml(niceDate(row.best_week_start))} · ${money(row.best_week_gmv)}</div></td>
    <td>${money(row[gmvKey] ?? row.lifetime_gmv)}</td>
    <td>${maxGmvEventCell(row)}</td>
  </tr>`).join("") || `<tr><td colspan="4" class="meta">${t("dash.none")}</td></tr>`;
  return `<table><thead><tr><th>#</th><th>${t("dash.titleCol")}</th><th>${gmvLabel}</th><th>${t("dash.maxGmvEvent")}</th></tr></thead><tbody>${body}</tbody></table>`;
}

function maxGmvEventCell(row) {
  const name = row?.max_gmv_event || "";
  if (!name) return `<span class="meta">${t("dash.none")}</span>`;
  const gmvBit = Number(row.max_gmv_event_gmv) > 0 ? ` · ${money(row.max_gmv_event_gmv)}` : "";
  return `<button type="button" class="linkish" data-open-event="${escapeHtml(name)}">${escapeHtml(name)}</button>
    <div class="meta">${escapeHtml(row.max_gmv_event_type || "")}${row.max_gmv_event_start ? ` · ${escapeHtml(niceDate(row.max_gmv_event_start))} – ${escapeHtml(niceDate(row.max_gmv_event_end))}` : ""}${gmvBit}</div>`;
}

function recommendedProductsCell(row) {
  const items = row?.recommended_products || [];
  if (!items.length) return `<span class="meta">${t("dash.none")}</span>`;
  return `<div class="rec-list">${items.map((item) => `<div>
    <button type="button" class="linkish" data-open="${escapeHtml(item.canonical_title)}">${escapeHtml(item.canonical_title)}</button>
    <span class="meta"> · ${money(item.year_gmv)}</span>
  </div>`).join("")}</div>`;
}

function leaderEventTable(rows) {
  const body = withoutQuarterTimeframes(rows).map((row, i) => `<tr>
    <td>${i + 1}</td>
    <td><button type="button" class="linkish" data-open-event="${escapeHtml(row.event)}">${escapeHtml(row.event)}</button>
      <div class="meta">${escapeHtml(row.event_type || "")} · ${escapeHtml(niceDate(row.runtime_start))} – ${escapeHtml(niceDate(row.runtime_end))}</div></td>
    <td>${money(row.year_gmv || row.week_gmv)}</td>
    <td>${Number(row.matched_skus || 0).toLocaleString(activeLocale())}</td>
    <td>${recommendedProductsCell(row)}</td>
  </tr>`).join("") || `<tr><td colspan="5" class="meta">${t("dash.none")}</td></tr>`;
  return `<table><thead><tr><th>#</th><th>${t("dash.event")}</th><th>${t("dash.weekGmv")}</th><th>${t("dash.skus")}</th><th>${t("dash.recommendedProducts")}</th></tr></thead><tbody>${body}</tbody></table>`;
}

function productYearEventMatrix(rows) {
  if (!(rows || []).some((row) => (row.year_max_events || []).length)) return "";
  const years = ["2022", "2023", "2024", "2025", "2026"];
  const body = (rows || []).map((row) => {
    const byYear = Object.fromEntries((row.year_max_events || []).map((item) => [item.year, item]));
    return `<tr>
      <td><button type="button" class="linkish" data-open="${escapeHtml(row.canonical_title)}">${escapeHtml(row.canonical_title)}</button></td>
      ${years.map((year) => {
        const item = byYear[year] || {};
        if (!item.max_gmv_event) return `<td class="meta">${t("dash.none")}</td>`;
        const gmvBit = Number(item.max_gmv_event_gmv) > 0 ? `<div class="meta">${money(item.max_gmv_event_gmv)}</div>` : "";
        return `<td><button type="button" class="linkish" data-open-event="${escapeHtml(item.max_gmv_event)}">${escapeHtml(item.max_gmv_event)}</button>
          ${gmvBit}</td>`;
      }).join("")}
    </tr>`;
  }).join("");
  return `<div class="table-scroll year-event-matrix">
    <table>
      <thead><tr><th>${t("dash.titleCol")}</th>${years.map((year) => `<th>${year}</th>`).join("")}</tr></thead>
      <tbody>${body}</tbody>
    </table>
  </div>`;
}

function showPage(name) {
  $$(".page").forEach((el) => el.classList.toggle("is-on", el.id === `page-${name}`));
  $$(".tab").forEach((el) => el.classList.toggle("is-on", el.dataset.page === name));
  $("#tabs").classList.remove("is-open");
  if (name === "dashboard") loadDashboard();
  if (name === "archive") loadArchive();
  if (name === "event") loadFeaturedEvents().catch(() => {});
  if (name === "crosssell") loadFeaturedCrossSell().catch(() => {});
  if (name === "calendar") { /* form is static */ }
  if (name === "trends") loadTrendsBoard();
  if (name === "traffic") loadTrafficBoard();
}

const COVER_FALLBACK = {
  product: "/static/img/placeholder-product.svg",
  event: "/static/img/placeholder-event.svg",
};

function coverHtml(url, alt, wide = false, kind = "product") {
  const fallback = COVER_FALLBACK[kind] || COVER_FALLBACK.product;
  const src = url || fallback;
  return `<img class="cover${wide ? " wide" : ""}" src="${escapeHtml(src)}" alt="${escapeHtml(alt || "")}" loading="lazy"
    onerror="this.onerror=null;this.src='${fallback}';" />`;
}

function dateSpan(row) {
  const label = row?.date_label;
  if (label) return label;
  const start = niceDate(row?.start || row?.runtime_start);
  const end = niceDate(row?.end || row?.runtime_end);
  return end && end !== start ? `${start} → ${end}` : start;
}

function isQuarterTimeframe(name) {
  const raw = String(name || "").trim().toLowerCase().replace(/\s+/g, " ");
  return /^(?:(?:fy|cy)\s*)?(?:20\d{2}\s+)?q\s*[1-4](?:\s*[/,&+|–—-]\s*q\s*[1-4])?(?:\s+20\d{2})?(?:\s+(?:planning\s+|release\s+)?window)?$/.test(raw);
}

function withoutQuarterTimeframes(rows, key = "event") {
  return (rows || []).filter((row) => {
    const name = typeof row === "string" ? row : (row?.[key] || row?.name || "");
    return !isQuarterTimeframe(name);
  });
}

function uniqueEventResults(rows) {
  const seen = new Set();
  const out = [];
  for (const row of rows || []) {
    const raw = String(row.name || row.event || "").trim();
    const name = raw.toLowerCase().replace(/\s+20\d{2}\s*$/, "");
    const start = String(row.start || row.runtime_start || row.event_start || "").slice(0, 10);
    const key = `${name}|${start}`;
    if (!name || isQuarterTimeframe(raw) || seen.has(key)) continue;
    seen.add(key);
    out.push(row);
  }
  return out;
}

function calendarRangeParams() {
  const params = new URLSearchParams();
  const startYear = $("#cal-start-year")?.value;
  const startMonth = $("#cal-start-month")?.value;
  const endYear = $("#cal-end-year")?.value;
  const endMonth = $("#cal-end-month")?.value;
  if (startYear && startMonth && endYear && endMonth) {
    params.set("start_year", startYear);
    params.set("start_month", startMonth);
    params.set("end_year", endYear);
    params.set("end_month", endMonth);
  }
  return params;
}

function calendarSpan() {
  const startYear = Number($("#cal-start-year")?.value || 0);
  const startMonth = Number($("#cal-start-month")?.value || 0);
  const endYear = Number($("#cal-end-year")?.value || 0);
  const endMonth = Number($("#cal-end-month")?.value || 0);
  if (!startYear || !startMonth || !endYear || !endMonth) return null;
  const start = `${startYear}-${String(startMonth).padStart(2, "0")}-01`;
  const last = new Date(endYear, endMonth, 0).getDate();
  const end = `${endYear}-${String(endMonth).padStart(2, "0")}-${String(last).padStart(2, "0")}`;
  return start <= end ? { start, end } : { start: end, end: start };
}

function isCurrentOrInCalendarRange(row) {
  const today = new Date().toISOString().slice(0, 10);
  const start = String(
    row?.runtime_start || row?.event_start || row?.start || row?.promo_start || row?.start_date || ""
  ).slice(0, 10);
  const end = String(
    row?.runtime_end || row?.event_end || row?.end || row?.promo_end || row?.end_date || start
  ).slice(0, 10);
  if (end && end >= today) return true;
  const span = calendarSpan();
  if (!span || !start) return false;
  return start <= span.end && (end || start) >= span.start;
}

function currentOrInRangeEvents(rows) {
  return (rows || []).filter(isCurrentOrInCalendarRange);
}

function ensureMappedEvents(rows, nameKey = "event") {
  const cleaned = withoutQuarterTimeframes(rows, nameKey);
  const filtered = currentOrInRangeEvents(cleaned);
  return filtered.length ? filtered : cleaned.slice(0, 1);
}

function dateConfidenceBadge(row) {
  const kind = String(row?.confirmation || (row?.exact_date ? "confirmed" : "tentative")).toLowerCase();
  const cls = kind === "confirmed" ? "on" : "hot";
  return `<span class="badge ${cls}">${escapeHtml(labelStatus(kind))}</span>`;
}

function verifiedBadge(source) {
  if (!source) return "";
  return `<span class="badge verified" title="${escapeHtml(source)}">✓ ${t("common.verified")}</span>`;
}

function renderChips(items) {
  if (!items?.length) return "";
  return `<div class="chip-row">${items.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>`;
}

function contentHashtagsFor(kit, title) {
  const rows = kit?.correlations || [];
  const match = rows.find((row) => String(row.product || "").toLowerCase() === String(title || "").toLowerCase()) || rows[0];
  const tags = match?.top_hashtags || [];
  if (!tags.length) return `<span class="meta">—</span>`;
  return tags.slice(0, 3).map((tag) => `<span class="hashtag">${escapeHtml(tag)}</span>`).join(" ");
}

function socialHashtags(row) {
  const tags = row?.top_hashtags || [];
  if (!tags.length) return `<span class="meta">—</span>`;
  return tags.slice(0, 4).map((tag) => `<span class="hashtag">${escapeHtml(tag)}</span>`).join(" ");
}

function socialTimes(row) {
  const times = row?.post_times || {};
  const bits = [
    times.tiktok && `TikTok · ${times.tiktok}`,
    times.instagram && `IG · ${times.instagram}`,
    times.youtube_shorts && `Shorts · ${times.youtube_shorts}`,
    times.x && `X · ${times.x}`,
  ].filter(Boolean);
  return bits.length ? bits.map((bit) => escapeHtml(bit)).join("<br>") : "—";
}

function socialAffiliate(row) {
  const aff = row?.affiliate || {};
  if (!aff.url) return `<span class="meta">—</span>`;
  return `<a class="linkish" href="${escapeHtml(aff.url)}" target="_blank" rel="noreferrer">${escapeHtml(aff.label || aff.network || t("brief.affiliate"))}</a>`;
}

function renderSocialCard(p) {
  return `<article class="social-card">
    <div class="social-card-head">
      <span class="badge ${p.role === "game" ? "on" : "hot"}">${escapeHtml(labelKind(p.role || "sku"))}</span>
      <button type="button" class="linkish" data-open-product="${escapeHtml(p.canonical_title)}">${escapeHtml(p.canonical_title)}</button>
      ${p.platform || p.event ? `<p class="meta">${escapeHtml([p.platform, p.event].filter(Boolean).join(" · "))}</p>` : ""}
    </div>
    <div class="social-cols">
      <div>
        <b>${t("brief.content")}</b>
        <div>${socialHashtags(p)}</div>
      </div>
      <div>
        <b>${t("brief.postOn")}</b>
        <p class="meta">${socialTimes(p)}</p>
      </div>
      <div>
        <b>${t("brief.seoKeywords")}</b>
        <p class="meta">${(p.seo_keywords || []).map(escapeHtml).join(" · ") || "—"}</p>
      </div>
      <div>
        <b>${t("brief.affiliate")}</b>
        <div>${socialAffiliate(p)}</div>
      </div>
    </div>
  </article>`;
}

function renderContentMarketing(kit) {
  const rows = withoutQuarterTimeframes(kit?.correlations || []);
  if (!rows.length) {
    return `<section class="card content-kit" style="margin-top:18px">
      <h4>${t("brief.contentMarketing")}</h4>
      <p class="meta">${t("brief.contentEmpty")}</p>
    </section>`;
  }
  return `<section class="card content-kit" style="margin-top:18px">
    <h4>${t("brief.contentMarketing")}</h4>
    <p class="meta">${t("brief.contentHint")}</p>
    <p class="meta">${escapeHtml(kit.disclaimer || "")}</p>
    ${rows.map((row) => {
      const social = Object.values(row.social || {});
      return `<article class="content-correlation">
        <div class="badge-row">
          <span class="badge on">${escapeHtml(labelKind(row.family || "default"))}</span>
          <span class="badge hot">${escapeHtml(labelKind(row.role || "game"))}</span>
          <span class="badge">${escapeHtml(niceDate(row.promo_start))} → ${escapeHtml(niceDate(row.promo_end))}</span>
        </div>
        <h5>
          <button type="button" class="linkish" data-open-product="${escapeHtml(row.product)}">${escapeHtml(row.product)}</button>
          <span class="meta"> × </span>
          <button type="button" class="linkish" data-open-event="${escapeHtml(row.event)}">${escapeHtml(row.event)}</button>
        </h5>
        <p class="meta">${t("brief.runtime")} ${escapeHtml(niceDate(row.runtime_start))} → ${escapeHtml(niceDate(row.runtime_end))}</p>
        <div class="content-social">
          ${social.map((pack) => `<div>
            <b>${escapeHtml(pack.platform)}</b>
            <p class="meta">${t("brief.postWhen")} ${escapeHtml(pack.best_times)}</p>
            <div class="chip-row">${(pack.hashtags || []).map((tag) => `<span class="hashtag">${escapeHtml(tag)}</span>`).join("")}</div>
          </div>`).join("")}
        </div>
        <p class="meta"><b>${t("brief.seoKeywords")}</b> ${(row.seo_keywords || []).map(escapeHtml).join(" · ")}</p>
        ${(row.schedule || []).length ? `<div class="phase-pills">${row.schedule.map((phase) => `<span>${escapeHtml(phase.label || phase.phase)} · ${escapeHtml(phase.cadence)} · ${escapeHtml(niceDate(phase.start))}→${escapeHtml(niceDate(phase.end))}</span>`).join("")}</div>` : ""}
        ${(row.pieces || []).length ? `<div class="table-scroll"><table class="content-pieces">
          <thead><tr>
            <th>${t("brief.piece")}</th>
            <th>${t("brief.postOn")}</th>
            <th>${t("brief.seoKeywords")}</th>
            <th>${t("brief.affiliate")}</th>
          </tr></thead>
          <tbody>
            ${(row.pieces || []).map((piece) => `<tr>
              <td>
                <b>${escapeHtml(piece.format)}</b>
                <p class="meta">${escapeHtml(piece.title)}</p>
                <div class="chip-row">${(piece.hashtags || []).slice(0, 4).map((tag) => `<span class="hashtag">${escapeHtml(tag)}</span>`).join("")}</div>
              </td>
              <td>
                <p>${escapeHtml(niceDate(piece.post_on) || "—")}</p>
                <p class="meta">${escapeHtml(piece.cadence || "")}</p>
                <p class="meta">${escapeHtml(piece.when || "")}</p>
              </td>
              <td class="meta">${(piece.seo_keywords || []).map(escapeHtml).join("<br>")}</td>
              <td>
                <a class="linkish" href="${escapeHtml(piece.affiliate?.url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(piece.affiliate?.label || piece.affiliate?.network || t("brief.affiliate"))}</a>
                <p class="meta">${escapeHtml(piece.affiliate?.note || "")}</p>
              </td>
            </tr>`).join("")}
          </tbody>
        </table></div>` : ""}
      </article>`;
    }).join("")}
  </section>`;
}

function bindContentMarketing(root) {
  if (!root) return;
  $$("[data-open-product]", root).forEach((btn) => btn.addEventListener("click", () => {
    $("#query").value = btn.dataset.openProduct;
    showPage("lookup");
    lookup(btn.dataset.openProduct);
  }));
  $$("[data-open-event]", root).forEach((btn) => btn.addEventListener("click", () => {
    $("#event-query").value = btn.dataset.openEvent;
    showPage("event");
    lookupEvent(btn.dataset.openEvent);
  }));
}

function renderBrief(data) {
  const cat = data.catalog;
  const promo = data.promotion;
  const trend = data.trends;
  const action = data.do_this_today;
  const meta = data.meta || {};
  const windows = ensureMappedEvents(promo.windows || []);
  const active = promo.active_now || [];
  const listings = (cat.listings || []).slice(0, 8);
  const today = new Date().toISOString().slice(0, 10);
  $("#brief").hidden = false;
  $("#brief").innerHTML = `
    <article class="lede">
      <div class="lede-hero">
        ${coverHtml(meta.image_url, data.canonical_title)}
        <div>
          <div class="badge-row">
            <span class="badge on">${escapeHtml(meta.source || t("common.catalog"))}</span>
            <span class="badge ${active.length ? "live" : ""}">${active.length ? t("common.liveEvent") : t("common.noLiveWindow")}</span>
            <span class="badge ${trend ? "hot" : ""}">${trend ? `${t("common.trend")} #${escapeHtml(trend.rank)}` : t("common.notOnTrends")}</span>
            ${meta.confirmation ? `<span class="badge">${escapeHtml(labelStatus(meta.confirmation))}</span>` : ""}
            ${meta.is_announced ? `<span class="badge hot">${t("common.announcedUnreleased")}</span>` : ""}
            ${cat.release_status ? `<span class="badge on">${escapeHtml(releaseStatusLabel(cat.release_status))}</span>` : ""}
            ${meta.release_label ? `<span class="badge">${escapeHtml(meta.release_label)}</span>` : ""}
            ${verifiedBadge(meta.official_source)}
          </div>
          <h3>${escapeHtml(data.canonical_title)}</h3>
          <p class="action">${escapeHtml(actionHeadline(action))}</p>
          <p>${escapeHtml(actionDetail(action))}</p>
          <ul>${renderShortList(data.in_short_i18n, data.in_short)}</ul>
          <p class="meta">${provenanceLine(meta.source || t("common.catalog"), meta.entry_date, meta.last_checked)}</p>
          ${meta.wikipedia_url ? `<p class="meta"><a class="linkish" href="${escapeHtml(meta.wikipedia_url)}" target="_blank" rel="noreferrer">${t("common.openProduct")}</a> · ${escapeHtml(meta.developer || meta.publisher || "")}</p>` : ""}
        </div>
      </div>
    </article>
    <div class="grid-3">
      <section class="card">
        <h4>${t("brief.whatsInStore")}</h4>
        <p class="meta">${Number(cat.sku_count).toLocaleString(activeLocale())} ${t("common.listings")} · ${escapeHtml(niceDate(cat.earliest_release))} → ${escapeHtml(niceDate(cat.latest_release))}</p>
        ${renderChips(cat.platforms || [])}
        ${meta.genre ? `<p class="meta">${escapeHtml(meta.genre)}</p>` : ""}
        <div class="table-scroll"><table>
          <thead><tr><th>${t("common.platform")}</th><th>${t("common.type")}</th><th>${t("common.release")}</th><th>${t("brief.content")}</th></tr></thead>
          <tbody>
            ${listings.map((row) => `<tr>
              <td>${escapeHtml(row.platform)}</td>
              <td>${escapeHtml(row.product_type)}</td>
              <td>${escapeHtml(row.release_label || niceDate(row.release_date))}</td>
              <td class="content-cell">${contentHashtagsFor(data.content_marketing, data.canonical_title)}</td>
            </tr>`).join("")}
          </tbody>
        </table></div>
      </section>
      <section class="card">
        <h4>${t("brief.whenToPromote")}</h4>
        ${windows.length ? windows.map((plan) => {
          const phases = plan.phases || [];
          const runtime = `${niceDate(plan.runtime_start || plan.event_start)} → ${niceDate(plan.runtime_end || plan.event_end)}`;
          const promoWin = `${niceDate(plan.promo_start)} → ${niceDate(plan.promo_end)}`;
          return `<div class="phase">
            <b>${escapeHtml(plan.event)}</b>
            <div class="badge-row" style="margin:6px 0">
              ${dateConfidenceBadge(plan)}
              <span class="badge ${plan.exact_date ? "" : "hot"}">${escapeHtml(plan.date_label || runtime)}${plan.exact_date === false ? ` · ${t("common.window")}` : ""}</span>
              ${verifiedBadge(plan.official_source)}
            </div>
            <div class="sync-rail">
              <div><b>${t("brief.runtime")}</b><br><span class="meta">${escapeHtml(runtime)}</span></div>
              <div><b>${t("brief.promo")}</b><br><span class="meta">${escapeHtml(promoWin)}</span></div>
              ${plan.synced_with_cross_media ? `<span class="badge live">${t("common.syncedCrossMedia")}</span>` : ""}
            </div>
            <div class="phase-pills">${phases.map((phase) => {
              const live = (phase.start || "") <= today && today <= (phase.end || "");
              return `<span class="${live ? "is-now" : ""}">${escapeHtml(phase.name || "")}${live ? ` · ${t("common.now")}` : ""} · ${escapeHtml(niceDate(phase.start))}→${escapeHtml(niceDate(phase.end))}</span>`;
            }).join("")}</div>
          </div>`;
        }).join("") : `<p class="meta">${t("common.noPromoWindow")}</p>`}
      </section>
      <section class="card">
        <h4>${t("brief.searching")}</h4>
        ${trend ? `<p><b>${t("common.priority")} #${escapeHtml(trend.rank)}</b></p>${(trend.reasons || []).map((r) => `<p class="meta">${escapeHtml(r)}</p>`).join("")}` : `<p class="meta">${escapeHtml(actionHeadline(action))}</p>`}
        <ul>${actionTactics(action).map((tactic) => `<li>${escapeHtml(tactic)}</li>`).join("")}</ul>
      </section>
    </div>
    ${renderContentMarketing(data.content_marketing)}
    <div class="grid-2">
      <section class="card feature-card">
        <h4>${t("brief.crossMedia")}</h4>
        ${(data.cross_media || []).length ? `<div class="media-grid">
          ${uniqueEventResults(currentOrInRangeEvents(data.cross_media)).map((row) => `<article class="media-tile">
            ${coverHtml(row.image_url, row.name, true, "event")}
            <div class="badge-row">
              <span class="badge hot">${escapeHtml(row.format || row.type || t("common.entertainment"))}</span>
              <span class="badge">${escapeHtml(labelStatus(row.confirmation || row.status || ""))}</span>
              ${row.synced_with_promote ? `<span class="badge live">${t("common.syncedPromote")}</span>` : ""}
            </div>
            <h5>${escapeHtml(row.name)}</h5>
            <p class="meta">${t("common.runtimeLabel")} ${escapeHtml(niceDate(row.runtime_start || row.start))} → ${escapeHtml(niceDate(row.runtime_end || row.end))}</p>
            ${row.promo_start ? `<p class="meta">${t("common.promote")} ${escapeHtml(niceDate(row.promo_start))} → ${escapeHtml(niceDate(row.promo_end))}</p>` : ""}
            <p>${escapeHtml(row.related || "")}</p>
            ${row.wikipedia_url ? `<a class="linkish" href="${escapeHtml(row.wikipedia_url)}" target="_blank" rel="noreferrer">${t("common.sourcePage")}</a>` : ""}
          </article>`).join("")}
        </div>` : `<p class="meta">${t("common.noCrossMedia")}</p>`}
      </section>
      <section class="card">
        <h4>${t("brief.relatedEvents")}</h4>
        ${(data.related_events || []).length ? `<div class="timeline">
          ${uniqueEventResults(ensureMappedEvents(data.related_events)).map((row) => `<article>
            <button type="button" class="linkish" data-related-event="${escapeHtml(row.name)}">${escapeHtml(row.name)}</button>
            <p class="meta">${escapeHtml(dateSpan(row))} · ${escapeHtml(row.attendance_mode || row.type)} · ${escapeHtml(row.location || row.scope)}</p>
            ${row.correlated_announced ? `<p class="meta">${t("common.announcedTies")}: ${escapeHtml(row.correlated_announced)}</p>` : ""}
          </article>`).join("")}
        </div>` : `<p class="meta">${t("common.noRelatedEvents")}</p>`}
      </section>
    </div>
  `;
  $$("[data-related-event]", $("#brief")).forEach((btn) => btn.addEventListener("click", () => {
    $("#event-query").value = btn.dataset.relatedEvent;
    showPage("event");
    lookupEvent(btn.dataset.relatedEvent);
  }));
  bindContentMarketing($("#brief"));
}

function renderMarketSections(markets) {
  if (!markets || !markets.length) return "";
  return `<section class="card" style="margin-top:18px">
    <h4>${t("brief.byCountry")}</h4>
    <p class="meta">${t("brief.byCountryHint")}</p>
    <div class="geo-placement-grid">
      ${markets.map((market) => `<article class="geo-card${market.geo === "WW" ? " is-worldwide" : ""}">
        <h5>${escapeHtml(market.geo === "WW" ? t("traffic.worldwide") : `${market.country || market.geo} · ${market.geo}`)}</h5>
        <p class="meta">${escapeHtml(market.language || "")}${market.location ? ` · ${escapeHtml(market.location)}` : ""}</p>
        <b>${t("brief.marketProducts")}</b>
        <ul>
          ${(market.products || []).slice(0, 10).map((product) => `<li>
            <button type="button" class="linkish" data-open-product="${escapeHtml(product.canonical_title)}">${escapeHtml(product.canonical_title)}</button>
            ${product.role ? `<span class="meta"> · ${escapeHtml(labelKind(product.role))}</span>` : ""}
          </li>`).join("") || `<li class="meta">${t("traffic.noProducts")}</li>`}
        </ul>
      </article>`).join("")}
    </div>
  </section>`;
}

function renderEventBrief(data) {
  const event = data.event || {};
  $("#event-brief").hidden = false;
  $("#event-brief").innerHTML = `
    <article class="lede">
      <div class="lede-hero">
        ${coverHtml(event.image_url, data.name, true, "event")}
        <div>
          <div class="badge-row">
            <span class="badge on">${escapeHtml(labelKind(event.kind || "event"))}</span>
            <span class="badge live">${escapeHtml(labelStatus(event.confirmation || event.status || "planning"))}</span>
            <span class="badge">${escapeHtml(event.source || t("common.calendar"))}</span>
            <span class="badge ${event.exact_date ? "" : "hot"}">${escapeHtml(dateSpan(event))}${event.exact_date ? "" : ` · ${t("common.window")}`}</span>
            ${verifiedBadge(event.official_source)}
          </div>
          <h3 class="event-title">${escapeHtml(data.name)}</h3>
          <p class="action">${escapeHtml(actionHeadline(data.do_this_today))}</p>
          <p>${escapeHtml(actionDetail(data.do_this_today))}</p>
          <ul>${renderShortList(data.in_short_i18n, data.in_short)}</ul>
          <p class="meta">${provenanceLine(event.source || t("common.calendar"), event.entry_date, event.last_checked)}</p>
          ${event.wikipedia_url ? `<p class="meta"><a class="linkish" href="${escapeHtml(event.wikipedia_url)}" target="_blank" rel="noreferrer">${t("common.openEvent")}</a></p>` : ""}
          <p class="meta"><button type="button" class="linkish" data-open-crosssell="${escapeHtml(data.name)}">${t("common.openCrossSell")}</button></p>
        </div>
      </div>
    </article>
    <div class="kpis compact-kpis">
      <div class="kpi"><b>${escapeHtml(labelKind(event.attendance_mode || "", "") || event.attendance_mode || "—")}</b><span>${t("common.attendance")}</span></div>
      <div class="kpi"><b>${escapeHtml(event.country || event.location || "—")}</b><span>${t("common.country")}</span></div>
      <div class="kpi"><b>${escapeHtml(event.language || "—")}</b><span>${t("common.language")}</span></div>
      <div class="kpi"><b>${escapeHtml(event.location || "—")}</b><span>${t("common.location")}</span></div>
      <div class="kpi"><b>${Number((data.products || []).length).toLocaleString(activeLocale())}</b><span>${t("common.mappedProducts")}</span></div>
    </div>
    <div class="grid-2">
      <section class="card">
        <h4>${t("brief.mappedProducts")}</h4>
        ${(data.products || []).length ? `<div class="priority-art">
          ${data.products.map((row) => `<article>
            ${coverHtml(row.image_url, row.canonical_title)}
            <div>
              <button type="button" class="linkish" data-open-product="${escapeHtml(row.canonical_title)}">${escapeHtml(row.canonical_title)}</button>
              <p class="meta">${escapeHtml(row.release_label || niceDate(row.release_date))} · ${escapeHtml(labelStatus(row.confirmation) || (row.product_types || []).map((x) => labelKind(x)).join(", ") || "")}</p>
            </div>
          </article>`).join("")}
        </div>` : `<p class="meta">${t("common.noCatalogMatch")}</p>`}
        ${(data.announced_products || []).length ? `<p class="meta" style="margin-top:12px">${t("common.includesAnnounced")}: ${Number((data.announced_products || []).length).toLocaleString(activeLocale())}</p>` : ""}
      </section>
      <section class="card">
        <h4>${t("brief.doThis")}</h4>
        <ul>${actionTactics(data.do_this_today).map((tactic) => `<li>${escapeHtml(tactic)}</li>`).join("")}</ul>
        <div class="timeline" style="margin-top:16px">
          ${currentOrInRangeEvents(data.windows || []).slice(0, 4).map((plan) => `<article>
            <b>${escapeHtml(plan.canonical_title)}</b>
            <div class="sync-rail">
              <div><b>${t("brief.runtime")}</b><br><span class="meta">${escapeHtml(niceDate(plan.runtime_start || plan.event_start))} → ${escapeHtml(niceDate(plan.runtime_end || plan.event_end))}</span></div>
              <div><b>${t("brief.promo")}</b><br><span class="meta">${escapeHtml(niceDate(plan.promo_start))} → ${escapeHtml(niceDate(plan.promo_end))}</span></div>
              ${plan.synced_with_cross_media ? `<span class="badge live">${t("common.synced")}</span>` : ""}
            </div>
          </article>`).join("")}
        </div>
      </section>
    </div>
    ${renderMarketSections(data.markets)}
    ${renderContentMarketing(data.content_marketing)}
    ${(data.related_releases || []).length ? `<section class="card">
      <h4>${t("brief.nearFranchise")}</h4>
      <div class="media-grid">
        ${uniqueEventResults(currentOrInRangeEvents(data.related_releases)).map((row) => `<article class="media-tile">
          ${coverHtml(row.image_url, row.name, true, "event")}
          <span class="badge hot">${escapeHtml(row.format || row.type)}</span>
          ${row.synced_with_promote ? `<span class="badge live">${t("common.syncedPromote")}</span>` : ""}
          <h5>${escapeHtml(row.name)}</h5>
          <p class="meta">${t("common.runtimeLabel")} ${escapeHtml(niceDate(row.runtime_start || row.start))} → ${escapeHtml(niceDate(row.runtime_end || row.end))}</p>
          ${row.promo_start ? `<p class="meta">${t("common.promote")} ${escapeHtml(niceDate(row.promo_start))} → ${escapeHtml(niceDate(row.promo_end))}</p>` : ""}
        </article>`).join("")}
      </div>
    </section>` : ""}
  `;
  $$("[data-open-product]", $("#event-brief")).forEach((btn) => btn.addEventListener("click", () => {
    $("#query").value = btn.dataset.openProduct;
    showPage("lookup");
    lookup(btn.dataset.openProduct);
  }));
  $$("[data-open-crosssell]", $("#event-brief")).forEach((btn) => btn.addEventListener("click", () => {
    $("#crosssell-query").value = btn.dataset.openCrosssell;
    showPage("crosssell");
    lookupCrossSell(btn.dataset.openCrosssell);
  }));
  $$("[data-open-event]", $("#event-brief")).forEach((btn) => btn.addEventListener("click", () => {
    $("#event-query").value = btn.dataset.openEvent;
    lookupEvent(btn.dataset.openEvent);
  }));
}

async function lookup(title) {
  const status = $("#lookup-status");
  status.hidden = false;
  status.textContent = t("status.lookup");
  try {
    const params = calendarRangeParams();
    params.set("q", title);
    const data = await getJSON(`/api/brief?${params}`);
    status.hidden = true;
    renderBrief(data);
  } catch (err) {
    status.textContent = err.message;
    $("#brief").hidden = true;
  }
}

async function lookupEvent(name) {
  const status = $("#event-status");
  status.hidden = false;
  status.textContent = t("status.event");
  try {
    const data = await getJSON(`/api/event?${new URLSearchParams({ q: name })}`);
    status.hidden = true;
    renderEventBrief(data);
  } catch (err) {
    status.textContent = err.message;
    $("#event-brief").hidden = true;
  }
}

function renderCrossSellBrief(data) {
  const event = data.event || {};
  const hero = data.hero || {};
  const byRole = data.by_role || {};
  const products = data.products || [];
  $("#crosssell-brief").hidden = false;
  $("#crosssell-brief").innerHTML = `
    <article class="lede">
      <div class="lede-hero">
        ${coverHtml(event.image_url || hero.image_url, data.name, true, "event")}
        <div>
          <div class="badge-row">
            <span class="badge on">${escapeHtml(labelKind(data.kind || "event"))}</span>
            <span class="badge ${data.live_runtime ? "live" : ""}">${data.live_runtime ? t("common.runtimeLive") : t("common.runtimeWindow")}</span>
            <span class="badge ${data.live_promo ? "hot" : ""}">${data.live_promo ? t("common.promoLive") : t("common.promoWindow")}</span>
            <span class="badge">${t("crosssell.submit")}</span>
          </div>
          <h3 class="event-title">${escapeHtml(data.name)}</h3>
          <p class="action">${escapeHtml(actionHeadline(data.do_this_today))}</p>
          <p>${escapeHtml(actionDetail(data.do_this_today))}</p>
          <ul>${renderShortList(data.in_short_i18n, data.in_short)}</ul>
          <div class="sync-rail" style="margin-top:12px">
            <div><b>${t("brief.runtime")}</b><br><span class="meta">${escapeHtml(niceDate(data.runtime_start))} → ${escapeHtml(niceDate(data.runtime_end))}</span></div>
            <div><b>${t("brief.promoteCrossSellWindow")}</b><br><span class="meta">${escapeHtml(niceDate(data.promo_start))} → ${escapeHtml(niceDate(data.promo_end))}</span></div>
          </div>
        </div>
      </div>
    </article>
    <div class="kpis compact-kpis">
      <div class="kpi"><b>${Number(data.product_count || 0).toLocaleString(activeLocale())}</b><span>${t("common.crossSellSkus")}</span></div>
      <div class="kpi"><b>${escapeHtml(event.country || event.location || "—")}</b><span>${t("common.country")}</span></div>
      <div class="kpi"><b>${escapeHtml(event.language || "—")}</b><span>${t("common.language")}</span></div>
      <div class="kpi"><b>${Number(data.game_count || 0).toLocaleString(activeLocale())}</b><span>${t("common.games")}</span></div>
      <div class="kpi"><b>${Number(data.attach_count || 0).toLocaleString(activeLocale())}</b><span>${t("common.attachProducts")}</span></div>
    </div>
    <div class="grid-2">
      <section class="card feature-card">
        <h4>${t("brief.heroGame")}</h4>
        ${hero.canonical_title ? `
          <div class="lede-hero" style="grid-template-columns: 120px 1fr; gap: 14px;">
            ${coverHtml(hero.image_url, hero.canonical_title)}
            <div>
              <h5><button type="button" class="linkish" data-open-product="${escapeHtml(hero.canonical_title)}">${escapeHtml(hero.canonical_title)}</button></h5>
              <p class="meta">${escapeHtml(hero.platform)} · ${escapeHtml(labelKind(hero.role))} · ${escapeHtml(hero.offer || "")}</p>
              <p>${escapeHtml(hero.strategy_summary || "")}</p>
              <ul>${actionTactics(data.do_this_today).map((tactic) => `<li>${escapeHtml(tactic)}</li>`).join("")}</ul>
            </div>
          </div>` : `<p class="meta">${t("common.noHero")}</p>`}
      </section>
      <section class="card">
        <h4>${t("brief.doThis")}</h4>
        <ul>${actionTactics(data.do_this_today).map((tactic) => `<li>${escapeHtml(tactic)}</li>`).join("")}</ul>
        ${(hero.phases || []).length ? `<div class="timeline" style="margin-top:16px">
          ${hero.phases.map((phase) => `<article>
            <b>${escapeHtml(phase.label || phase.name)}</b>
            <p class="meta">${escapeHtml(niceDate(phase.start))} → ${escapeHtml(niceDate(phase.end))}</p>
          </article>`).join("")}
        </div>` : ""}
      </section>
    </div>
    <section class="card" style="margin-top:18px">
      <h4>${t("brief.attachProducts")}</h4>
      ${products.length ? `<div class="priority-art">
        ${products.map((row) => `<article>
          ${coverHtml(row.image_url, row.canonical_title)}
          <div>
            <div class="badge-row">
              <span class="badge ${row.role === "game" ? "on" : "hot"}">${escapeHtml(labelKind(row.role || "sku"))}</span>
              <span class="badge">${escapeHtml(row.platform || "")}</span>
            </div>
            <button type="button" class="linkish" data-open-product="${escapeHtml(row.canonical_title)}">${escapeHtml(row.canonical_title)}</button>
            <p class="meta">${escapeHtml(row.offer || "")}</p>
            <p class="meta">${t("common.runtimeLabel")} ${escapeHtml(niceDate(row.runtime_start))} → ${escapeHtml(niceDate(row.runtime_end))}</p>
          </div>
        </article>`).join("")}
      </div>` : `<p class="meta">${t("common.noCrossSellProducts")}</p>`}
    </section>
    ${Object.keys(byRole).length ? `<div class="grid-2" style="margin-top:18px">
      ${Object.entries(byRole).map(([role, rows]) => `<section class="card">
        <h4>${escapeHtml(labelKind(role))} (${Number(rows.length).toLocaleString(activeLocale())})</h4>
        <ul>${rows.slice(0, 10).map((row) => `<li>
          <button type="button" class="linkish" data-open-product="${escapeHtml(row.canonical_title)}">${escapeHtml(row.canonical_title)}</button>
          <span class="meta"> · ${escapeHtml(row.platform || "")}</span>
        </li>`).join("")}</ul>
      </section>`).join("")}
    </div>` : ""}
    ${renderMarketSections(data.markets)}
    ${renderContentMarketing(data.content_marketing)}
  `;
  $$("[data-open-product]", $("#crosssell-brief")).forEach((btn) => btn.addEventListener("click", () => {
    $("#query").value = btn.dataset.openProduct;
    showPage("lookup");
    lookup(btn.dataset.openProduct);
  }));
  $$("[data-open-event]", $("#crosssell-brief")).forEach((btn) => btn.addEventListener("click", () => {
    $("#event-query").value = btn.dataset.openEvent;
    showPage("event");
    lookupEvent(btn.dataset.openEvent);
  }));
}

async function lookupCrossSell(name) {
  const status = $("#crosssell-status");
  status.hidden = false;
  status.textContent = t("status.crosssell");
  try {
    const data = await getJSON(`/api/cross-sell?q=${encodeURIComponent(name)}`);
    status.hidden = true;
    renderCrossSellBrief(data);
  } catch (err) {
    status.textContent = err.message;
    $("#crosssell-brief").hidden = true;
  }
}

async function loadFeaturedCrossSell() {
  const select = $("#featured-crosssell");
  if (!select || select.dataset.ready) return;
  const data = await getJSON("/api/cross-sell/events?limit=50");
  for (const row of data.results || []) {
    if (isQuarterTimeframe(row.name)) continue;
    const opt = document.createElement("option");
    opt.value = row.name;
    opt.textContent = row.name;
    select.append(opt);
  }
  select.dataset.ready = "1";
}

function renderCalendarBrief(data) {
  const rangeLabel = `${t(`month.${data.start_month}`)} ${data.start_year} → ${t(`month.${data.end_month}`)} ${data.end_year}`;
  const events = uniqueEventResults(data.events || []);
  $("#calendar-brief").hidden = false;
  $("#calendar-brief").innerHTML = `
    <article class="lede">
      <div class="badge-row">
        <span class="badge on">${t("common.calendarWindow")}</span>
        <span class="badge live">${escapeHtml(rangeLabel)}</span>
        <span class="badge">${escapeHtml(labelKind(data.kind || "all"))}</span>
      </div>
      <h3>${t("common.calendarWindow")}</h3>
      <p class="action">${Number(events.length).toLocaleString(activeLocale())} ${t("common.overlapping")}</p>
      <ul>${renderShortList(data.in_short_i18n, data.in_short)}</ul>
      <div class="sync-rail" style="margin-top:12px">
        <div><b>${t("common.rangeStart")}</b><br><span class="meta">${escapeHtml(niceDate(data.range_start))}</span></div>
        <div><b>${t("common.rangeEnd")}</b><br><span class="meta">${escapeHtml(niceDate(data.range_end))}</span></div>
        <div><b>${t("common.uniqueProducts")}</b><br><span class="meta">${Number(data.unique_products || 0).toLocaleString(activeLocale())}</span></div>
      </div>
    </article>
    <div class="kpis compact-kpis">
      <div class="kpi"><b>${Number(data.event_count || 0).toLocaleString(activeLocale())}</b><span>${t("common.eventsInRange")}</span></div>
      <div class="kpi"><b>${Number(data.exact_count || 0).toLocaleString(activeLocale())}</b><span>${t("common.exactDates")}</span></div>
      <div class="kpi"><b>${Number(data.events_with_products || 0).toLocaleString(activeLocale())}</b><span>${t("common.withPromoteKits")}</span></div>
      <div class="kpi"><b>${Number(data.unique_products || 0).toLocaleString(activeLocale())}</b><span>${t("common.uniqueSkus")}</span></div>
      <div class="kpi"><b>${escapeHtml(niceDate(data.range_start))} → ${escapeHtml(niceDate(data.range_end))}</b><span>${t("common.inclusiveWindow")}</span></div>
    </div>
    <section class="card" style="margin-top:18px">
      <h4>${t("common.monthWindows")}</h4>
      ${events.length ? `<div class="calendar-windows">
        ${events.map((row) => `<article class="media-tile calendar-tile">
          ${coverHtml(row.image_url, row.name, true, "event")}
          <div class="badge-row">
            <span class="badge ${row.kind === "adaptation" ? "hot" : "on"}">${escapeHtml(labelKind(row.kind || "event"))}</span>
            <span class="badge">${escapeHtml(labelKind(row.attendance_mode || "", "") || row.attendance_mode || row.format || row.type || "")}</span>
            ${row.product_count ? `<span class="badge live">${Number(row.product_count).toLocaleString(activeLocale())} ${t("common.skus")}</span>` : ""}
            ${row.exact_date ? "" : `<span class="badge hot">${escapeHtml(labelKind(row.date_precision || "", "") || row.date_precision || t("common.window"))} ${t("common.window")}</span>`}
            ${verifiedBadge(row.official_source)}
          </div>
          <h5><button type="button" class="linkish" data-open-event="${escapeHtml(row.name)}">${escapeHtml(row.name)}</button></h5>
          <p class="meta">${escapeHtml(dateSpan(row))}${row.location ? ` · ${escapeHtml(row.location)}` : ""}${row.language ? ` · ${escapeHtml(row.language)}` : ""}</p>
          ${row.promo_start ? `<p class="meta">${t("common.promote")} ${escapeHtml(niceDate(row.promo_start))} → ${escapeHtml(niceDate(row.promo_end))}</p>` : ""}
          <p>${escapeHtml(row.related || labelStatus(row.confirmation) || "")}</p>
          ${row.hero ? `<p class="meta">${t("common.hero")}: <button type="button" class="linkish" data-open-product="${escapeHtml(row.hero)}">${escapeHtml(row.hero)}</button></p>` : `<p class="meta">${t("common.noMappedProducts")}</p>`}
          ${(row.top_hashtags || []).length ? `<div class="chip-row">${row.top_hashtags.map((tag) => `<span class="hashtag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
          ${(row.products || []).length ? `<div class="social-card-list">${row.products.slice(0, 10).map(renderSocialCard).join("")}</div>` : ""}
          <p class="meta">
            <button type="button" class="linkish" data-open-crosssell="${escapeHtml(row.name)}">${t("crosssell.submit")}</button>
          </p>
        </article>`).join("")}
      </div>` : `<p class="meta">${t("common.noOverlap")}</p>`}
    </section>
    ${(data.products || []).length ? `<section class="card" style="margin-top:18px">
      <h4>${t("common.allPromoteInRange")}</h4>
      <div class="social-card-list range-social">
        ${data.products.slice(0, 36).map(renderSocialCard).join("")}
      </div>
    </section>` : ""}
    ${renderContentMarketing(data.content_marketing)}
  `;
  const root = $("#calendar-brief");
  $$("[data-open-product]", root).forEach((btn) => btn.addEventListener("click", () => {
    $("#query").value = btn.dataset.openProduct;
    showPage("lookup");
    lookup(btn.dataset.openProduct);
  }));
  $$("[data-open-event]", root).forEach((btn) => btn.addEventListener("click", () => {
    $("#event-query").value = btn.dataset.openEvent;
    showPage("event");
    lookupEvent(btn.dataset.openEvent);
  }));
  $$("[data-open-crosssell]", root).forEach((btn) => btn.addEventListener("click", () => {
    $("#crosssell-query").value = btn.dataset.openCrosssell;
    showPage("crosssell");
    lookupCrossSell(btn.dataset.openCrosssell);
  }));
}

async function lookupCalendarRange() {
  const status = $("#calendar-status");
  status.hidden = false;
  status.textContent = t("status.calendar");
  const params = new URLSearchParams({
    start_year: $("#cal-start-year").value,
    start_month: $("#cal-start-month").value,
    end_year: $("#cal-end-year").value,
    end_month: $("#cal-end-month").value,
    kind: $("#cal-kind").value || "",
    precision: $("#cal-precision")?.value || "dated",
    limit: "80",
  });
  try {
    const data = await getJSON(`/api/calendar-range?${params}`);
    status.hidden = true;
    renderCalendarBrief(data);
  } catch (err) {
    status.textContent = err.message;
    $("#calendar-brief").hidden = true;
  }
}

async function loadFeatured() {
  const data = await getJSON("/api/products?limit=60");
  const select = $("#featured");
  for (const row of data.results) {
    const opt = document.createElement("option");
    opt.value = row.canonical_title;
    opt.textContent = row.canonical_title;
    select.append(opt);
  }
}

async function loadFeaturedEvents() {
  const select = $("#featured-event");
  if (select.dataset.ready) return;
  const data = await getJSON("/api/events?limit=50");
  for (const row of uniqueEventResults(data.results)) {
    const opt = document.createElement("option");
    opt.value = row.name;
    opt.textContent = `${row.name} · ${niceDate(row.start)}`;
    select.append(opt);
  }
  select.dataset.ready = "1";
}

function eventFilterQuery() {
  const params = new URLSearchParams({ limit: "80" });
  if ($("#event-year").value) params.set("year", $("#event-year").value);
  if ($("#event-kind").value) params.set("kind", $("#event-kind").value);
  if ($("#event-mode").value) params.set("mode", $("#event-mode").value);
  return params;
}

async function browseEvents() {
  const root = $("#event-results");
  const status = $("#event-status");
  status.hidden = false;
  status.textContent = t("status.browse");
  try {
    const data = await getJSON(`/api/events?${eventFilterQuery()}`);
    root.hidden = false;
    root.innerHTML = uniqueEventResults(data.results).map((row) => `<article class="media-tile">
      ${coverHtml(row.image_url, row.name, true, "event")}
      <div class="badge-row">
        <span class="badge ${row.kind === "adaptation" ? "hot" : "on"}">${escapeHtml(labelKind(row.kind))}</span>
        <span class="badge">${escapeHtml(labelKind(row.attendance_mode || "", "") || row.attendance_mode || row.format || row.type || "")}</span>
        ${row.exact_date ? "" : `<span class="badge hot">${t("common.window")}</span>`}
      </div>
      <h5><button type="button" class="linkish" data-browse-event="${escapeHtml(row.name)}">${escapeHtml(row.name)}</button></h5>
      <p class="meta">${escapeHtml(dateSpan(row))}</p>
      <p>${escapeHtml(row.location || row.country || row.related || "")}${row.language ? ` · ${escapeHtml(row.language)}` : ""}</p>
    </article>`).join("") || `<p class="meta">${t("common.noFilterRows")}</p>`;
    $$("[data-browse-event]", root).forEach((btn) => btn.addEventListener("click", () => {
      $("#event-query").value = btn.dataset.browseEvent;
      lookupEvent(btn.dataset.browseEvent);
    }));
    status.hidden = true;
  } catch (err) {
    status.textContent = err.message;
  }
}

function bindSuggest(inputSel, boxSel, endpoint, onPick) {
  let timer = 0;
  let index = -1;
  let items = [];
  const input = $(inputSel);
  const box = $(boxSel);
  function paint() {
    box.innerHTML = items.map((row, i) => {
      const label = row.canonical_title || row.name;
      const extra = (row.platforms || [row.type, niceDate(row.start)]).filter(Boolean).slice(0, 3).join(" · ");
      const thumb = row.image_url
        ? `<img class="suggest-thumb" src="${escapeHtml(row.image_url)}" alt="" loading="lazy" />`
        : `<span class="suggest-thumb suggest-thumb--empty"></span>`;
      return `<li role="option" data-title="${escapeHtml(label)}" class="${i === index ? "is-on" : ""}">${thumb}<span class="suggest-copy">${escapeHtml(label)} <span class="meta">${escapeHtml(extra)}</span></span></li>`;
    }).join("");
    box.hidden = !items.length;
    input.setAttribute("aria-expanded", items.length ? "true" : "false");
  }
  input.addEventListener("input", (ev) => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      index = -1;
      const q = ev.target.value.trim();
      if (!q) { items = []; paint(); return; }
      const data = await getJSON(`${endpoint}?q=${encodeURIComponent(q)}&limit=12`);
      const rows = data.results || [];
      items = endpoint.includes("/api/events") ? uniqueEventResults(rows) : rows;
      paint();
    }, 160);
  });
  input.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown" && items.length) { ev.preventDefault(); index = Math.min(items.length - 1, index + 1); paint(); }
    else if (ev.key === "ArrowUp" && items.length) { ev.preventDefault(); index = Math.max(0, index - 1); paint(); }
    else if (ev.key === "Enter" && index >= 0 && items[index]) {
      ev.preventDefault();
      const label = items[index].canonical_title || items[index].name;
      input.value = label;
      box.hidden = true;
      onPick(label);
    } else if (ev.key === "Escape") box.hidden = true;
  });
  box.addEventListener("click", (ev) => {
    const li = ev.target.closest("li");
    if (!li) return;
    input.value = li.dataset.title;
    box.hidden = true;
    onPick(li.dataset.title);
  });
}

function barRow(label, value, max) {
  const pct = max ? Math.max(4, Math.round((value / max) * 100)) : 0;
  return `<div class="bar"><span>${escapeHtml(label)}</span><i style="width:${pct}%"></i><span>${Number(value).toLocaleString(activeLocale())}</span></div>`;
}

function provenanceLine(source, entryDate, lastChecked) {
  const parts = [`${t("common.source")}: ${escapeHtml(source)}`];
  if (entryDate) parts.push(`${t("common.entered")} ${escapeHtml(niceDate(entryDate))}`);
  if (lastChecked) parts.push(`${t("common.checked")} ${escapeHtml(niceDate(lastChecked))}`);
  return parts.join(" · ");
}

let archivePayload = null;

async function loadArchive(force = false) {
  const root = $("#archive-board");
  const status = $("#archive-status");
  if (!root || !status) return;
  if (archivePayload && !force) {
    renderArchive(archivePayload);
    return;
  }
  status.hidden = false;
  status.textContent = t("status.archive");
  try {
    archivePayload = await getJSON("/api/archive");
    status.hidden = true;
    root.hidden = false;
    renderArchive(archivePayload);
  } catch (err) {
    status.textContent = err.message;
    root.hidden = true;
  }
}

function renderArchive(data) {
  const root = $("#archive-board");
  const year = $("#archive-year")?.value || "";
  const needle = ($("#archive-query")?.value || "").trim().toLowerCase();
  const years = (data.years || []).filter((block) => !year || block.year === year);
  const filteredYears = years.map((block) => {
    const events = uniqueEventResults(block.events || []).filter((row) => {
      if (!needle) return true;
      const blob = `${row.name || ""} ${row.location || ""} ${row.type || ""} ${row.category || ""}`.toLowerCase();
      return blob.includes(needle);
    });
    return { ...block, events, count: events.length };
  }).filter((block) => block.events.length);
  const total = filteredYears.reduce((sum, block) => sum + block.count, 0);
  root.hidden = false;
  root.innerHTML = `
    <p class="meta">${tf("archive.count", { n: total })} · 2022–2026</p>
    ${filteredYears.length ? filteredYears.map((block) => `
      <section class="card archive-year">
        <h3>${escapeHtml(block.year)}</h3>
        <p class="meta">${tf("archive.yearCount", { n: block.count, year: block.year })}</p>
        <div class="table-scroll">
          <table>
            <thead><tr>
              <th>${t("archive.event")}</th>
              <th>${t("archive.runtime")}</th>
              <th>${t("archive.location")}</th>
              <th>${t("archive.type")}</th>
            </tr></thead>
            <tbody>
              ${block.events.map((row) => `<tr>
                <td><button type="button" class="linkish" data-open-event="${escapeHtml(row.name)}">${escapeHtml(row.name)}</button></td>
                <td>${escapeHtml(row.date_label || dateSpan({ start: row.runtime_start, end: row.runtime_end, date_label: row.date_label }))}</td>
                <td class="meta">${escapeHtml(row.location || t("traffic.worldwide"))}</td>
                <td class="meta">${escapeHtml(labelKind(row.type || row.category || "", "") || row.type || "—")}${row.attendance_mode ? ` · ${escapeHtml(labelKind(row.attendance_mode, "") || row.attendance_mode)}` : ""}</td>
              </tr>`).join("")}
            </tbody>
          </table>
        </div>
      </section>
    `).join("") : `<p class="meta">${t("archive.empty")}</p>`}
  `;
  root.querySelectorAll("[data-open-event]").forEach((btn) => btn.addEventListener("click", () => {
    $("#event-query").value = btn.dataset.openEvent;
    showPage("event");
    lookupEvent(btn.dataset.openEvent);
  }));
}

async function loadDashboard(force = false) {
  const root = $("#dashboard");
  const status = $("#dash-status");
  if (root.dataset.ready && !force) return;
  status.hidden = false;
  status.textContent = t("status.dashboard");
  try {
    const d = await getJSON("/api/dashboard");
    const maxPlat = Math.max(...d.platforms.map(([, n]) => n), 1);
    const maxType = Math.max(...d.product_types.map(([, n]) => n), 1);
    const maxFam = Math.max(...d.promo_families.map(([, n]) => n), 1);
    const maxFormat = Math.max(...(d.adaptation_formats || []).map(([, n]) => n), 1);
    const maxMode = Math.max(...(d.event_modes || []).map(([, n]) => n), 1);
    const maxEventYear = Math.max(...(d.event_years || []).map(([, n]) => n), 1);
    const maxMediaYear = Math.max(...(d.adaptation_years || []).map(([, n]) => n), 1);
    $("#dash-asof").textContent = `${t("dash.checked")} ${d.kpis.last_checked || d.as_of} · ${d.kpis.horizon}${d.kpis.rag_documents ? ` · ${Number(d.kpis.rag_documents).toLocaleString(activeLocale())} ${t("dash.ragDocs")}` : ""}`;
    status.hidden = true;
    root.hidden = false;
    root.dataset.ready = "1";
    const o = d.orders || {};
    const ok = o.kpis || {};
    const years = o.years || [];
    const ordersBlock = ok.sku_count ? `
      <section class="card gmv-board">
        <h3>${t("dash.ordersHeading")}</h3>
        <p class="meta">${t("dash.ordersCaption")}</p>
        <div class="kpis gmv-kpis">
          <div class="kpi"><b>${money(ok.lifetime_gmv)}</b><span>${t("dash.kpis.lifetimeGmv")}</span></div>
          <div class="kpi"><b>${money(ok.best_week_gmv)}</b><span>${t("dash.kpis.bestWeekGmv")}</span></div>
          <div class="kpi highlight"><b>${ok.matched_best_week_pct}%</b><span>${t("dash.kpis.hitBestPct")}</span></div>
          <div class="kpi highlight"><b>${ok.pct_2026_best_week_hit_event}%</b><span>${t("dash.kpis.hit2026")}</span></div>
          <div class="kpi"><b>${Number(ok.matched_skus).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.matchedSkus")}</span></div>
          <div class="kpi"><b>${Number(ok.events_with_peak_gmv).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.eventHits")}</span></div>
          <div class="kpi"><b>${money(ok.release_window_week_gmv)}</b><span>${t("dash.kpis.releaseGmv")}</span></div>
          <div class="kpi"><b>${money(ok.unique_linked_week_gmv)}</b><span>${t("dash.kpis.uniqueWeekGmv")}</span></div>
          <div class="kpi highlight"><b>${ok.top5_product_share || 0}%</b><span>${t("dash.kpis.top5ProductShare")}</span></div>
          <div class="kpi highlight"><b>${ok.top5_event_share || 0}%</b><span>${t("dash.kpis.top5EventShare")}</span></div>
          <div class="kpi"><b class="kpi-name">${escapeHtml(ok.top_product || "—")}</b><span>${t("dash.kpis.topProduct")} · ${money(ok.top_product_gmv)}</span></div>
          <div class="kpi"><b class="kpi-name">${escapeHtml(ok.top_event || "—")}</b><span>${t("dash.kpis.topEvent")} · ${money(ok.top_event_gmv)}</span></div>
        </div>
        <section class="leader-block">
          <h4>${t("dash.periodLeaders")}</h4>
          <p class="meta">${t("dash.periodLeadersHint")}</p>
          <div class="grid-2">
            <div>
              <h5>${t("dash.top5Products")}</h5>
              ${leaderProductTable(o.period_top_products, "lifetime_gmv")}
            </div>
            <div>
              <h5>${t("dash.top5Events")}</h5>
              ${leaderEventTable(o.period_top_events)}
            </div>
          </div>
          <h5>${t("dash.productEventYears")}</h5>
          <p class="meta">${t("dash.productEventYearsHint")}</p>
          ${productYearEventMatrix(o.period_top_products)}
        </section>
        <div class="dash-readout">
          <h4>${t("dash.readoutTitle")}</h4>
          <ul>
            <li>${t("dash.readout1")}</li>
            <li>${t("dash.readout2")}</li>
            <li>${t("dash.readout3")}</li>
          </ul>
        </div>
        <div class="grid-2">
          <div class="chart-wrap"><canvas id="gmv-year-chart"></canvas><p class="meta">${t("dash.yearChart")}</p></div>
          <div class="chart-wrap"><canvas id="gmv-hit-chart"></canvas><p class="meta">${t("dash.yearHitChart")}</p></div>
        </div>
        <section class="leader-block">
          <h4>${t("dash.yearLeaders")}</h4>
          <p class="meta">${t("dash.yearLeadersHint")}</p>
          <div class="year-leader-stack">
            ${years.map((row) => {
              const yk = row.kpis || {};
              return `<article class="card year-leaders">
                <h4>${escapeHtml(row.year)}</h4>
                <div class="kpis gmv-kpis">
                  <div class="kpi"><b>${money(yk.observed_week_gmv)}</b><span>${t("dash.kpis.yearObservedGmv")}</span></div>
                  <div class="kpi"><b>${money(yk.event_week_gmv)}</b><span>${t("dash.kpis.yearEventGmv")}</span></div>
                  <div class="kpi"><b>${Number(yk.sku_titles || 0).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.yearTitles")}</span></div>
                  <div class="kpi"><b>${yk.top5_product_share || 0}%</b><span>${t("dash.kpis.yearTop5ProductShare")}</span></div>
                  <div class="kpi highlight"><b class="kpi-name">${escapeHtml(yk.top_product || "—")}</b><span>${t("dash.kpis.topProduct")} · ${money(yk.top_product_gmv)}</span></div>
                  <div class="kpi highlight"><b class="kpi-name">${escapeHtml(yk.top_event || "—")}</b><span>${t("dash.kpis.topEvent")} · ${money(yk.top_event_gmv)}</span></div>
                </div>
                <div class="grid-2">
                  <div>
                    <h5>${t("dash.top5Products")}</h5>
                    ${leaderProductTable(row.top_products, "year_gmv")}
                  </div>
                  <div>
                    <h5>${t("dash.top5Events")}</h5>
                    ${leaderEventTable(row.top_events)}
                  </div>
                </div>
              </article>`;
            }).join("")}
          </div>
        </section>
      </section>
      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <h4>${t("dash.topEvents")}</h4>
          <table><thead><tr><th>${t("dash.event")}</th><th>${t("dash.runtime")}</th><th>${t("dash.skus")}</th><th>${t("dash.weekGmv")}</th></tr></thead><tbody>
            ${(withoutQuarterTimeframes(o.top_events)).map((row) => `<tr>
              <td>${escapeHtml(row.event)}<div class="meta">${escapeHtml(row.event_type || "")}</div></td>
              <td class="meta">${escapeHtml(niceDate(row.runtime_start))} – ${escapeHtml(niceDate(row.runtime_end))}</td>
              <td>${row.matched_skus}</td>
              <td>${money(row.week_gmv)}</td>
            </tr>`).join("")}
          </tbody></table>
        </section>
        <section class="card">
          <h4>${t("dash.eventTypes")}</h4>
          <div class="bars">${(o.event_types || []).map((row) => barRow(row.event_type, row.week_gmv, Math.max(...(o.event_types || []).map((item) => item.week_gmv), 1))).join("")}</div>
        </section>
      </div>
      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <h4>${t("dash.topOrders")}</h4>
          <table><thead><tr><th>${t("dash.titleCol")}</th><th>${t("dash.lifetimeCol")}</th><th>${t("dash.bestWeek")}</th><th>${t("dash.overlap")}</th></tr></thead><tbody>
            ${(o.top_skus || []).map((row) => `<tr>
              <td>${escapeHtml(row.canonical_title)}</td>
              <td>${money(row.lifetime_gmv)}</td>
              <td class="meta">${escapeHtml(niceDate(row.best_week_start))} · ${money(row.best_week_gmv)}</td>
              <td class="meta">${escapeHtml((row.events && row.events.filter((name) => !isQuarterTimeframe(name)).length) ? row.events.filter((name) => !isQuarterTimeframe(name)).join("; ") : (row.gap || t("dash.none")))}</td>
            </tr>`).join("")}
          </tbody></table>
        </section>
        <section class="card">
          <h4>${t("dash.missed")}</h4>
          <table><thead><tr><th>${t("dash.titleCol")}</th><th>${t("dash.lifetimeCol")}</th><th>${t("dash.bestWeek")}</th><th>${t("dash.gap")}</th></tr></thead><tbody>
            ${(o.missed_skus || []).map((row) => `<tr>
              <td>${escapeHtml(row.canonical_title)}</td>
              <td>${money(row.lifetime_gmv)}</td>
              <td class="meta">${escapeHtml(niceDate(row.best_week_start))} · ${money(row.best_week_gmv)}</td>
              <td class="meta">${escapeHtml(row.gap || "")}</td>
            </tr>`).join("")}
          </tbody></table>
        </section>
      </div>
    ` : `<p class="meta">${t("dash.ordersEmpty")}</p>`;
    root.innerHTML = `
      ${ordersBlock}
      <div class="kpis">
        <div class="kpi"><b>${Number(d.kpis.catalog_skus).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.catalogSkus")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.unique_titles).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.uniqueTitles")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.announced_games || 0).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.announcedGames")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.correlated_events || 0).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.correlatedEvents")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.announced_tba || 0).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.announcedTba")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.events).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.events")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.adaptations).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.adaptations")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.promotion_plans).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.promotionPlans")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.active_windows_today).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.liveToday")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.trend_priorities).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.trendPriorities")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.daily_changes || 0).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.dailyChanges")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.rag_documents || 0).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.ragDocuments")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.artwork_products || 0).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.artworkProducts")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.artwork_events || 0).toLocaleString(activeLocale())}</b><span>${t("dash.kpis.artworkEvents")}</span></div>
      </div>
      <div class="grid-2">
        <section class="card">
          <h4>${t("dash.merchandiseToday")}</h4>
          <table><thead><tr><th>${t("dash.rank")}</th><th>${t("dash.titleCol")}</th><th>${t("dash.why")}</th></tr></thead><tbody>
            ${(d.priorities || []).filter((row) => !isQuarterTimeframe(row.canonical_title)).map((row) => `<tr>
              <td>${row.rank}</td>
              <td><button type="button" class="linkish" data-open="${escapeHtml(row.canonical_title)}">${escapeHtml(row.canonical_title)}</button></td>
              <td class="meta">${escapeHtml((row.sources || []).join(", "))}<br>${escapeHtml((row.reasons || [])[0] || "")}</td>
            </tr>`).join("")}
          </tbody></table>
        </section>
        <section class="card">
          <h4>${t("dash.liveWindows")}</h4>
          <p class="meta">${t("dash.liveWindowsHint")}</p>
          <div class="timeline">
            ${uniqueEventResults(d.live_windows || []).map((row) => `<article>
              <button type="button" class="linkish" data-open-event="${escapeHtml(row.event)}">${escapeHtml(row.event)}</button>
              <div class="badge-row" style="margin:6px 0">
                ${dateConfidenceBadge(row)}
                <span class="badge ${row.exact_date ? "" : "hot"}">${escapeHtml(dateSpan(row))}${row.exact_date ? "" : ` · ${t("common.window")}`}</span>
                ${verifiedBadge(row.official_source)}
              </div>
              <p class="meta">${escapeHtml(row.family)} · ${escapeHtml(row.title)}</p>
              ${row.promo_start ? `<p class="meta">${t("common.promote")} ${escapeHtml(niceDate(row.promo_start))} → ${escapeHtml(niceDate(row.promo_end))}</p>` : ""}
            </article>`).join("") || `<p class="meta">${t("dash.noLive")}</p>`}
          </div>
        </section>
      </div>
      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <h4>${t("dash.audit")}</h4>
          <table><thead><tr><th>${t("dash.change")}</th><th>${t("dash.titleCol")}</th><th>${t("dash.detail")}</th></tr></thead><tbody>
            ${(d.recent_changes || []).map((row) => `<tr>
              <td><span class="badge ${row.change_type === "delayed" || row.change_type === "cancelled" ? "hot" : "on"}">${escapeHtml(labelChange(row.change_type || ""))}</span></td>
              <td>${escapeHtml(row.title || "")}</td>
              <td class="meta">${escapeHtml(row.detail || `${row.before || ""} → ${row.after || ""}`)}</td>
            </tr>`).join("") || `<tr><td colspan="3" class="meta">${t("dash.noAudit")}</td></tr>`}
          </tbody></table>
        </section>
        <section class="card">
          <h4>${t("dash.ragIndex")}</h4>
          <p class="meta">${escapeHtml((d.rag && d.rag.as_of) || d.as_of)} · ${Number((d.rag && d.rag.document_count) || d.kpis.rag_documents || 0).toLocaleString(activeLocale())} ${t("dash.documents")} · ${t("dash.trained")} ${escapeHtml(boolLabel(Boolean(d.rag && d.rag.trained)))}</p>
          <div class="bars">${Object.entries((d.rag && d.rag.kinds) || {}).map(([label, n]) => barRow(label, n, Math.max(...Object.values((d.rag && d.rag.kinds) || {x:1}), 1))).join("") || `<p class="meta">${t("dash.ragEmpty")}</p>`}</div>
        </section>
      </div>
      <div class="grid-3" style="margin-top:18px">
        <section class="card"><h4>${t("dash.platformMix")}</h4><div class="bars">${d.platforms.map(([label, n]) => barRow(label, n, maxPlat)).join("")}</div></section>
        <section class="card"><h4>${t("dash.productTypes")}</h4><div class="bars">${d.product_types.map(([label, n]) => barRow(label, n, maxType)).join("")}</div></section>
        <section class="card"><h4>${t("dash.promoFamilies")}</h4><div class="bars">${d.promo_families.map(([label, n]) => barRow(label, n, maxFam)).join("")}</div></section>
      </div>
      <div class="grid-2" style="margin-top:18px">
        <section class="card"><h4>${t("dash.formats")}</h4><div class="bars">${(d.adaptation_formats || []).map(([label, n]) => barRow(label, n, maxFormat)).join("")}</div></section>
        <section class="card"><h4>${t("dash.modes")}</h4><div class="bars">${(d.event_modes || []).map(([label, n]) => barRow(label, n, maxMode)).join("")}</div></section>
      </div>
      <div class="grid-2" style="margin-top:18px">
        <section class="card"><h4>${t("dash.eventsByYear")}</h4><div class="bars">${(d.event_years || []).map(([label, n]) => barRow(label, n, maxEventYear)).join("")}</div></section>
        <section class="card"><h4>${t("dash.mediaByYear")}</h4><div class="bars">${(d.adaptation_years || []).map(([label, n]) => barRow(label, n, maxMediaYear)).join("")}</div></section>
      </div>
      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <h4>${t("dash.next60")}</h4>
          <div class="timeline">
            ${uniqueEventResults(d.timeline || []).map((row) => `<article>
              <b>${escapeHtml(row.name)}</b>
              <p class="meta">${escapeHtml(niceDate(row.start))} · ${escapeHtml(row.related)}</p>
            </article>`).join("")}
          </div>
        </section>
        <section class="card">
          <h4>${t("dash.trendsSignals")}</h4>
          <table><thead><tr><th>${t("dash.signal")}</th><th>${t("dash.detail")}</th></tr></thead><tbody>
            ${(d.google_trends || []).slice(0, 6).map((row) => `<tr><td>${escapeHtml(row.geo)}</td><td>${escapeHtml(row.title)} · ${escapeHtml(row.traffic_label || "")}</td></tr>`).join("")}
            ${(d.wikipedia || []).slice(0, 5).map((row) => `<tr><td>${t("dash.wiki")}</td><td>${escapeHtml(row.article)} · ${row.spike_ratio}×</td></tr>`).join("")}
          </tbody></table>
        </section>
      </div>
      <section class="card" style="margin-top:18px">
        <h4>${t("dash.announced")}</h4>
        <div class="media-grid">
          ${(d.upcoming_announced || []).filter((row) => !isQuarterTimeframe(row.canonical_title)).map((row) => `<article class="media-tile">
            ${coverHtml(row.image_url, row.canonical_title, true)}
            <div class="badge-row">
              <span class="badge hot">${escapeHtml(labelStatus(row.confirmation || "announced"))}</span>
              ${row.date_precision && row.date_precision !== "day" ? `<span class="badge">${escapeHtml(labelKind(row.date_precision))} ${t("common.window")}</span>` : ""}
            </div>
            <h5><button type="button" class="linkish" data-open="${escapeHtml(row.canonical_title)}">${escapeHtml(row.canonical_title)}</button></h5>
            <p class="meta">${escapeHtml(row.release_label || niceDate(row.release_date))} · ${(row.platforms || []).slice(0, 2).join(" · ") || t("common.multi")}</p>
          </article>`).join("") || `<p class="meta">${t("dash.noAnnounced")}</p>`}
        </div>
      </section>
      <section class="card" style="margin-top:18px">
        <h4>${t("dash.correlated")}</h4>
        <div class="timeline">
          ${uniqueEventResults(d.correlated_event_sample || []).map((row) => `<article>
            <button type="button" class="linkish" data-open-event="${escapeHtml(row.name)}">${escapeHtml(row.name)}</button>
            <p class="meta">${escapeHtml(niceDate(row.start))} · ${escapeHtml(row.correlated_announced || row.related)}</p>
          </article>`).join("") || `<p class="meta">${t("dash.noCorrelated")}</p>`}
        </div>
      </section>
      <section class="card" style="margin-top:18px">
        <h4>${t("dash.upcomingMedia")}</h4>
        <div class="media-grid">
          ${uniqueEventResults(d.upcoming_adaptations || []).map((row) => `<article class="media-tile">
            <span class="badge hot">${escapeHtml(row.format || row.type)}</span>
            <h5><button type="button" class="linkish" data-open-event="${escapeHtml(row.name)}">${escapeHtml(row.name)}</button></h5>
            <p class="meta">${escapeHtml(niceDate(row.start))} · ${escapeHtml(labelStatus(row.confirmation || row.status))}</p>
            <p>${escapeHtml(row.related || "")}</p>
          </article>`).join("")}
        </div>
      </section>
    `;
    if (years.length) {
      const labels = years.map((row) => row.year);
      paintChart("gmv-year-chart", {
        type: "bar",
        data: {
          labels,
          datasets: [
            { label: t("dash.kpis.bestWeekGmv"), data: years.map((row) => row.best_week_gmv), backgroundColor: "rgba(90, 200, 250, 0.75)" },
            { label: t("dash.weekGmv"), data: years.map((row) => row.hit_best_week_gmv), backgroundColor: "rgba(255, 99, 164, 0.75)" },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { labels: { color: "#dce4ef" } } },
          scales: {
            x: { ticks: { color: "#9aa8b8" }, grid: { color: "rgba(255,255,255,0.06)" } },
            y: { ticks: { color: "#9aa8b8", callback: (v) => money(v) }, grid: { color: "rgba(255,255,255,0.06)" } },
          },
        },
      });
      paintChart("gmv-hit-chart", {
        type: "bar",
        data: {
          labels,
          datasets: [{ label: t("dash.yearHitChart"), data: years.map((row) => row.hit_pct), backgroundColor: "rgba(90, 200, 250, 0.85)" }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#9aa8b8" }, grid: { color: "rgba(255,255,255,0.06)" } },
            y: { suggestedMax: 30, ticks: { color: "#9aa8b8", callback: (v) => `${v}%` }, grid: { color: "rgba(255,255,255,0.06)" } },
          },
        },
      });
    }
    root.querySelectorAll("[data-open]").forEach((btn) => btn.addEventListener("click", () => {
      $("#query").value = btn.dataset.open;
      showPage("lookup");
      lookup(btn.dataset.open);
    }));
    root.querySelectorAll("[data-open-event]").forEach((btn) => btn.addEventListener("click", () => {
      $("#event-query").value = btn.dataset.openEvent;
      showPage("event");
      lookupEvent(btn.dataset.openEvent);
    }));
  } catch (err) {
    status.textContent = err.message;
  }
}

const chartHandles = {};

function paintChart(id, config) {
  const canvas = document.getElementById(id);
  if (!canvas || typeof Chart === "undefined") return;
  if (chartHandles[id]) chartHandles[id].destroy();
  chartHandles[id] = new Chart(canvas, config);
}

async function loadTrendsBoard(force = false) {
  const root = $("#trends-board");
  const status = $("#trends-status");
  if (root.dataset.ready && !force) return;
  status.hidden = false;
  status.textContent = t("status.trends");
  try {
    const d = await getJSON("/api/trends/analysis");
    $("#trends-asof").textContent = `${t("trends.asOf")} ${d.as_of}`;
    status.hidden = true;
    root.hidden = false;
    root.dataset.ready = "1";
    root.innerHTML = `
      <div class="kpis">
        <div class="kpi"><b>${Number(d.kpis.google_topics).toLocaleString(activeLocale())}</b><span>${t("trends.topics")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.total_google_traffic).toLocaleString(activeLocale())}</b><span>${t("trends.matchedTraffic")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.wikipedia_spikes).toLocaleString(activeLocale())}</b><span>${t("trends.wikiSpikes")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.priority_titles).toLocaleString(activeLocale())}</b><span>${t("trends.priorities")}</span></div>
      </div>
      <div class="grid-2">
        <section class="card chart-card">
          <h4>${t("trends.googleTopics")}</h4>
          <canvas id="chart-google-topics" height="220"></canvas>
        </section>
        <section class="card chart-card">
          <h4>${t("trends.priorityScores")}</h4>
          <canvas id="chart-priority-scores" height="220"></canvas>
        </section>
      </div>
      <section class="card" style="margin-top:18px">
        <h4>${t("trends.matchedDetail")}</h4>
        <div class="priority-art">
          ${(d.priority_scores || []).map((row) => `<article>
            ${coverHtml(row.image_url, row.canonical_title)}
            <div>
              <button type="button" class="linkish" data-open="${escapeHtml(row.canonical_title)}">#${row.rank} ${escapeHtml(row.canonical_title)}</button>
              <p class="meta">${t("common.score")} ${escapeHtml(row.score)} · ${(row.sources || []).join(", ")}</p>
            </div>
          </article>`).join("")}
        </div>
      </section>
      <section class="card" style="margin-top:18px">
        <h4>${t("trends.topTopics")}</h4>
        <table><thead><tr><th>${t("trends.topic")}</th><th>${t("trends.geo")}</th><th>${t("trends.traffic")}</th><th>${t("trends.news")}</th></tr></thead><tbody>
          ${(d.google_top || []).map((row) => `<tr>
            <td>${escapeHtml(row.label)}</td>
            <td>${escapeHtml(row.geo)}</td>
            <td>${Number(row.traffic).toLocaleString(activeLocale())}</td>
            <td class="meta">${escapeHtml(row.news || "")}</td>
          </tr>`).join("")}
        </tbody></table>
      </section>
    `;
    paintChart("chart-google-topics", {
      type: "bar",
      data: {
        labels: (d.google_top || []).slice(0, 12).map((row) => row.label.slice(0, 28)),
        datasets: [{
          label: t("trends.traffic"),
          data: (d.google_top || []).slice(0, 12).map((row) => row.traffic),
          backgroundColor: "rgba(92, 225, 230, 0.55)",
          borderRadius: 8,
        }],
      },
      options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: "#9aa6c3" } }, y: { ticks: { color: "#9aa6c3" } } } },
    });
    paintChart("chart-priority-scores", {
      type: "bar",
      data: {
        labels: (d.priority_scores || []).slice(0, 12).map((row) => row.canonical_title.slice(0, 22)),
        datasets: [{
          label: t("trends.priorityScore"),
          data: (d.priority_scores || []).slice(0, 12).map((row) => row.score),
          backgroundColor: "rgba(255, 92, 168, 0.55)",
          borderRadius: 8,
        }],
      },
      options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { ticks: { color: "#9aa6c3" } }, y: { ticks: { color: "#9aa6c3" } } } },
    });
    root.querySelectorAll("[data-open]").forEach((btn) => btn.addEventListener("click", () => {
      $("#query").value = btn.dataset.open;
      showPage("lookup");
      lookup(btn.dataset.open);
    }));
  } catch (err) {
    status.textContent = err.message;
  }
}

async function loadTrafficBoard(force = false) {
  const root = $("#traffic-board");
  const status = $("#traffic-status");
  if (root.dataset.ready && !force) return;
  status.hidden = false;
  status.textContent = t("traffic.loading");
  try {
    const d = await getJSON("/api/trends/analysis");
    const placement = d.geo_placement || { tracked_geos: [], placements: {} };
    const selectedGeo = window.FloorI18n?.geo() || "US";
    const geos = [...(placement.tracked_geos || [])]
      .filter((geo) => {
        const row = placement.placements?.[geo] || {};
        return geo === "WW" || geo === selectedGeo || (row.event_count || 0) > 0 || (row.product_count || 0) > 0;
      })
      .sort((left, right) => {
        if (left === selectedGeo) return -1;
        if (right === selectedGeo) return 1;
        if (left === "WW") return -1;
        if (right === "WW") return 1;
        const leftN = placement.placements?.[left]?.event_count || 0;
        const rightN = placement.placements?.[right]?.event_count || 0;
        return rightN - leftN;
      });
    const displayNames = typeof Intl.DisplayNames === "function"
      ? new Intl.DisplayNames([activeLocale()], { type: "region" })
      : null;
    const geoLabel = (geo, row) => displayNames?.of(geo) || row.country || geo;
    status.hidden = true;
    root.hidden = false;
    root.dataset.ready = "1";
    root.innerHTML = `
      <div class="kpis">
        <div class="kpi"><b>${d.kpis.geographies}</b><span>${t("traffic.geographies")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.total_google_traffic).toLocaleString(activeLocale())}</b><span>${t("traffic.googleTraffic")}</span></div>
        <div class="kpi"><b>${Number(d.kpis.total_wiki_views).toLocaleString(activeLocale())}</b><span>${t("traffic.wikiViews")}</span></div>
        <div class="kpi"><b>${d.kpis.wikipedia_spikes}</b><span>${t("traffic.spikes")}</span></div>
        <div class="kpi"><b>${d.kpis.placement_products || 0}</b><span>${t("traffic.placementProducts")}</span></div>
        <div class="kpi"><b>${d.kpis.placement_events || 0}</b><span>${t("traffic.placementEvents")}</span></div>
      </div>
      ${d.has_google ? "" : `<section class="card empty-signal">
        <p class="meta">${t("traffic.noGoogle")}</p>
      </section>`}
      <div class="grid-2">
        ${d.has_google ? `<section class="card chart-card">
          <h4>${t("traffic.googleByGeo")}</h4>
          <canvas id="chart-geo" height="240"></canvas>
        </section>` : ""}
        <section class="card chart-card">
          <h4>${t("traffic.signalMix")}</h4>
          <canvas id="chart-mix" height="240"></canvas>
        </section>
      </div>
      <div class="grid-2" style="margin-top:18px">
        <section class="card chart-card">
          <h4>${t("traffic.wikiSpikes")}</h4>
          <canvas id="chart-wiki" height="240"></canvas>
        </section>
        <section class="card">
          <h4>${t("traffic.spikeDetail")}</h4>
          <table><thead><tr><th>${t("traffic.article")}</th><th>${t("traffic.views")}</th><th>${t("traffic.spike")}</th></tr></thead><tbody>
            ${(d.wikipedia_top || []).map((row) => `<tr>
              <td>${escapeHtml(row.label)}</td>
              <td>${Number(row.views).toLocaleString(activeLocale())}</td>
              <td>${escapeHtml(row.spike_ratio)}×</td>
            </tr>`).join("")}
          </tbody></table>
        </section>
      </div>
      <section class="card" style="margin-top:18px">
        <h4>${t("traffic.countryPlacement")}</h4>
        <p class="meta">${t("traffic.horizon")}: ${niceDate(placement.as_of)} → ${niceDate(placement.horizon_end)}</p>
        <div class="geo-placement-grid">
          ${geos.map((geo) => {
            const row = placement.placements?.[geo] || {};
            return `<article class="geo-card${geo === selectedGeo ? " is-selected" : ""}${geo === "WW" ? " is-worldwide" : ""}">
              <h5>${escapeHtml(geo === "WW" ? t("traffic.worldwide") : `${geoLabel(geo, row)} · ${geo}`)}</h5>
              <p class="meta">${escapeHtml(row.language || "")} · ${row.product_count || 0} ${t("traffic.products")} · ${row.event_count || 0} ${t("traffic.events")}${geo !== "WW" ? ` · ${t("traffic.localHost")}` : ""}</p>
              <b>${t("traffic.products")}</b>
              <ul>
                ${(row.products || []).slice(0, 8).map((product) => `<li>
                  <button type="button" class="linkish" data-open="${escapeHtml(product.canonical_title)}">${escapeHtml(product.canonical_title)}</button>
                  <span class="meta">${product.event && !isQuarterTimeframe(product.event) ? ` · ${escapeHtml(product.event)}` : ""}</span>
                </li>`).join("") || `<li class="meta">${t("traffic.noProducts")}</li>`}
              </ul>
              <b>${t("traffic.events")}</b>
              <ul>
                ${uniqueEventResults(row.events || []).slice(0, 8).map((event) => `<li>
                  <button type="button" class="linkish" data-open-event="${escapeHtml(event.name)}">${escapeHtml(event.name)}</button>
                  <span class="meta"> · ${niceDate(event.start)} · ${escapeHtml(event.location || event.country || event.scope || "")}</span>
                </li>`).join("") || `<li class="meta">${t("traffic.noEvents")}</li>`}
              </ul>
            </article>`;
          }).join("")}
        </div>
      </section>
    `;
    if (d.has_google) {
      paintChart("chart-geo", {
        type: "doughnut",
        data: {
          labels: (d.google_by_geo || []).map(([geo]) => geo),
          datasets: [{
            data: (d.google_by_geo || []).map(([, n]) => n),
            backgroundColor: ["#5ce1e6", "#ff5ca8", "#ffc14a", "#7dffb0", "#8aa4ff", "#f4f7ff", "#9aa6c3"],
          }],
        },
        options: { plugins: { legend: { labels: { color: "#9aa6c3" } } } },
      });
    }
    paintChart("chart-mix", {
      type: "pie",
      data: {
        labels: (d.source_mix || []).map(([label]) => label),
        datasets: [{
          data: (d.source_mix || []).map(([, n]) => n),
          backgroundColor: ["#5ce1e6", "#ff5ca8", "#ffc14a"],
        }],
      },
      options: { plugins: { legend: { labels: { color: "#9aa6c3" } } } },
    });
    paintChart("chart-wiki", {
      type: "bar",
      data: {
        labels: (d.wikipedia_top || []).slice(0, 10).map((row) => row.label.slice(0, 24)),
        datasets: [{
          label: t("traffic.views"),
          data: (d.wikipedia_top || []).slice(0, 10).map((row) => row.views),
          backgroundColor: "rgba(255, 193, 74, 0.6)",
          borderRadius: 8,
        }],
      },
      options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: "#9aa6c3" } }, y: { ticks: { color: "#9aa6c3" } } } },
    });
    root.querySelectorAll("[data-open]").forEach((btn) => btn.addEventListener("click", () => {
      $("#query").value = btn.dataset.open;
      showPage("lookup");
      lookup(btn.dataset.open);
    }));
    root.querySelectorAll("[data-open-event]").forEach((btn) => btn.addEventListener("click", () => {
      $("#event-query").value = btn.dataset.openEvent;
      showPage("event");
      lookupEvent(btn.dataset.openEvent);
    }));
  } catch (err) {
    status.textContent = err.message;
  }
}

function boot() {
  document.title = `${t("shell.title")} — ${t("shell.kicker")}`;
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => showPage(tab.dataset.page)));
  $("#nav-toggle").addEventListener("click", () => $("#tabs").classList.toggle("is-open"));
  $("#featured").addEventListener("change", (ev) => { if (ev.target.value) { $("#query").value = ev.target.value; lookup(ev.target.value); } });
  $("#featured-event").addEventListener("change", (ev) => { if (ev.target.value) { $("#event-query").value = ev.target.value; lookupEvent(ev.target.value); } });
  $("#featured-crosssell")?.addEventListener("change", (ev) => {
    if (ev.target.value) {
      $("#crosssell-query").value = ev.target.value;
      lookupCrossSell(ev.target.value);
    }
  });
  bindSuggest("#query", "#suggest", "/api/products", lookup);
  bindSuggest("#event-query", "#event-suggest", "/api/events", lookupEvent);
  bindSuggest("#crosssell-query", "#crosssell-suggest", "/api/events", lookupCrossSell);
  document.addEventListener("click", (ev) => {
    if (!ev.target.closest(".grow")) {
      $("#suggest").hidden = true;
      $("#event-suggest").hidden = true;
      $("#crosssell-suggest") && ($("#crosssell-suggest").hidden = true);
    }
  });
  $("#lookup-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const q = $("#query").value.trim() || $("#featured").value;
    if (q) lookup(q);
  });
  $("#event-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const q = $("#event-query").value.trim() || $("#featured-event").value;
    if (q) lookupEvent(q);
  });
  $("#crosssell-form")?.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const q = $("#crosssell-query").value.trim() || $("#featured-crosssell").value;
    if (q) lookupCrossSell(q);
  });
  $("#calendar-form")?.addEventListener("submit", (ev) => {
    ev.preventDefault();
    lookupCalendarRange();
  });
  $("#archive-year")?.addEventListener("change", () => {
    if (archivePayload) renderArchive(archivePayload);
    else loadArchive(true);
  });
  $("#archive-query")?.addEventListener("input", () => {
    if (archivePayload) renderArchive(archivePayload);
  });
  $("#archive-form")?.addEventListener("submit", (ev) => ev.preventDefault());
  $$(".cal-preset").forEach((btn) => btn.addEventListener("click", () => {
    $("#cal-start-month").value = btn.dataset.sm;
    $("#cal-start-year").value = btn.dataset.sy;
    $("#cal-end-month").value = btn.dataset.em;
    $("#cal-end-year").value = btn.dataset.ey;
    showPage("calendar");
    lookupCalendarRange();
  }));
  $("#browse-events").addEventListener("click", browseEvents);
  $("#refresh-trends-page")?.addEventListener("click", async () => {
    const btn = $("#refresh-trends-page");
    btn.disabled = true;
    try {
      await getJSON("/api/trends/refresh", { method: "POST" });
      await loadTrendsBoard(true);
      await loadTrafficBoard(true);
    } finally {
      btn.disabled = false;
    }
  });
  $("#refresh-trends").addEventListener("click", async () => {
    const btn = $("#refresh-trends");
    btn.disabled = true;
    try {
      await getJSON("/api/trends/refresh", { method: "POST" });
      await loadDashboard(true);
    } finally {
      btn.disabled = false;
    }
  });
  $("#refresh-db").addEventListener("click", async () => {
    const btn = $("#refresh-db");
    btn.disabled = true;
    btn.textContent = t("common.checkingPages");
    try {
      await getJSON("/api/database/refresh", { method: "POST" });
      await loadDashboard(true);
    } catch (err) {
      $("#dash-status").hidden = false;
      $("#dash-status").textContent = err.message;
    } finally {
      btn.disabled = false;
      btn.textContent = t("common.refreshDb");
    }
  });
  loadFeatured().catch((err) => {
    $("#lookup-status").hidden = false;
    $("#lookup-status").textContent = err.message;
  });
}

boot();
