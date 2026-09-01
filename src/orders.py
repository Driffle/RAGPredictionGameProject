"""Load 2022–2026 order GMV and join best/worst sales weeks to event runtimes."""

from __future__ import annotations

import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import iterparse
from zipfile import ZipFile

from src.calendar_dedupe import is_quarter_timeframe
from src.first_party import is_owned_title, showcase_owner
from src.load_data import canonical_title, gzip_sidecar, load_events, open_tabular
from src.match import _compile_queries, _query_score, queries_for_calendar_row
from src.paths import DATA_PROCESSED, DATA_RAW

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DEFAULT_ORDERS_XLSX = Path(
    "/Users/driffle/Downloads/orders_2022_to_2026_2026-08-18T11_24_32.26557Z.xlsx"
)
WEEK_RE = re.compile(
    r"(?P<start>\d{4}-\d{2}-\d{2})\s+to\s+(?P<end>\d{4}-\d{2}-\d{2})\s+\(GMV:\s*(?P<gmv>[0-9.,]+)\)",
    re.I,
)
ORDERS_CSV = DATA_PROCESSED / "orders.csv"
ORDER_WEEKS_CSV = DATA_PROCESSED / "order_weeks.csv"
ORDER_EVENT_PEAKS_CSV = DATA_PROCESSED / "order_event_peaks.csv"
ORDER_SUMMARY_CSV = DATA_PROCESSED / "order_event_summary.csv"
ORDER_DASHBOARD_JSON = DATA_PROCESSED / "order_dashboard.json"
DASHBOARD_SCHEMA = 3
_JUNK_TITLE = re.compile(r"random 1 key|try to get", re.I)


def orders_path() -> Path:
    local = DATA_RAW / "orders_2022_to_2026.xlsx"
    if local.exists():
        return local
    if DEFAULT_ORDERS_XLSX.exists():
        return DEFAULT_ORDERS_XLSX
    if ORDERS_CSV.exists() or gzip_sidecar(ORDERS_CSV).exists():
        return gzip_sidecar(ORDERS_CSV) if gzip_sidecar(ORDERS_CSV).exists() else ORDERS_CSV
    raise FileNotFoundError(f"Orders file not found at {local} or {DEFAULT_ORDERS_XLSX}")


def _col_letter(cell_ref: str) -> str:
    match = re.match(r"[A-Z]+", cell_ref or "")
    return match.group(0) if match else ""


def _cell_value(elem) -> tuple[str | None, str | None]:
    cell_type = elem.get("t")
    value_node = elem.find(f"{NS}v")
    inline = elem.find(f"{NS}is")
    if value_node is not None and value_node.text is not None:
        return cell_type, value_node.text
    if inline is not None:
        texts = [node.text or "" for node in inline.iter(f"{NS}t")]
        return cell_type, "".join(texts)
    return cell_type, None


def _coerce_id(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def _coerce_float(value: str | None) -> float:
    try:
        return float((value or "0").replace(",", ""))
    except ValueError:
        return 0.0


def parse_week_ranges(blob: str | None, kind: str) -> list[dict]:
    """Parse `2025-11-07 to 2025-11-13 (GMV: 121757.74) | ...` into week rows."""
    weeks: list[dict] = []
    for rank, match in enumerate(WEEK_RE.finditer(blob or ""), start=1):
        weeks.append(
            {
                "week_kind": kind,
                "week_rank": rank,
                "week_start": match.group("start"),
                "week_end": match.group("end"),
                "week_gmv": round(_coerce_float(match.group("gmv")), 2),
            }
        )
    return weeks


def load_orders_xlsx(path: Path) -> list[dict]:
    rows: list[dict] = []
    with ZipFile(path) as archive:
        with archive.open("xl/worksheets/sheet1.xml") as handle:
            current: dict[str, tuple[str | None, str | None]] = {}
            in_row = False
            for event, elem in iterparse(handle, events=("start", "end")):
                tag = elem.tag.rsplit("}", 1)[-1]
                if event == "start" and tag == "row":
                    current = {}
                    in_row = True
                elif event == "end" and tag == "c" and in_row:
                    ref = elem.get("r") or ""
                    letter = _col_letter(ref)
                    if letter:
                        current[letter] = _cell_value(elem)
                    elem.clear()
                elif event == "end" and tag == "row":
                    values = {key: (val[1] or "") for key, val in current.items()}
                    header = (values.get("A") or "").strip()
                    if header == "product_id":
                        elem.clear()
                        continue
                    product_id = _coerce_id(values.get("A"))
                    title = (values.get("B") or "").strip()
                    if not product_id and not title:
                        elem.clear()
                        continue
                    best_raw = (values.get("D") or "").strip()
                    worst_raw = (values.get("E") or "").strip()
                    best = parse_week_ranges(best_raw, "best")
                    worst = parse_week_ranges(worst_raw, "worst")
                    top = best[0] if best else {}
                    rows.append(
                        {
                            "product_id": product_id,
                            "product_title": title,
                            "canonical_title": canonical_title(title),
                            "total_gmv_2022_2026": round(_coerce_float(values.get("C")), 2),
                            "best_sales_week_ranges": best_raw,
                            "worst_sales_week_ranges": worst_raw,
                            "best_week_start": top.get("week_start") or "",
                            "best_week_end": top.get("week_end") or "",
                            "best_week_gmv": top.get("week_gmv") or 0,
                            "best_weeks": best,
                            "worst_weeks": worst,
                            "source": "orders_xlsx",
                        }
                    )
                    elem.clear()
    rows.sort(key=lambda row: (-float(row["total_gmv_2022_2026"]), row["canonical_title"]))
    return rows


def load_orders() -> list[dict]:
    path = orders_path()
    if path.suffix.lower() == ".csv" or str(path).endswith(".csv.gz"):
        plain = Path(str(path).removesuffix(".gz")) if str(path).endswith(".gz") else path
        with open_tabular(plain) as handle:
            rows = []
            for raw in csv.DictReader(handle):
                raw["best_weeks"] = parse_week_ranges(raw.get("best_sales_week_ranges"), "best")
                raw["worst_weeks"] = parse_week_ranges(raw.get("worst_sales_week_ranges"), "worst")
                raw["total_gmv_2022_2026"] = _coerce_float(raw.get("total_gmv_2022_2026"))
                raw["best_week_gmv"] = _coerce_float(raw.get("best_week_gmv"))
                rows.append(raw)
            return rows
    return load_orders_xlsx(path)


def explode_order_weeks(orders: list[dict], *, kinds: tuple[str, ...] = ("best", "worst")) -> list[dict]:
    rows: list[dict] = []
    for order in orders:
        for kind in kinds:
            for week in order.get(f"{kind}_weeks") or []:
                rows.append(
                    {
                        "product_id": order.get("product_id") or "",
                        "canonical_title": order.get("canonical_title") or "",
                        "product_title": order.get("product_title") or "",
                        "total_gmv_2022_2026": order.get("total_gmv_2022_2026") or 0,
                        "week_kind": week["week_kind"],
                        "week_rank": week["week_rank"],
                        "week_start": week["week_start"],
                        "week_end": week["week_end"],
                        "week_gmv": week["week_gmv"],
                        "source": "order_week",
                    }
                )
    return rows


def _iso(value: str | None) -> date | None:
    text = (value or "")[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _event_span(row: dict) -> tuple[date, date] | None:
    start = _iso(row.get("runtime_start") or row.get("start_date"))
    end = _iso(row.get("runtime_end") or row.get("end_date") or row.get("runtime_start") or row.get("start_date"))
    if start is None or end is None:
        return None
    if end < start:
        end = start
    return start, end


def correlate_weeks_with_events(
    weeks: list[dict],
    events: list[dict] | None = None,
    *,
    min_score: int = 2,
    week_kind: str = "best",
    max_runtime_days: int = 45,
) -> list[dict]:
    """Join franchise-matched SKUs to events whose runtime overlaps a sales week.

    Season-long / year-TBA windows are skipped so a 7-day sales spike is not
    attributed to an entire F1 championship or a 2026 planning stub.
    """
    events = events if events is not None else load_events()
    prepared: list[tuple[dict, list, date, date]] = []
    for event in events:
        if is_quarter_timeframe(event):
            continue
        span = _event_span(event)
        queries = queries_for_calendar_row(event)
        if not span or not queries:
            continue
        if (span[1] - span[0]).days > max_runtime_days:
            continue
        prepared.append((event, _compile_queries(queries), span[0], span[1]))
    linked: list[dict] = []
    for week in weeks:
        if week_kind and week.get("week_kind") != week_kind:
            continue
        start = _iso(week.get("week_start"))
        end = _iso(week.get("week_end")) or start
        if start is None or end is None:
            continue
        canonical = week.get("canonical_title") or ""
        full_title = week.get("product_title") or ""
        for event, compiled, ev_start, ev_end in prepared:
            if ev_start > end or ev_end < start:
                continue
            if _query_score(canonical, full_title, compiled) < min_score:
                continue
            linked.append(
                {
                    "product_id": week.get("product_id") or "",
                    "canonical_title": canonical,
                    "product_title": full_title,
                    "total_gmv_2022_2026": week.get("total_gmv_2022_2026") or 0,
                    "week_kind": week.get("week_kind") or "",
                    "week_rank": week.get("week_rank") or "",
                    "week_start": week.get("week_start") or "",
                    "week_end": week.get("week_end") or "",
                    "week_gmv": week.get("week_gmv") or 0,
                    "event": event.get("event") or "",
                    "event_type": event.get("event_type") or "",
                    "category": event.get("category") or "",
                    "related_game": event.get("related_game") or "",
                    "runtime_start": event.get("runtime_start") or event.get("start_date") or "",
                    "runtime_end": event.get("runtime_end") or event.get("end_date") or "",
                    "date_label": event.get("date_label") or "",
                    "source": "order_event_week",
                }
            )
    linked.sort(
        key=lambda row: (
            -float(row.get("week_gmv") or 0),
            row.get("canonical_title") or "",
            row.get("event") or "",
        )
    )
    return linked


def summarize_order_event_peaks(links: list[dict]) -> list[dict]:
    buckets: dict[tuple[str, str], dict] = {}
    seen_skus: dict[tuple[str, str], set[str]] = {}
    for row in links:
        event_name = (row.get("event") or "").strip()
        runtime = (row.get("runtime_start") or "")[:10]
        if not event_name or is_quarter_timeframe(event_name):
            continue
        key = (event_name, runtime)
        bucket = buckets.setdefault(
            key,
            {
                "event": event_name,
                "event_type": row.get("event_type") or "",
                "category": row.get("category") or "",
                "runtime_start": row.get("runtime_start") or "",
                "runtime_end": row.get("runtime_end") or "",
                "matched_skus": 0,
                "matched_weeks": 0,
                "week_gmv": 0.0,
                "lifetime_gmv": 0.0,
            },
        )
        sku_set = seen_skus.setdefault(key, set())
        sku = str(row.get("product_id") or "")
        if sku and sku not in sku_set:
            sku_set.add(sku)
            bucket["lifetime_gmv"] += float(row.get("total_gmv_2022_2026") or 0)
        bucket["matched_weeks"] += 1
        bucket["week_gmv"] += float(row.get("week_gmv") or 0)
        bucket["event_type"] = row.get("event_type") or bucket["event_type"]
        bucket["category"] = row.get("category") or bucket["category"]
        bucket["runtime_end"] = row.get("runtime_end") or bucket["runtime_end"]
    rows = list(buckets.values())
    for key, bucket in buckets.items():
        bucket["matched_skus"] = len(seen_skus.get(key, ()))
        bucket["week_gmv"] = round(bucket["week_gmv"], 2)
        bucket["lifetime_gmv"] = round(bucket["lifetime_gmv"], 2)
    rows.sort(key=lambda row: (-row["week_gmv"], row["event"]))
    return rows


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    gz_path = gzip_sidecar(path) if not str(path).endswith(".gz") else path
    with gzip.open(gz_path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})
    plain = Path(str(gz_path)[:-3]) if str(gz_path).endswith(".gz") else path
    if plain.exists() and plain != gz_path:
        plain.unlink()
    return gz_path


def write_order_datasets(*, orders: list[dict] | None = None, events: list[dict] | None = None) -> dict:
    orders = orders if orders is not None else load_orders()
    weeks = explode_order_weeks(orders)
    links = correlate_weeks_with_events(weeks, events, week_kind="best")
    summary = summarize_order_event_peaks(links)
    _write_csv(
        ORDERS_CSV,
        orders,
        [
            "product_id",
            "canonical_title",
            "product_title",
            "total_gmv_2022_2026",
            "best_week_start",
            "best_week_end",
            "best_week_gmv",
            "best_sales_week_ranges",
            "worst_sales_week_ranges",
            "source",
        ],
    )
    _write_csv(
        ORDER_WEEKS_CSV,
        weeks,
        [
            "product_id",
            "canonical_title",
            "product_title",
            "total_gmv_2022_2026",
            "week_kind",
            "week_rank",
            "week_start",
            "week_end",
            "week_gmv",
            "source",
        ],
    )
    _write_csv(
        ORDER_EVENT_PEAKS_CSV,
        links,
        [
            "product_id",
            "canonical_title",
            "product_title",
            "total_gmv_2022_2026",
            "week_kind",
            "week_rank",
            "week_start",
            "week_end",
            "week_gmv",
            "event",
            "event_type",
            "category",
            "related_game",
            "runtime_start",
            "runtime_end",
            "date_label",
            "source",
        ],
    )
    _write_csv(
        ORDER_SUMMARY_CSV,
        summary,
        [
            "event",
            "event_type",
            "category",
            "runtime_start",
            "runtime_end",
            "matched_skus",
            "matched_weeks",
            "week_gmv",
            "lifetime_gmv",
        ],
    )
    matched_ids = {row.get("product_id") for row in links}
    dashboard = build_order_dashboard(orders, links, summary)
    ORDER_DASHBOARD_JSON.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    return {
        "orders": len(orders),
        "week_rows": len(weeks),
        "linked_rows": len(links),
        "matched_skus": len(matched_ids),
        "events_with_peak_gmv": len(summary),
        "orders_csv": str(ORDERS_CSV),
        "weeks_csv": str(ORDER_WEEKS_CSV),
        "peaks_csv": str(ORDER_EVENT_PEAKS_CSV),
        "summary_csv": str(ORDER_SUMMARY_CSV),
        "dashboard_json": str(ORDER_DASHBOARD_JSON),
        "kpis": dashboard.get("kpis") or {},
    }


def _money(value: float) -> float:
    return round(float(value or 0), 2)


def _pct(part: float, whole: float) -> float:
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 1)


def _gap_reason(row: dict) -> str:
    start = (row.get("best_week_start") or "")[5:7]
    title = (row.get("canonical_title") or "").lower()
    if start in {"11", "12", "01"} and any(token in title for token in ("minecraft", "lego", "sims")):
        return "Holiday catalog, not an event window"
    if any(token in title for token in ("grand theft auto", "gta v", "gta 5")):
        return "Evergreen catalog; no dated 2022–2026 tentpole on the calendar"
    return "Launch / peak week with no franchise event runtime on the calendar"


ORDER_YEARS = ("2022", "2023", "2024", "2025", "2026")


def _year_of(value: str | None) -> str:
    text = (value or "")[:4]
    return text if text in ORDER_YEARS else ""


def _top_n(rows: list[dict], key: str, limit: int = 5) -> list[dict]:
    ranked = sorted(rows, key=lambda row: (-float(row.get(key) or 0), row.get("canonical_title") or row.get("event") or ""))
    return ranked[:limit]


def _unique_link_gmv(
    links: list[dict],
    *,
    year: str | None = None,
    title_by_id: dict[str, str] | None = None,
) -> list[dict]:
    """One overlapping-week GMV row per SKU, week, event runtime, and exact title."""
    seen: set[tuple[str, str, str, str, str]] = set()
    out: list[dict] = []
    titles = title_by_id or {}
    for row in links:
        sku = str(row.get("product_id") or "")
        title = (row.get("canonical_title") or "").strip() or (titles.get(sku) or "").strip()
        event = (row.get("event") or "").strip()
        if not title or not event or is_quarter_timeframe(event) or _JUNK_TITLE.search(title):
            continue
        week = (row.get("week_start") or "")[:10]
        year_key = _year_of(week)
        if year and year_key != year:
            continue
        runtime = (row.get("runtime_start") or "")[:10]
        sku = str(row.get("product_id") or "")
        key = (title, sku, week, event, runtime)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "canonical_title": title,
                "event": event,
                "event_type": row.get("event_type") or "",
                "runtime_start": runtime,
                "runtime_end": (row.get("runtime_end") or "")[:10],
                "week_start": week,
                "week_gmv": float(row.get("week_gmv") or 0),
                "year": year_key,
            }
        )
    return out


def _max_gmv_event_for_title(title: str, rows: list[dict]) -> dict:
    buckets: dict[tuple[str, str], dict] = {}
    for row in rows:
        if row.get("canonical_title") != title:
            continue
        key = (row.get("event") or "", row.get("runtime_start") or "")
        bucket = buckets.setdefault(
            key,
            {
                "event": row.get("event") or "",
                "event_type": row.get("event_type") or "",
                "runtime_start": row.get("runtime_start") or "",
                "runtime_end": row.get("runtime_end") or "",
                "gmv": 0.0,
            },
        )
        bucket["gmv"] += float(row.get("week_gmv") or 0)
        bucket["runtime_end"] = row.get("runtime_end") or bucket["runtime_end"]
        bucket["event_type"] = row.get("event_type") or bucket["event_type"]
    empty = {
        "max_gmv_event": "",
        "max_gmv_event_gmv": 0.0,
        "max_gmv_event_type": "",
        "max_gmv_event_start": "",
        "max_gmv_event_end": "",
    }
    if not buckets:
        return empty
    best = max(buckets.values(), key=lambda item: (float(item.get("gmv") or 0), item.get("event") or ""))
    return {
        "max_gmv_event": best.get("event") or "",
        "max_gmv_event_gmv": _money(best.get("gmv")),
        "max_gmv_event_type": best.get("event_type") or "",
        "max_gmv_event_start": best.get("runtime_start") or "",
        "max_gmv_event_end": best.get("runtime_end") or "",
    }


def _year_max_events_for_title(title: str, rows: list[dict]) -> list[dict]:
    return [
        {"year": year, **_max_gmv_event_for_title(title, [row for row in rows if row.get("year") == year])}
        for year in ORDER_YEARS
    ]


def _recommended_products_for_event(
    event: str,
    runtime_start: str,
    rows: list[dict],
    *,
    limit: int = 5,
) -> list[dict]:
    buckets: dict[str, float] = defaultdict(float)
    runtime = (runtime_start or "")[:10]
    for row in rows:
        if (row.get("event") or "") != event:
            continue
        if runtime and (row.get("runtime_start") or "")[:10] != runtime:
            continue
        title = (row.get("canonical_title") or "").strip()
        if title:
            buckets[title] += float(row.get("week_gmv") or 0)
    ranked = sorted(buckets.items(), key=lambda item: (-item[1], item[0]))[:limit]
    owner = showcase_owner(event)
    if owner:
        owned = [(name, gmv) for name, gmv in ranked if is_owned_title(name, owner)]
        if len(owned) < limit:
            seen = {name.lower() for name, _ in owned}
            extras = sorted(buckets.items(), key=lambda item: (-item[1], item[0]))
            for name, gmv in extras:
                if name.lower() in seen or not is_owned_title(name, owner):
                    continue
                owned.append((name, gmv))
                seen.add(name.lower())
                if len(owned) >= limit:
                    break
        ranked = owned[:limit] or ranked
    return [{"canonical_title": name, "year_gmv": _money(gmv)} for name, gmv in ranked]


def _with_max_event(row: dict, contrib: list[dict], *, with_years: bool = False) -> dict:
    out = dict(row)
    out.update(_max_gmv_event_for_title(row.get("canonical_title") or "", contrib))
    if with_years:
        out["year_max_events"] = _year_max_events_for_title(row.get("canonical_title") or "", contrib)
    return out


def _with_recommended_products(row: dict, contrib: list[dict]) -> dict:
    out = dict(row)
    out["recommended_products"] = _recommended_products_for_event(
        row.get("event") or "",
        row.get("runtime_start") or "",
        contrib,
    )
    return out


def period_and_year_leaderboards(orders: list[dict], links: list[dict]) -> dict:
    """Top 5 products and events by observed GMV for 2022–2026 and each year."""
    weeks = explode_order_weeks(orders, kinds=("best",))
    title_by_id = {
        str(row.get("product_id") or ""): (row.get("canonical_title") or "").strip()
        for row in orders
        if row.get("product_id")
    }
    all_contrib = _unique_link_gmv(links, title_by_id=title_by_id)
    product_period: dict[str, dict] = {}
    product_year: dict[tuple[str, str], dict] = {}
    for week in weeks:
        title = (week.get("canonical_title") or "").strip()
        if not title:
            continue
        gmv = float(week.get("week_gmv") or 0)
        sku = str(week.get("product_id") or "")
        start = week.get("week_start") or ""
        period = product_period.setdefault(
            title,
            {
                "canonical_title": title,
                "year_gmv": 0.0,
                "best_week_gmv": 0.0,
                "best_week_start": "",
                "weeks": 0,
                "skus": set(),
            },
        )
        period["year_gmv"] += gmv
        period["weeks"] += 1
        if sku:
            period["skus"].add(sku)
        if gmv > period["best_week_gmv"]:
            period["best_week_gmv"] = gmv
            period["best_week_start"] = start
        year = _year_of(start)
        if not year:
            continue
        bucket = product_year.setdefault(
            (year, title),
            {
                "year": year,
                "canonical_title": title,
                "year_gmv": 0.0,
                "best_week_gmv": 0.0,
                "best_week_start": "",
                "weeks": 0,
                "skus": set(),
            },
        )
        bucket["year_gmv"] += gmv
        bucket["weeks"] += 1
        if sku:
            bucket["skus"].add(sku)
        if gmv > bucket["best_week_gmv"]:
            bucket["best_week_gmv"] = gmv
            bucket["best_week_start"] = start

    # Lifetime GMV by title (all SKUs of that name) for the period ranking.
    lifetime_by_title: dict[str, float] = defaultdict(float)
    sku_by_title: dict[str, set[str]] = defaultdict(set)
    for row in orders:
        title = (row.get("canonical_title") or "").strip()
        if not title:
            continue
        lifetime_by_title[title] += float(row.get("total_gmv_2022_2026") or 0)
        sku = str(row.get("product_id") or "")
        if sku:
            sku_by_title[title].add(sku)

    period_products = []
    for title, life in lifetime_by_title.items():
        peak = product_period.get(title) or {}
        period_products.append(
            {
                "canonical_title": title,
                "lifetime_gmv": _money(life),
                "year_gmv": _money(peak.get("year_gmv")),
                "best_week_gmv": _money(peak.get("best_week_gmv")),
                "best_week_start": peak.get("best_week_start") or "",
                "weeks": int(peak.get("weeks") or 0),
                "sku_count": len(sku_by_title.get(title) or peak.get("skus") or ()),
            }
        )
    top_products = [_with_max_event(row, all_contrib, with_years=True) for row in _top_n(period_products, "lifetime_gmv")]

    event_period: dict[tuple[str, str], dict] = {}
    event_year: dict[tuple[str, str, str], dict] = {}
    for row in links:
        name = (row.get("event") or "").strip()
        if not name or is_quarter_timeframe(name):
            continue
        gmv = float(row.get("week_gmv") or 0)
        sku = str(row.get("product_id") or "")
        runtime = (row.get("runtime_start") or "")[:10]
        period_key = (name, runtime)
        bucket = event_period.setdefault(
            period_key,
            {
                "event": name,
                "event_type": row.get("event_type") or "",
                "category": row.get("category") or "",
                "runtime_start": row.get("runtime_start") or "",
                "runtime_end": row.get("runtime_end") or "",
                "year_gmv": 0.0,
                "weeks": 0,
                "skus": set(),
            },
        )
        bucket["year_gmv"] += gmv
        bucket["weeks"] += 1
        if sku:
            bucket["skus"].add(sku)
        bucket["event_type"] = row.get("event_type") or bucket["event_type"]
        bucket["runtime_end"] = row.get("runtime_end") or bucket["runtime_end"]
        year = _year_of(row.get("week_start") or runtime)
        if not year:
            continue
        ykey = (year, name, runtime)
        ybucket = event_year.setdefault(
            ykey,
            {
                "year": year,
                "event": name,
                "event_type": row.get("event_type") or "",
                "category": row.get("category") or "",
                "runtime_start": row.get("runtime_start") or "",
                "runtime_end": row.get("runtime_end") or "",
                "year_gmv": 0.0,
                "weeks": 0,
                "skus": set(),
            },
        )
        ybucket["year_gmv"] += gmv
        ybucket["weeks"] += 1
        if sku:
            ybucket["skus"].add(sku)
        ybucket["event_type"] = row.get("event_type") or ybucket["event_type"]
        ybucket["runtime_end"] = row.get("runtime_end") or ybucket["runtime_end"]

    def _freeze_event(row: dict) -> dict:
        return {
            "event": row.get("event") or "",
            "event_type": row.get("event_type") or "",
            "category": row.get("category") or "",
            "runtime_start": row.get("runtime_start") or "",
            "runtime_end": row.get("runtime_end") or "",
            "year_gmv": _money(row.get("year_gmv")),
            "week_gmv": _money(row.get("year_gmv")),
            "weeks": int(row.get("weeks") or 0),
            "matched_skus": len(row.get("skus") or ()),
        }

    top_events = [
        _with_recommended_products(row, all_contrib)
        for row in _top_n([_freeze_event(row) for row in event_period.values()], "year_gmv")
    ]
    period_product_gmv = sum(float(row["lifetime_gmv"]) for row in top_products)
    period_event_gmv = sum(float(row["year_gmv"]) for row in top_events)
    period_observed = sum(float(row.get("week_gmv") or 0) for row in weeks)
    period_event_total = sum(float(row.get("year_gmv") or 0) for row in event_period.values())
    period_life = sum(lifetime_by_title.values())

    years = []
    for year in ORDER_YEARS:
        year_contrib = [row for row in all_contrib if row.get("year") == year]
        year_products = []
        for (item_year, title), row in product_year.items():
            if item_year != year:
                continue
            year_products.append(
                {
                    "canonical_title": title,
                    "year_gmv": _money(row["year_gmv"]),
                    "lifetime_gmv": _money(lifetime_by_title.get(title)),
                    "best_week_gmv": _money(row["best_week_gmv"]),
                    "best_week_start": row.get("best_week_start") or "",
                    "weeks": int(row["weeks"]),
                    "sku_count": len(row["skus"]),
                }
            )
        year_events = [
            _freeze_event(row)
            for (item_year, _name, _runtime), row in event_year.items()
            if item_year == year
        ]
        top_year_products = [
            _with_max_event(row, year_contrib)
            for row in _top_n(year_products, "year_gmv")
        ]
        top_year_events = [
            _with_recommended_products(row, year_contrib)
            for row in _top_n(year_events, "year_gmv")
        ]
        year_gmv = sum(float(row["year_gmv"]) for row in year_products)
        year_event_gmv = sum(float(row["year_gmv"]) for row in year_events)
        top5_product_gmv = sum(float(row["year_gmv"]) for row in top_year_products)
        top5_event_gmv = sum(float(row["year_gmv"]) for row in top_year_events)
        hero_product = top_year_products[0] if top_year_products else {}
        hero_event = top_year_events[0] if top_year_events else {}
        years.append(
            {
                "year": year,
                "kpis": {
                    "observed_week_gmv": _money(year_gmv),
                    "event_week_gmv": _money(year_event_gmv),
                    "sku_titles": len(year_products),
                    "events": len(year_events),
                    "top5_product_gmv": _money(top5_product_gmv),
                    "top5_product_share": _pct(top5_product_gmv, year_gmv),
                    "top5_event_gmv": _money(top5_event_gmv),
                    "top5_event_share": _pct(top5_event_gmv, year_event_gmv),
                    "top_product": hero_product.get("canonical_title") or "",
                    "top_product_gmv": _money(hero_product.get("year_gmv")),
                    "top_event": hero_event.get("event") or "",
                    "top_event_gmv": _money(hero_event.get("year_gmv")),
                },
                "top_products": top_year_products,
                "top_events": top_year_events,
            }
        )

    return {
        "kpis": {
            "top5_product_gmv": _money(period_product_gmv),
            "top5_product_share": _pct(period_product_gmv, period_life),
            "top5_event_gmv": _money(period_event_gmv),
            "top5_event_share": _pct(period_event_gmv, period_event_total),
            "observed_week_gmv": _money(period_observed),
            "top_product": (top_products[0]["canonical_title"] if top_products else ""),
            "top_product_gmv": _money(top_products[0]["lifetime_gmv"] if top_products else 0),
            "top_event": (top_events[0]["event"] if top_events else ""),
            "top_event_gmv": _money(top_events[0]["year_gmv"] if top_events else 0),
        },
        "top_products": top_products,
        "top_events": top_events,
        "years": years,
    }


def build_order_dashboard(
    orders: list[dict],
    links: list[dict],
    summary: list[dict],
    *,
    as_of: str | None = None,
) -> dict:
    """KPIs that judge whether event-runtime RAG would have caught historical peaks."""
    lifetime = sum(float(row.get("total_gmv_2022_2026") or 0) for row in orders)
    best_sum = sum(float(row.get("best_week_gmv") or 0) for row in orders)
    matched_ids = {str(row.get("product_id") or "") for row in links}
    matched_orders = [row for row in orders if str(row.get("product_id") or "") in matched_ids]
    matched_life = sum(float(row.get("total_gmv_2022_2026") or 0) for row in matched_orders)
    matched_best = sum(float(row.get("best_week_gmv") or 0) for row in matched_orders)

    uniq_week: dict[tuple[str, str], float] = {}
    first_event: dict[tuple[str, str], dict] = {}
    rank1_gmv: dict[str, float] = {}
    for row in links:
        sku = str(row.get("product_id") or "")
        start = (row.get("week_start") or "")[:10]
        gmv = float(row.get("week_gmv") or 0)
        key = (sku, start)
        uniq_week[key] = gmv
        first_event.setdefault(key, row)
        if str(row.get("week_rank") or "") in {"1", "1.0"}:
            rank1_gmv[sku] = gmv

    type_gmv: dict[str, float] = defaultdict(float)
    type_n: Counter[str] = Counter()
    cat_gmv: dict[str, float] = defaultdict(float)
    for key, row in first_event.items():
        event_type = row.get("event_type") or "Other"
        type_gmv[event_type] += uniq_week[key]
        type_n[event_type] += 1
        cat_gmv[row.get("category") or "Other"] += uniq_week[key]

    years = []
    leaders = period_and_year_leaderboards(orders, links)
    leaders_by_year = {row["year"]: row for row in leaders.get("years") or []}
    for year in ORDER_YEARS:
        rows = [row for row in orders if (row.get("best_week_start") or "").startswith(year)]
        year_life = sum(float(row.get("total_gmv_2022_2026") or 0) for row in rows)
        year_best = sum(float(row.get("best_week_gmv") or 0) for row in rows)
        year_hit = sum(
            float(row.get("best_week_gmv") or 0)
            for row in rows
            if str(row.get("product_id") or "") in matched_ids
        )
        board = leaders_by_year.get(year) or {}
        years.append(
            {
                "year": year,
                "skus": len(rows),
                "lifetime_gmv": _money(year_life),
                "best_week_gmv": _money(year_best),
                "hit_best_week_gmv": _money(year_hit),
                "hit_pct": _pct(year_hit, year_best),
                "kpis": board.get("kpis") or {},
                "top_products": board.get("top_products") or [],
                "top_events": board.get("top_events") or [],
            }
        )

    sorted_orders = sorted(orders, key=lambda row: -float(row.get("total_gmv_2022_2026") or 0))
    top10 = sum(float(row.get("total_gmv_2022_2026") or 0) for row in sorted_orders[:10])
    top50 = sum(float(row.get("total_gmv_2022_2026") or 0) for row in sorted_orders[:50])

    def events_for(sku: str, *, rank1_only: bool = True) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for row in links:
            if str(row.get("product_id") or "") != sku:
                continue
            if rank1_only and str(row.get("week_rank") or "") not in {"1", "1.0"}:
                continue
            name = row.get("event") or ""
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names

    top_skus = []
    for row in sorted_orders[:8]:
        sku = str(row.get("product_id") or "")
        names = events_for(sku, rank1_only=True) or events_for(sku, rank1_only=False)
        top_skus.append(
            {
                "canonical_title": row.get("canonical_title") or "",
                "lifetime_gmv": _money(row.get("total_gmv_2022_2026")),
                "best_week_start": row.get("best_week_start") or "",
                "best_week_end": row.get("best_week_end") or "",
                "best_week_gmv": _money(row.get("best_week_gmv")),
                "events": names,
                "gap": "" if names else _gap_reason(row),
            }
        )

    missed = []
    for row in sorted_orders:
        if str(row.get("product_id") or "") in matched_ids:
            continue
        missed.append(
            {
                "canonical_title": row.get("canonical_title") or "",
                "lifetime_gmv": _money(row.get("total_gmv_2022_2026")),
                "best_week_start": row.get("best_week_start") or "",
                "best_week_gmv": _money(row.get("best_week_gmv")),
                "gap": _gap_reason(row),
            }
        )
        if len(missed) >= 8:
            break

    y2026 = next((row for row in years if row["year"] == "2026"), {})
    y2024 = next((row for row in years if row["year"] == "2024"), {})
    release_gmv = type_gmv.get("Product Release", 0.0)
    leader_kpis = leaders.get("kpis") or {}
    return {
        "as_of": as_of or date.today().isoformat(),
        "schema": DASHBOARD_SCHEMA,
        "source": "orders_2022_to_2026.xlsx · event runtimes 2022–2026",
        "kpis": {
            "sku_count": len(orders),
            "lifetime_gmv": _money(lifetime),
            "best_week_gmv": _money(best_sum),
            "best_week_share_of_lifetime": _pct(best_sum, lifetime),
            "matched_skus": len(matched_ids),
            "matched_sku_pct": _pct(len(matched_ids), len(orders)),
            "matched_lifetime_gmv": _money(matched_life),
            "matched_lifetime_pct": _pct(matched_life, lifetime),
            "matched_best_week_gmv": _money(matched_best),
            "matched_best_week_pct": _pct(matched_best, best_sum),
            "events_with_peak_gmv": len(summary),
            "unique_linked_week_gmv": _money(sum(uniq_week.values())),
            "unique_rank1_linked_gmv": _money(sum(rank1_gmv.values())),
            "pct_2026_best_week_hit_event": y2026.get("hit_pct") or 0.0,
            "pct_2024_best_week_hit_event": y2024.get("hit_pct") or 0.0,
            "top10_lifetime_share": _pct(top10, lifetime),
            "top50_lifetime_share": _pct(top50, lifetime),
            "release_window_week_gmv": _money(release_gmv),
            "top5_product_gmv": leader_kpis.get("top5_product_gmv") or 0.0,
            "top5_product_share": leader_kpis.get("top5_product_share") or 0.0,
            "top5_event_gmv": leader_kpis.get("top5_event_gmv") or 0.0,
            "top5_event_share": leader_kpis.get("top5_event_share") or 0.0,
            "top_product": leader_kpis.get("top_product") or "",
            "top_product_gmv": leader_kpis.get("top_product_gmv") or 0.0,
            "top_event": leader_kpis.get("top_event") or "",
            "top_event_gmv": leader_kpis.get("top_event_gmv") or 0.0,
        },
        "years": years,
        "period_top_products": leaders.get("top_products") or [],
        "period_top_events": leaders.get("top_events") or [],
        "event_types": [
            {"event_type": name, "weeks": type_n[name], "week_gmv": _money(gmv)}
            for name, gmv in sorted(type_gmv.items(), key=lambda item: -item[1])[:10]
        ],
        "categories": [
            {"category": name, "week_gmv": _money(gmv)}
            for name, gmv in sorted(cat_gmv.items(), key=lambda item: -item[1])
            if gmv >= 100
        ],
        "top_events": [
            {
                "event": row.get("event") or "",
                "event_type": row.get("event_type") or "",
                "category": row.get("category") or "",
                "runtime_start": row.get("runtime_start") or "",
                "runtime_end": row.get("runtime_end") or "",
                "matched_skus": int(row.get("matched_skus") or 0),
                "week_gmv": _money(row.get("week_gmv")),
                "lifetime_gmv": _money(row.get("lifetime_gmv")),
            }
            for row in summary
            if not is_quarter_timeframe(row.get("event") or "")
        ][:12],
        "top_skus": top_skus,
        "missed_skus": missed,
    }


def _dashboard_has_year_leaders(payload: dict) -> bool:
    years = payload.get("years") or []
    products = payload.get("period_top_products") or []
    events = payload.get("period_top_events") or []
    first_year = years[0] if years else {}
    year_products = first_year.get("top_products") or []
    year_events = first_year.get("top_events") or []
    return bool(
        payload.get("schema") == DASHBOARD_SCHEMA
        and products
        and events
        and years
        and first_year.get("top_products") is not None
        and first_year.get("top_events") is not None
        and "max_gmv_event" in products[0]
        and "year_max_events" in products[0]
        and "recommended_products" in events[0]
        and (not year_products or "max_gmv_event" in year_products[0])
        and (not year_events or "recommended_products" in year_events[0])
    )


def _orders_from_processed_csv() -> list[dict]:
    if not (ORDERS_CSV.exists() or gzip_sidecar(ORDERS_CSV).exists()):
        return load_orders()
    rows = []
    with open_tabular(ORDERS_CSV) as handle:
        for raw in csv.DictReader(handle):
            raw["best_weeks"] = parse_week_ranges(raw.get("best_sales_week_ranges"), "best")
            raw["worst_weeks"] = parse_week_ranges(raw.get("worst_sales_week_ranges"), "worst")
            raw["total_gmv_2022_2026"] = _coerce_float(raw.get("total_gmv_2022_2026"))
            raw["best_week_gmv"] = _coerce_float(raw.get("best_week_gmv"))
            rows.append(raw)
    return rows


def load_order_dashboard() -> dict:
    if ORDER_DASHBOARD_JSON.exists():
        try:
            payload = json.loads(ORDER_DASHBOARD_JSON.read_text(encoding="utf-8"))
            if _dashboard_has_year_leaders(payload):
                return payload
        except json.JSONDecodeError:
            pass
    if not (ORDERS_CSV.exists() or gzip_sidecar(ORDERS_CSV).exists()) or not (
        ORDER_EVENT_PEAKS_CSV.exists() or gzip_sidecar(ORDER_EVENT_PEAKS_CSV).exists()
    ):
        return {}
    orders = _orders_from_processed_csv()
    with open_tabular(ORDER_EVENT_PEAKS_CSV) as handle:
        links = list(csv.DictReader(handle))
    if ORDER_SUMMARY_CSV.exists() or gzip_sidecar(ORDER_SUMMARY_CSV).exists():
        with open_tabular(ORDER_SUMMARY_CSV) as handle:
            summary = list(csv.DictReader(handle))
    else:
        summary = summarize_order_event_peaks(links)
    dashboard = build_order_dashboard(orders, links, summary)
    ORDER_DASHBOARD_JSON.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    return dashboard
