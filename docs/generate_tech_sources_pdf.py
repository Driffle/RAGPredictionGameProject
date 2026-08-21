#!/usr/bin/env python3
"""Build the Floor Brief technology and dataset-sources PDF."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent / "FloorBrief_Technologies_and_Dataset_Sources.pdf"

NAVY = colors.HexColor("#0b1224")
INK = colors.HexColor("#1a2238")
MUTED = colors.HexColor("#4a5670")
CYAN = colors.HexColor("#1a8a90")
LINE = colors.HexColor("#d5dce8")
ROW = colors.HexColor("#f4f7fb")
WHITE = colors.white


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover_kicker": ParagraphStyle(
            "cover_kicker",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=CYAN,
            letterSpacing=1.4,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=17,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=NAVY,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            textColor=CYAN,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=7,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=INK,
            leftIndent=4,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=11,
            textColor=INK,
        ),
        "cell_h": ParagraphStyle(
            "cell_h",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=11,
            textColor=WHITE,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            textColor=MUTED,
            spaceAfter=10,
            spaceBefore=2,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }
    return s


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 14 * mm, A4[0], 14 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, A4[1] - 9 * mm, "Floor Brief  ·  Technologies and dataset sources")
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 9 * mm, "Website + macOS app  ·  19 Aug 2026")
    canvas.setFillColor(CYAN)
    canvas.rect(0, A4[1] - 14.8 * mm, A4[0], 1.6, fill=1, stroke=0)
    canvas.setFillColor(LINE)
    canvas.rect(0, 12 * mm, A4[0], 0.4, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 7 * mm, "Internal reference  ·  not a public license notice")
    canvas.drawRightString(A4[0] - 18 * mm, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def cover_header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 42 * mm, A4[0], 42 * mm, fill=1, stroke=0)
    canvas.setFillColor(CYAN)
    canvas.rect(0, A4[1] - 43.6 * mm, A4[0], 1.6, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(A4[0] / 2, A4[1] - 18 * mm, "FLOOR BRIEF")
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawCentredString(A4[0] / 2, A4[1] - 26 * mm, "Live merchandising desk  ·  2026–2030")
    canvas.setFillColor(LINE)
    canvas.rect(0, 12 * mm, A4[0], 0.4, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(A4[0] / 2, 7 * mm, "Prepared 19 August 2026  ·  API version 1.1.0")
    canvas.restoreState()


def P(text, style):
    return Paragraph(text, style)


def bullets(items, st):
    return ListFlowable(
        [ListItem(P(item, st["bullet"]), leftIndent=8, bulletColor=CYAN) for item in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
        bulletFontName="Helvetica",
        bulletFontSize=9,
        spaceBefore=2,
        spaceAfter=8,
    )


def table(headers, rows, st, col_widths):
    head = [P(h, st["cell_h"]) for h in headers]
    body = [[P(c, st["cell"]) for c in row] for row in rows]
    data = [head] + body
    t = Table(data, colWidths=col_widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ROW))
    t.setStyle(TableStyle(cmds))
    return t


def build():
    st = styles()
    story = []

    story.append(Spacer(1, 38 * mm))
    story.append(P("TECHNOLOGY AND DATASET SOURCES", st["cover_kicker"]))
    story.append(P("Floor Brief", st["cover_title"]))
    story.append(
        P(
            "A reference for the latest website and macOS app builds:<br/>"
            "what they run on, how they are packaged, and where every dataset comes from.",
            st["cover_sub"],
        )
    )
    story.append(Spacer(1, 10 * mm))
    meta = table(
        ["Item", "Value"],
        [
            ["Product", "Floor Brief (RAG Prediction Game Project)"],
            ["Surfaces described", "Website at http://127.0.0.1:8765 and FloorBrief.app (macOS)"],
            ["API version", "1.1.0  (FastAPI title Floor Brief)"],
            ["Website JS / CSS", "apps/web  ·  last edited 19 Aug 2026 16:47 IST"],
            ["macOS app bundle", "dist/FloorBrief.app and Desktop/FloorBrief.app  ·  built 19 Aug 2026 16:51 IST"],
            ["Live database as-of", "19 August 2026"],
            ["Horizon", "Planning calendar 2026–2030; GMV join 2022–2026"],
            ["This document", "19 August 2026"],
        ],
        st,
        [48 * mm, 124 * mm],
    )
    story.append(meta)
    story.append(
        P(
            "The website and the Mac app share one FastAPI application, one JavaScript desk, "
            "and the same live datasets. The Mac app is a native window around that website, not a second product.",
            st["caption"],
        )
    )

    story.append(PageBreak())
    story.append(P("1. What this version ships", st["h1"]))
    story.append(
        P(
            "Floor Brief is a merchandising desk. It answers what to promote today against a catalog of "
            "game products, a 2026–2030 event and entertainment calendar, live search-interest signals, "
            "and 2022–2026 order GMV. Retrieval uses a TF-IDF RAG index retrained whenever product and "
            "event datasets rebuild. Confirmed publisher and organizer dates override stale Wikipedia scrapes. "
            "Cover art comes from Wikipedia/Wikimedia with local SVG fallbacks so tiles are never blank.",
            st["body"],
        )
    )
    story.append(P("Website and Mac app pages", st["h2"]))
    story.append(
        table(
            ["Page", "What it does"],
            [
                ["Product", "Look up a catalog or announced title: promotions, trends, cover art, related events."],
                ["Event", "Open a calendar window with confirmation status, mapped SKUs, and related media."],
                ["Cross-sell", "Enter an event → games and attach products to merchandise in that runtime."],
                ["Calendar", "Month/year range → overlapping events with promote and cross-sell lists."],
                ["Trends", "Google Trends RSS topics ranked against merchandising priorities and art."],
                ["Traffic", "Search signals plus country-wise product and event placement."],
                ["Dashboard", "2022–2026 weekly GMV joined to franchise event runtimes, with year leaderboards."],
            ],
            st,
            [36 * mm, 136 * mm],
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        P(
            "Live snapshot on 19 Aug 2026: 1,139 events, 589 adaptations, 264 announced games, "
            "2,223 promotion plans, 2,092 artwork records, 59,808 RAG documents "
            "(55,857 product + 1,139 event + 589 adaptation + 2,223 promotion). "
            "Daily audits recorded 1,002 changes on that rebuild.",
            st["body"],
        )
    )

    story.append(P("2. Runtime architecture", st["h1"]))
    story.append(
        P(
            "One Python process serves HTML, CSS, JavaScript, artwork, and JSON APIs. "
            "The website binds 0.0.0.0:8765. The Mac app starts the same FastAPI app on a free "
            "localhost port, waits for /api/health, then opens a pywebview window at 1320×880.",
            st["body"],
        )
    )
    story.append(
        table(
            ["Layer", "Technology", "Role in this build"],
            [
                [
                    "Language",
                    "Python 3.12.10",
                    "API, datasets, RAG, desktop host, PyInstaller boot.",
                ],
                [
                    "HTTP API",
                    "FastAPI 0.141.1",
                    "REST under /api/* plus static mounts for /static and /media/artwork.",
                ],
                [
                    "ASGI server",
                    "Uvicorn 0.52.3",
                    "Website: python -m apps. Mac app: background thread in apps/desktop.py.",
                ],
                [
                    "CORS",
                    "Starlette CORSMiddleware",
                    "Allow-all origins so the local desk and webview can call the API.",
                ],
                [
                    "UI",
                    "HTML5 + CSS3 + vanilla JS",
                    "apps/web — no React/Vue. Tabs, search comboboxes, briefs, charts.",
                ],
                [
                    "Charts",
                    "Chart.js 4.4.1 (jsDelivr CDN)",
                    "Trends, traffic, and GMV dashboard canvases.",
                ],
                [
                    "Fonts",
                    "IBM Plex Sans + Syne",
                    "Loaded from Google Fonts; system sans-serif fallback.",
                ],
                [
                    "i18n",
                    "apps/web/js/i18n.js",
                    "Full copy in English, German, Japanese, Brazilian Portuguese; market picker for 43 geos + WW.",
                ],
                [
                    "Desktop shell",
                    "pywebview 6.2.1",
                    "Native macOS window (WKWebView) pointing at the local Uvicorn URL.",
                ],
                [
                    "Packaging",
                    "PyInstaller 6.22.1",
                    "scripts/build_desktop.sh → dist/FloorBrief.app (bundle id com.ragprediction.floorbrief).",
                ],
            ],
            st,
            [28 * mm, 48 * mm, 96 * mm],
        )
    )

    story.append(P("3. Data, retrieval, and analysis libraries", st["h1"]))
    story.append(
        table(
            ["Library", "Version", "Used for"],
            [
                ["pandas", "3.0.5", "Catalog/calendar wrangling in notebooks and some rebuild paths."],
                ["scikit-learn", "1.9.0", "TfidfVectorizer (1–2 grams, 50k features) and cosine similarity retrieval."],
                ["joblib", "1.5.3", "Persist and load data/processed/rag/tfidf_index.joblib."],
                ["openpyxl", "3.1.5", "Excel exports under data/processed/sheets/ (source + entry_date columns)."],
                ["odfpy / stdlib zip+XML", "1.4.1", "Read the ODS planning calendar; orders XLSX parsed via zip/XML."],
                ["python-dateutil", "2.9.0", "Date parsing around flexible Wikipedia and catalog stamps."],
                ["stdlib csv/json/xml", "—", "Catalog CSV, live JSON, Google Trends RSS, artwork metadata."],
            ],
            st,
            [38 * mm, 28 * mm, 106 * mm],
        )
    )
    story.append(P("Supporting tools (not in the shipped UI)", st["h2"]))
    story.append(
        bullets(
            [
                "Jupyter / ipykernel — notebooks 01–05 for exploration, promotion, trends, cross-sell, calendar.",
                "pytest — tests for orders, calendar dedupe, promote, geo, coverage, audits, trend filtering.",
                "macOS launchd (scripts/install_daily_job.sh) — daily 08:15 refresh of datasets, audits, RAG, and trends.",
                "curl fallback in src/http.py when system Python lacks CA certificates.",
            ],
            st,
        )
    )

    story.append(P("4. How the website and Mac app differ", st["h1"]))
    story.append(
        table(
            ["", "Website", "macOS FloorBrief.app"],
            [
                [
                    "Start",
                    "python -m apps  (host 0.0.0.0, port 8765)",
                    "Open FloorBrief.app, or python -m apps.desktop",
                ],
                [
                    "Process",
                    "Long-running Uvicorn in the project venv",
                    "Bundled Python + Uvicorn on an ephemeral 127.0.0.1 port",
                ],
                [
                    "UI",
                    "Browser at http://127.0.0.1:8765",
                    "pywebview window titled Floor Brief, min size 960×640",
                ],
                [
                    "Code",
                    "Live files under apps/web and src/",
                    "Frozen copy inside Contents/Resources (sys._MEIPASS)",
                ],
                [
                    "Data",
                    "data/processed on disk, refreshed in place",
                    "Datasets bundled at build time; in-app refresh still calls the same Python modules",
                ],
                [
                    "Health check",
                    "GET /api/health",
                    "Desktop waits up to ~45s for /api/health before showing the window",
                ],
            ],
            st,
            [28 * mm, 72 * mm, 72 * mm],
        )
    )
    story.append(
        P(
            "This Mac build includes the 19 Aug 2026 click/search fix (restored dateConfidenceBadge in app.js). "
            "Linux and Windows packaging were removed from the project.",
            st["caption"],
        )
    )

    story.append(P("5. Dataset sources", st["h1"]))
    story.append(
        P(
            "Every product and event row carries source, entry_date (first seen), and last_checked. "
            "Excel/CSV exports under data/processed/sheets/ keep those columns. "
            "Rows from a pinned publisher or organizer source show a green “Verified date” badge in the UI.",
            st["body"],
        )
    )

    story.append(P("5.1 First-party storefront and planning files", st["h2"]))
    story.append(
        table(
            ["Dataset", "File / origin", "How Floor Brief uses it"],
            [
                [
                    "Product catalog",
                    "data/raw/game_products.csv (gzip fallback). Original export: list_of_all_game_products_by_release_date (12 Aug 2026).",
                    "Storefront SKUs, platforms, types. Gift cards dropped. Corrupt dates before 1971 ignored. Live Wikipedia/Wikidata overlay announced titles.",
                ],
                [
                    "Events &amp; adaptations ODS",
                    "data/raw/events_and_adaptations.ods (fallback: RAGPredictionGameProjectDataset.ods on Desktop).",
                    "Seed industry calendar and IP adaptations. Source stamp: ods. Live Wikipedia/Wikidata/horizon rows overwrite or extend it.",
                ],
                [
                    "Orders GMV 2022–2026",
                    "data/raw/orders_2022_to_2026.xlsx (or Downloads export dated 18 Aug 2026).",
                    "Weekly GMV strings joined to franchise event runtimes. Dashboard period/year product and event leaderboards. Windows longer than 45 days are skipped.",
                ],
            ],
            st,
            [36 * mm, 62 * mm, 74 * mm],
        )
    )

    story.append(P("5.2 Open web APIs (no paid keys)", st["h2"]))
    story.append(
        table(
            ["Source", "Endpoint / pages", "What is taken"],
            [
                [
                    "English Wikipedia API",
                    "https://en.wikipedia.org/w/api.php  (parse wikitext; search)",
                    "Year pages YYYY_in_video_games (2022–2030) for major events and game-based films. List_of_video_games_released_in_YYYY and year pages for announced titles 2026–2030.",
                ],
                [
                    "Wikipedia REST summaries",
                    "https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
                    "Box art, posters, event logos. Search fallback when the storefront title ≠ article title.",
                ],
                [
                    "Wikidata SPARQL",
                    "https://query.wikidata.org/sparql",
                    "Video games (P31/P279* Q7889) with publication date P577 by year. Adaptations: works with P144 based on a video game. Limit 500 rows/year.",
                ],
                [
                    "Google Trends RSS",
                    "https://trends.google.com/trending/rss?geo={US,GB,DE,JP,BR,AU}",
                    "Daily trending search titles, approx_traffic, related news headlines. Geos: United States, UK, Germany, Japan, Brazil, Australia.",
                ],
                [
                    "Wikimedia Pageviews",
                    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/...",
                    "Last ~10 days of English Wikipedia user pageviews for a merchandising watchlist (Spider-Man, GTA, Zelda, Minecraft, etc.). Spike vs median baseline.",
                ],
            ],
            st,
            [40 * mm, 62 * mm, 70 * mm],
        )
    )
    story.append(
        P(
            "User-Agent: RAGPredictionGameProject/1.0 (local merchandising research; Wikimedia + Google Trends RSS). "
            "Wikimedia content is used under the projects’ published terms; this desk is an internal research tool.",
            st["caption"],
        )
    )

    story.append(P("5.3 Curated and generated layers", st["h2"]))
    story.append(
        table(
            ["Layer", "Module", "Source of truth"],
            [
                [
                    "Official date overrides",
                    "src/official_dates.py",
                    "Publisher/organizer pages beat Wikipedia and horizon templates. Re-applied on every store load.",
                ],
                [
                    "Historical registry",
                    "src/historical_calendar.py",
                    "Confirmed 2022–2026 runtimes for cons, showcases, sports, films, OTT. Stamp: historical_registry / Wikipedia year pages and organizer calendars.",
                ],
                [
                    "Horizon templates",
                    "src/horizon.py + src/coverage.py",
                    "Recurring 2026–2030 windows (CES, GDC, Gamescom, TGS, The Game Awards, sports seasons, esports). Live year-page dates overwrite these when confirmed.",
                ],
                [
                    "Announced titles",
                    "src/announced.py",
                    "Hand-maintained tentpoles with Wikipedia URLs (GTA VI, Witcher 4, Wolverine, Fable, Silksong, …) plus release-window events on the calendar.",
                ],
                [
                    "Cross-media extras",
                    "src/coverage.py",
                    "Example: Spider-Man: Brand New Day theatrical window from Sony Pictures (sonypictures.com).",
                ],
                [
                    "Geo placement",
                    "src/geo_placement.py",
                    "43 markets + worldwide inferred from event location/scope, not a third-party geo API.",
                ],
                [
                    "Calendar dedupe",
                    "src/calendar_dedupe.py",
                    "Merges “Gamescom” vs “Gamescom 2026”, overlapping entertainment titles, and near-duplicate windows. Distinct editions (e.g. Steam Next Fest Feb vs June) are kept.",
                ],
                [
                    "Promotion plans",
                    "src/promote.py",
                    "Maps every dated event to catalog/announced SKUs by franchise overlap and runtime. Confirmation kind: confirmed / tentative / cancelled (src/dates.py).",
                ],
                [
                    "Artwork cache",
                    "src/artwork.py → data/processed/live/artwork/",
                    "Wikimedia thumbs plus generated SVG placeholders. Web layer substitutes bundled SVG if a remote image fails.",
                ],
                [
                    "RAG corpus",
                    "src/documents.py → data/processed/rag/",
                    "JSONL documents for events, adaptations, products, promotion plans. Retrained on daily --refresh.",
                ],
            ],
            st,
            [40 * mm, 42 * mm, 90 * mm],
        )
    )

    story.append(P("6. Pinned official sources (verified-date badge)", st["h1"]))
    story.append(
        P(
            "These notes are stored on the row as official_source and win over scrapes. "
            "URLs below are the publishers’ or organizers’ public pages as recorded in src/official_dates.py.",
            st["body"],
        )
    )
    story.append(P("Products", st["h2"]))
    story.append(
        table(
            ["Title", "Recorded source"],
            [
                ["Grand Theft Auto VI", "Rockstar Games / Take-Two — rockstargames.com/VI"],
                ["Marvel’s Wolverine", "Marvel.com / PlayStation Store / Insomniac"],
                ["Resident Evil Requiem", "Capcom press release"],
                ["007 First Light", "IO Interactive support / 007.com"],
                ["Death Stranding 2: On the Beach", "Kojima Productions / PlayStation"],
                ["Mafia: The Old Country", "2K Newsroom"],
                ["Metroid Prime 4: Beyond", "Nintendo"],
                ["Hollow Knight: Silksong", "Team Cherry"],
                ["Ghost of Yōtei", "PlayStation Blog"],
                ["Monster Hunter Wilds", "Capcom"],
                ["DOOM: The Dark Ages", "Bethesda / id Software"],
                ["Fable (2027)", "Xbox / Playground Games"],
                ["Crimson Desert", "Pearl Abyss"],
                ["Forza Horizon 6", "Forza.net / Playground Games"],
            ],
            st,
            [70 * mm, 102 * mm],
        )
    )
    story.append(P("Tentpole events (2026 editions unless noted)", st["h2"]))
    story.append(
        table(
            ["Event", "Recorded source"],
            [
                ["The Game Awards 2026", "thegameawards.com — 10 Dec 2026"],
                ["Gamescom 2026", "gamescom.global / Koelnmesse — 26–30 Aug 2026"],
                ["Gamescom Opening Night Live", "gamescom.global — 25 Aug 2026"],
                ["Tokyo Game Show 2026", "tgs.cesa.or.jp — 17–21 Sep 2026"],
                ["Summer Game Fest 2026", "Wikipedia 2026 in video games / VGC — 5–8 Jun 2026"],
                ["Historical TGA / Gamescom / TGS / SGF 2022–2025", "English Wikipedia year pages (YYYY in video games) and event articles"],
            ],
            st,
            [70 * mm, 102 * mm],
        )
    )

    story.append(P("7. Source precedence", st["h1"]))
    story.append(
        P(
            "When two rows describe the same event or title, Floor Brief keeps the stronger source. "
            "Confirmed / known-cycle and historical_registry ranks sit at the top; horizon planning templates sit at the bottom.",
            st["body"],
        )
    )
    story.append(
        bullets(
            [
                "Official pinned dates (src/official_dates.py) always overwrite after merge.",
                "Rank (high → low): confirmed/known cycle and historical_registry → announced_registry → ODS seed → Wikipedia scrape → Wikidata → horizon_template.",
                "Wikipedia year-page dates replace horizon templates for that edition when the parse succeeds.",
                "Date precision is stored as day, month, quarter, or year (src/dates.py). A “September 2026” announcement is shown as September 2026, not a 31 Dec stub.",
                "Daily src/audit_changes.py flags delays, advances, cancellations, and unconfirmed→confirmed flips into data/processed/daily/{date}/changes.json.",
            ],
            st,
        )
    )

    story.append(P("8. Key URLs used at runtime", st["h1"]))
    story.append(
        table(
            ["Purpose", "URL"],
            [
                ["Wikipedia API", "https://en.wikipedia.org/w/api.php"],
                ["Wikipedia REST summary", "https://en.wikipedia.org/api/rest_v1/page/summary/"],
                ["Wikipedia year page pattern", "https://en.wikipedia.org/wiki/{year}_in_video_games"],
                ["Wikipedia release-list pattern", "https://en.wikipedia.org/wiki/List_of_video_games_released_in_{year}"],
                ["Wikidata Query Service", "https://query.wikidata.org/sparql"],
                ["Google Trends RSS", "https://trends.google.com/trending/rss?geo=XX"],
                ["Wikimedia pageviews", "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/..."],
                ["Chart.js CDN", "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"],
                ["Google Fonts", "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans&amp;family=Syne"],
                ["The Game Awards", "https://thegameawards.com"],
                ["Gamescom", "https://www.gamescom.global"],
                ["Tokyo Game Show", "https://tgs.cesa.or.jp"],
                ["GTA VI", "https://www.rockstargames.com/VI"],
            ],
            st,
            [52 * mm, 120 * mm],
        )
    )

    story.append(P("9. Build identifiers for this version", st["h1"]))
    story.append(
        table(
            ["Artifact", "Location / identifier"],
            [
                ["Website entry", "python -m apps  →  FastAPI + Uvicorn on port 8765"],
                ["Desktop entry", "python -m apps.desktop  or  FloorBrief.app"],
                ["macOS bundle id", "com.ragprediction.floorbrief"],
                ["PyInstaller spec", "packaging/floorbrief.spec"],
                ["Mac build script", "bash scripts/build_desktop.sh"],
                ["GitHub Actions", "macOS-only desktop workflow (.github/workflows/desktop-builds.yml)"],
                ["Live meta", "data/processed/live/meta.json  last_checked 2026-08-19"],
                ["Daily brief", "data/processed/daily/2026-08-19/"],
                ["GMV dashboard cache", "data/processed/order_dashboard.json"],
            ],
            st,
            [48 * mm, 124 * mm],
        )
    )
    story.append(
        P(
            "To refresh live Wikipedia/Wikidata/art/RAG: python -m src.database or python -m src.daily_brief --refresh. "
            "The website must be restarted after Python store changes (get_store is lru_cached). "
            "Static JS/CSS are served from disk and pick up on a hard refresh.",
            st["body"],
        )
    )

    story.append(P("10. Notes for readers", st["h1"]))
    story.append(
        bullets(
            [
                "This document describes the 19 August 2026 website and macOS builds. It is not a software license and does not grant redistribution rights to third-party data.",
                "Catalog and orders files are internal storefront extracts. Wikipedia, Wikidata, Wikimedia pageviews, and Google Trends RSS remain owned by their operators and subject to their terms.",
                "Pinned dates can still move; the daily audit is the change log. Do not treat a horizon template as a confirmed organizer date unless the confirmation badge says confirmed.",
                "Observed best-week GMV on the dashboard is not full-year GMV.",
                "Contact path for this project is the local Floor Brief desk in this repository.",
            ],
            st,
        )
    )
    story.append(Spacer(1, 8 * mm))
    story.append(
        P(
            "End of document  ·  Floor Brief  ·  Technologies and dataset sources  ·  19 August 2026",
            st["cover_sub"],
        )
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title="Floor Brief — Technologies and dataset sources",
        author="Floor Brief",
        subject="Website and macOS app stack, plus dataset sources as of 19 August 2026",
    )
    doc.build(story, onFirstPage=cover_header_footer, onLaterPages=header_footer)
    print(OUT)


if __name__ == "__main__":
    build()
