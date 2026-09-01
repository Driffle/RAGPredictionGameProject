#!/usr/bin/env python3
"""Export Floor Brief's top Sep–Dec 2026 events to PDF and DOCX.

Layout mirrors the website desk: dark mast, kicker, event lede cards,
runtime KPIs, and a mapped-products grid of ten recommended games.
"""

from __future__ import annotations

import html
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.artwork import artwork_for, load_artwork
from src.calendar_dedupe import canonical_event_name, dedupe_calendar_rows, is_gaming_world_event, unique_event_listings
from src.date_range import event_window, events_in_range, row_precision
from src.dates import annotate_event
from src.first_party import showcase_owner
from src.load_data import load_catalog
from src.match import build_title_index
from src.promote import calendar_label, recommended_games_for_event

RANGE_START = date(2026, 9, 1)
RANGE_END = date(2026, 12, 31)
STEM = "FloorBrief_Sep-Dec_2026_Top_Events"
DESKTOP = Path.home() / "Desktop"
DOCS = ROOT / "docs"

BG = "07080F"
INK = "F4F7FF"
MUTED = "9AA6C3"
CYAN = "5CE1E6"
MAGENTA = "FF5CA8"
AMBER = "FFC14A"
CARD = "0E1222"
LINE = "2A3148"

MAJOR_WEIGHTS = (
    ("the game awards", 90),
    ("state of play", 88),
    ("nintendo direct", 84),
    ("tokyo game show", 80),
    ("steam next fest", 82),
    ("pax west", 50),
    ("blizzcon", 60),
    ("paris games week", 58),
    ("brasil game show", 52),
    ("golden joystick", 48),
    ("g-star", 46),
)


def nice_date(value: str | None) -> str:
    text = (value or "")[:10]
    if len(text) < 10:
        return value or "—"
    parsed = date.fromisoformat(text)
    return parsed.strftime("%-d %b %Y")


def runtime_label(row: dict) -> str:
    dated = annotate_event(row)
    label = dated.get("date_label") or ""
    if label:
        return label
    start, end = event_window(row)
    if not start:
        return "—"
    left = nice_date(start.isoformat())
    right = nice_date((end or start).isoformat())
    return left if left == right else f"{left} → {right}"


def load_calendar() -> list[dict]:
    from src.database import live_events

    rows = live_events()
    if rows:
        return rows
    from src.historical_calendar import historical_events
    from src.horizon import projected_events
    from src.load_data import load_events

    return list(historical_events()) + list(projected_events()) + list(load_events())


def event_score(row: dict) -> tuple:
    name = (row.get("event") or "").lower()
    event_type = (row.get("event_type") or "").lower()
    status = f"{row.get('confirmation') or ''} {row.get('status') or ''}".lower()
    score = 0
    for needle, points in MAJOR_WEIGHTS:
        if needle in name:
            score += points
            break
    else:
        if "showcase" in event_type or "awards" in event_type:
            score += 30
        elif "expo" in event_type:
            score += 24
        elif "festival" in event_type:
            score += 18
    if "japan" in name and "state of play" in name:
        score -= 20
    if "partner" in name:
        score -= 40
    if "confirm" in status:
        score += 18
    precision = row_precision(row)
    if precision == "day":
        score += 8
    elif precision == "month":
        score -= 6
    start = row.get("start_date") or "9999"
    return (-score, start, name)


def top_events(rows: list[dict], *, limit: int = 5) -> list[dict]:
    matched = events_in_range(rows, RANGE_START, RANGE_END, kind="event", precision="dated")
    gaming = [row for row in matched if is_gaming_world_event(row)]
    gaming = unique_event_listings(dedupe_calendar_rows(gaming))
    gaming.sort(key=event_score)
    picked: list[dict] = []
    seen_family: set[str] = set()
    for row in gaming:
        name = (row.get("event") or "").lower()
        if "state of play" in name:
            family = "state of play"
        elif "nintendo direct" in name:
            family = "nintendo direct"
        else:
            family = canonical_event_name(row)
        if not family or family in seen_family:
            continue
        seen_family.add(family)
        picked.append(row)
        if len(picked) >= limit:
            break
    picked.sort(key=lambda row: row.get("start_date") or "9999")
    return picked


def art_uri(name: str, kind: str, dataset: dict) -> str:
    art = artwork_for(name, kind=kind, dataset=dataset)
    path = Path(str(art.get("local_path") or ""))
    if path.exists():
        return path.resolve().as_uri()
    return str(art.get("image_url") or "")


def local_art(name: str, kind: str, dataset: dict) -> Path | None:
    art = artwork_for(name, kind=kind, dataset=dataset)
    path = Path(str(art.get("local_path") or ""))
    return path if path.exists() else None


def build_payload() -> dict:
    catalog = load_catalog(games_only=True, drop_placeholder_dates=True)
    title_index = build_title_index(catalog)
    artwork = load_artwork()
    events = []
    for row in top_events(load_calendar()):
        games = recommended_games_for_event(row, catalog, limit=10, title_index=title_index)
        start, end = event_window(row)
        owner = showcase_owner(calendar_label(row))
        events.append(
            {
                "name": calendar_label(row),
                "kind": row.get("event_type") or row.get("kind") or "event",
                "status": row.get("confirmation") or row.get("status") or "planning",
                "location": row.get("location") or "",
                "country": row.get("country") or "",
                "mode": row.get("attendance_mode") or "",
                "related": row.get("related_game") or "",
                "runtime": runtime_label(row),
                "start": start.isoformat() if start else "",
                "end": (end or start).isoformat() if (end or start) else "",
                "owner": owner.publisher_label if owner else "",
                "image": art_uri(calendar_label(row), "event", artwork),
                "image_path": local_art(calendar_label(row), "event", artwork),
                "games": [
                    {
                        "title": game.get("canonical_title") or "",
                        "platform": game.get("platform") or "",
                        "release": nice_date(game.get("release_date") or "")
                        if game.get("release_date")
                        else "TBA",
                        "type": game.get("product_type") or "game",
                        "publisher": game.get("publisher") or "",
                        "image": art_uri(game.get("canonical_title") or "", "product", artwork),
                        "image_path": local_art(game.get("canonical_title") or "", "product", artwork),
                    }
                    for game in games
                ],
            }
        )
    return {
        "as_of": date.today().isoformat(),
        "range_label": f"{nice_date(RANGE_START.isoformat())} → {nice_date(RANGE_END.isoformat())}",
        "events": events,
    }


def render_html(payload: dict) -> str:
    cards = []
    for index, event in enumerate(payload["events"], start=1):
        tiles = []
        for rank, game in enumerate(event["games"], start=1):
            img = (
                f'<img src="{html.escape(game["image"])}" alt="">'
                if game["image"]
                else '<span class="thumb-empty"></span>'
            )
            tiles.append(
                f"""
            <article class="media-tile">
              <span class="rank">#{rank:02d}</span>
              {img}
              <h5>{html.escape(game["title"])}</h5>
              <p class="meta">{html.escape(game["release"])} · {html.escape(game["type"])}</p>
              <p class="meta">{html.escape(game["platform"] or "Multi")}</p>
            </article>"""
            )
        owner_badge = (
            f'<span class="badge on">{html.escape(event["owner"])}</span>' if event["owner"] else ""
        )
        cover = (
            f'<img class="lede-cover" src="{html.escape(event["image"])}" alt="">'
            if event["image"]
            else '<div class="lede-cover empty"></div>'
        )
        cards.append(
            f"""
        <article class="lede">
          <div class="lede-hero">
            {cover}
            <div>
              <div class="badge-row">
                <span class="badge on">#{index:02d} · {html.escape(event["kind"])}</span>
                <span class="badge live">{html.escape(event["status"])}</span>
                {owner_badge}
                <span class="badge">{html.escape(event["mode"] or "digital / physical")}</span>
              </div>
              <h3 class="event-title">{html.escape(event["name"])}</h3>
              <p class="action">Event runtime {html.escape(event["runtime"])}</p>
              <p class="meta">{html.escape(event["location"] or event["country"] or "Worldwide")}</p>
            </div>
          </div>
          <div class="kpis">
            <div class="kpi"><b>{html.escape(nice_date(event["start"]))}</b><span>Runtime start</span></div>
            <div class="kpi"><b>{html.escape(nice_date(event["end"]))}</b><span>Runtime end</span></div>
            <div class="kpi"><b>{len(event["games"])}</b><span>Recommended games</span></div>
            <div class="kpi"><b>{html.escape(event["mode"] or "—")}</b><span>Attendance</span></div>
          </div>
          <section class="card">
            <h4>Mapped products · top 10 recommended games</h4>
            <div class="media-grid">{"".join(tiles)}</div>
          </section>
        </article>"""
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Floor Brief · Sep–Dec 2026</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Syne:wght@700;800&display=swap" rel="stylesheet"/>
  <style>
    :root {{ --bg:#{BG}; --ink:#{INK}; --muted:#{MUTED}; --cyan:#{CYAN}; --magenta:#{MAGENTA}; --amber:#{AMBER}; --card:#{CARD}; --line:#{LINE}; }}
    * {{ box-sizing:border-box; }}
    html, body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 "IBM Plex Sans", "Segoe UI", sans-serif; }}
    body {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
    .aurora {{ position:fixed; inset:0; pointer-events:none; background:
      radial-gradient(900px 500px at 12% -10%, rgba(92,225,230,.22), transparent 55%),
      radial-gradient(700px 420px at 90% 8%, rgba(255,92,168,.18), transparent 50%),
      radial-gradient(600px 400px at 70% 90%, rgba(255,193,74,.1), transparent 55%); }}
    .mast, main {{ position:relative; z-index:1; }}
    .mast {{ display:flex; justify-content:space-between; align-items:flex-end; padding:28px 36px 18px; border-bottom:1px solid rgba(255,255,255,.12); }}
    .kicker {{ margin:0; letter-spacing:.16em; text-transform:uppercase; font-size:11px; color:var(--cyan); display:flex; align-items:center; gap:8px; }}
    .pulse-dot {{ width:8px; height:8px; border-radius:50%; background:var(--cyan); }}
    .mast h1 {{ margin:6px 0 0; font-family:Syne, Palatino, sans-serif; font-size:48px; letter-spacing:-.04em; line-height:.9;
      background:linear-gradient(120deg,#fff 20%,var(--cyan) 50%,var(--magenta) 90%); -webkit-background-clip:text; background-clip:text; color:transparent; }}
    .range {{ color:var(--muted); font-size:13px; text-align:right; }}
    main {{ padding:28px 36px 48px; width:min(1100px,100%); }}
    .intro h2 {{ font-family:Syne, sans-serif; font-size:32px; margin:0 0 8px; letter-spacing:-.03em; }}
    .intro p {{ margin:0 0 22px; color:var(--muted); max-width:70ch; }}
    .lede, .card {{ background:rgba(14,18,34,.86); border:1px solid rgba(255,255,255,.12); border-radius:20px; padding:22px; margin:0 0 22px; }}
    .lede-hero {{ display:grid; grid-template-columns:140px 1fr; gap:18px; align-items:start; }}
    .lede-cover {{ width:140px; height:180px; object-fit:cover; border-radius:14px; background:rgba(255,255,255,.06); }}
    .event-title {{ margin:0 0 8px; font-family:Syne, sans-serif; font-size:30px; letter-spacing:-.03em; }}
    .action {{ font-size:17px; color:var(--amber); margin:0 0 6px; }}
    .badge-row {{ display:flex; flex-wrap:wrap; gap:8px; margin:0 0 12px; }}
    .badge {{ font-size:10px; letter-spacing:.08em; text-transform:uppercase; padding:5px 9px; border-radius:999px; border:1px solid rgba(255,255,255,.12); }}
    .badge.on {{ border-color:var(--cyan); color:var(--cyan); }}
    .badge.live {{ border-color:#7dffb0; color:#7dffb0; }}
    .kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:16px 0; }}
    .kpi {{ border:1px solid rgba(255,255,255,.12); border-radius:14px; padding:10px 12px; background:rgba(255,255,255,.03); }}
    .kpi b {{ display:block; font-size:16px; }}
    .kpi span {{ color:var(--muted); font-size:10px; letter-spacing:.1em; text-transform:uppercase; }}
    h4 {{ margin:0 0 12px; letter-spacing:.08em; text-transform:uppercase; font-size:11px; color:var(--cyan); }}
    .media-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }}
    .media-tile {{ position:relative; padding:12px 12px 12px 70px; min-height:78px; border:1px solid rgba(255,255,255,.12); border-radius:16px; background:linear-gradient(145deg,rgba(255,255,255,.05),rgba(92,225,230,.04)); }}
    .media-tile img, .thumb-empty {{ position:absolute; left:12px; top:12px; width:44px; height:58px; object-fit:cover; border-radius:8px; background:rgba(255,255,255,.08); }}
    .media-tile h5 {{ margin:0 0 4px; font:700 15px/1.25 Syne, sans-serif; }}
    .meta {{ margin:3px 0; color:var(--muted); font-size:12px; }}
    .rank {{ position:absolute; right:10px; top:8px; color:var(--cyan); font-size:10px; letter-spacing:.12em; }}
    .colophon {{ color:var(--muted); font-size:11px; padding:0 36px 28px; }}
    @page {{ size:A4; margin:12mm; }}
    @media print {{
      .lede {{ break-inside:avoid; page-break-inside:avoid; }}
    }}
  </style>
</head>
<body>
  <div class="aurora"></div>
  <header class="mast">
    <div>
      <p class="kicker"><span class="pulse-dot"></span> Live desk · 2026–2030</p>
      <h1>Floor Brief</h1>
    </div>
    <p class="range">Event window<br><b style="color:{INK}">{html.escape(payload["range_label"])}</b><br>As of {html.escape(payload["as_of"])}</p>
  </header>
  <main>
    <div class="intro">
      <h2>Which event windows are live?</h2>
      <p>Top five merchandising events overlapping 1 Sep 2026–31 Dec 2026, ranked like the Floor Brief desk: confirmed showcases and expos first. Each card lists the event runtime and the ten catalog games to recommend in that window. Console showcases keep first-party owned-studio games (SIE on State of Play, Nintendo on Directs).</p>
    </div>
    {"".join(cards)}
  </main>
  <p class="colophon">Floor Brief · mapped products from the live catalog and promotion plans · {html.escape(payload["as_of"])}</p>
</body>
</html>
"""


def write_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        raise FileNotFoundError("Google Chrome is required to print the Floor Brief PDF")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--allow-file-access-from-files",
        f"--print-to-pdf={pdf_path}",
        html_path.resolve().as_uri(),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _shade(cell, fill: str) -> None:
    from docx.oxml import parse_xml

    tc_pr = cell._tc.get_or_add_tcPr()
    tc_pr.append(
        parse_xml(
            f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="{fill}" w:val="clear"/>'
        )
    )


def _run(paragraph, text: str, *, size: int = 11, color: str = INK, bold: bool = False, font: str = "Calibri") -> None:
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    run = paragraph.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    run.font.color.rgb = RGBColor.from_string(color)


def write_docx(payload: dict, path: Path) -> None:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import parse_xml
    from docx.oxml.ns import qn
    from docx.shared import Cm, Inches, Pt, RGBColor

    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(1.4)
    section.right_margin = Cm(1.4)
    section.top_margin = Cm(1.2)
    section.bottom_margin = Cm(1.2)
    background = parse_xml(
        f'<w:background xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:color="{BG}"/>'
    )
    doc.element.insert(0, background)
    settings = doc.settings.element
    display = parse_xml(
        '<w:displayBackgroundShape xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
    )
    settings.append(display)

    def dark_table(rows: int, cols: int):
        table = doc.add_table(rows=rows, cols=cols)
        table.autofit = True
        for row in table.rows:
            for cell in row.cells:
                _shade(cell, CARD)
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_after = Pt(2)
        return table

    mast = dark_table(1, 2)
    _shade(mast.cell(0, 0), BG)
    _shade(mast.cell(0, 1), BG)
    left = mast.cell(0, 0).paragraphs[0]
    _run(left, "●  LIVE DESK · 2026–2030", size=9, color=CYAN, bold=True)
    title = mast.cell(0, 0).add_paragraph()
    _run(title, "Floor Brief", size=28, color=CYAN, bold=True, font="Arial")
    right = mast.cell(0, 1).paragraphs[0]
    right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run(right, "Event window", size=9, color=MUTED)
    rng = mast.cell(0, 1).add_paragraph()
    rng.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run(rng, payload["range_label"], size=12, color=INK, bold=True)
    asof = mast.cell(0, 1).add_paragraph()
    asof.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run(asof, f"As of {payload['as_of']}", size=10, color=MUTED)

    intro = dark_table(1, 1)
    _run(intro.cell(0, 0).paragraphs[0], "Which event windows are live?", size=18, color=INK, bold=True, font="Arial")
    p = intro.cell(0, 0).add_paragraph()
    _run(
        p,
        "Top five merchandising events overlapping 1 Sep 2026–31 Dec 2026. "
        "Each card lists the event runtime and the ten catalog games to recommend. "
        "Console showcases keep first-party owned-studio games.",
        size=11,
        color=MUTED,
    )

    for index, event in enumerate(payload["events"], start=1):
        card = dark_table(1, 1)
        head = card.cell(0, 0).paragraphs[0]
        _run(head, f"#{index:02d}  {event['kind'].upper()}   ·   {event['status']}", size=9, color=CYAN, bold=True)
        name = card.cell(0, 0).add_paragraph()
        _run(name, event["name"], size=20, color=INK, bold=True, font="Arial")
        runtime = card.cell(0, 0).add_paragraph()
        _run(runtime, f"Event runtime  {event['runtime']}", size=13, color=AMBER, bold=True)
        meta = card.cell(0, 0).add_paragraph()
        _run(
            meta,
            f"{event['start']} → {event['end']}    ·    {event['location'] or event['country'] or 'Worldwide'}    ·    {event['mode'] or '—'}"
            + (f"    ·    {event['owner']}" if event["owner"] else ""),
            size=10,
            color=MUTED,
        )
        if event["image_path"]:
            pic = card.cell(0, 0).add_paragraph()
            run = pic.add_run()
            run.add_picture(str(event["image_path"]), width=Inches(1.4))

        games = dark_table(11, 4)
        headers = ("#", "Recommended game", "Release", "Platform")
        for col, label in enumerate(headers):
            _shade(games.cell(0, col), "12182A")
            para = games.cell(0, col).paragraphs[0]
            para.text = ""
            _run(para, label.upper(), size=8, color=CYAN, bold=True)
        for row_i, game in enumerate(event["games"], start=1):
            values = (f"{row_i:02d}", game["title"], game["release"], game["platform"] or "Multi")
            for col, value in enumerate(values):
                fill = "141A2C" if row_i % 2 else CARD
                _shade(games.cell(row_i, col), fill)
                para = games.cell(row_i, col).paragraphs[0]
                para.text = ""
                _run(para, value, size=10, color=INK, bold=col == 1)
                if game["image_path"] and col == 1:
                    try:
                        pic = games.cell(row_i, col).add_paragraph()
                        pic.add_run().add_picture(str(game["image_path"]), width=Inches(0.42))
                    except Exception:
                        pass

    note = dark_table(1, 1)
    _shade(note.cell(0, 0), BG)
    _run(
        note.cell(0, 0).paragraphs[0],
        f"Floor Brief · mapped products from the live catalog · {payload['as_of']}",
        size=9,
        color=MUTED,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


def main() -> None:
    payload = build_payload()
    html_path = DOCS / f"{STEM}.html"
    pdf_path = DOCS / f"{STEM}.pdf"
    docx_path = DOCS / f"{STEM}.docx"
    html_path.write_text(render_html(payload), encoding="utf-8")
    write_pdf(html_path, pdf_path)
    write_docx(payload, docx_path)
    DESKTOP.mkdir(parents=True, exist_ok=True)
    for src in (pdf_path, docx_path):
        shutil.copy2(src, DESKTOP / src.name)
    print(f"Wrote {pdf_path}")
    print(f"Wrote {docx_path}")
    print(f"Copied to {DESKTOP}")
    for event in payload["events"]:
        games = ", ".join(game["title"] for game in event["games"][:4])
        print(f"  {event['name']} [{event['runtime']}] → {games}")


if __name__ == "__main__":
    main()
