# RAG Prediction Game Project

Predict demand around physical/digital gaming events and cross-media entertainment releases, time promotions to those windows, and rank **what to merchandise today** from live search trends.

The live database is checked **daily** against Wikipedia product/event pages and Wikidata, covering **2026 through 2030**. New announcements are added; existing rows are overwritten with extra metadata. Future year-wide rows remain labeled as planning windows rather than confirmed dates.

Coverage includes:

- global and regional expos, conventions, conferences, game jams, esports, showcases, sales, festivals, and platform/publisher broadcasts
- physical, digital, and hybrid attendance modes
- theatrical film, broadcast/streaming TV, animation, anime, audio drama/podcasts, reality TV, and live-stage/concert formats
- announced-but-unreleased products (dated and TBA), with release windows written into the event calendar
- franchise-normalized correlations: `Spider Man 2`, `Spider-Man 2`, and `Spiderman 2` all connect to **Spider-Man: Brand New Day**

```bash
python3 -m src.database          # refresh product + event pages now
python3 -m src.daily_brief --refresh   # datasets + audits + RAG retrain + trends
bash scripts/install_daily_job.sh      # macOS 08:15 daily automation
```

Daily `--refresh` rebuilds product/event/trend datasets, writes Excel sheets with
`source` + `entry_date` columns under `data/processed/sheets/`, audits delays /
cancellations / confirmation flips into `data/processed/daily/{date}/changes.json`,
and retrains the TF-IDF RAG index under `data/processed/rag/`.

## Floor Brief

| Surface | How to run |
| --- | --- |
| Website | `python3 -m apps` → http://127.0.0.1:8765 |
| Native desktop | `python3 -m apps.desktop` |
| Native builds | `bash scripts/build_desktop.sh` (Mac) |

- **Product page:** catalog + announced/unreleased titles + promotions + trends + cross-media + related events.
- **Event page:** filters, confirmation status, mapped products including announced titles, and related media.
- **Cross-sell page:** enter an event name → games and attach products to merchandise in that timeframe (notebook 04).
- **Calendar page:** enter a month/year range → overlapping events with promote / cross-sell products (notebook 05). A date-accuracy filter keeps confirmed days and month windows in front of quarter/year placeholders.
- **Trends / Traffic:** filtered Google/Wikipedia signals plus country-wise product/event
  placement for US, UK, Germany, Japan, Brazil, and Australia. The market selector translates
  the shared web/desktop UI into English, German, Japanese, or Brazilian Portuguese.
- **Analyst dashboard:** announced products, event/product correlations, formats, attendance modes, and trends.

## Notebooks

1. `notebooks/01_explore_datasets.ipynb` — catalog + live calendar
2. `notebooks/02_promotion_strategies.ipynb` — equivalent-event promotion plans
3. `notebooks/03_daily_trend_priorities.ipynb` — daily Google Trends / Wikipedia ranking
4. `notebooks/04_event_cross_sell.ipynb` — enter an event → cross-sell games/products for that window
5. `notebooks/05_date_range_calendar.ipynb` — month/year range → events + promote/cross-sell products
6. Floor Brief GUI — product, event, cross-sell, calendar, trends, traffic, and dashboard in one desk

## Dates and artwork

Every stored date carries a precision (`day`, `month`, `quarter`, `year`) plus the window it
really covers, so a "September 2026" announcement matches a September search and displays as
*September 2026* rather than a 31 December stub. `src/dates.py` owns that logic; datasets keep
`runtime_start` / `runtime_end` for events and `release_start` / `release_end` for products.

High-value titles and tentpole events are pinned in `src/official_dates.py` from publisher /
organizer sources (Rockstar, Capcom, PlayStation, Nintendo, Xbox/Playground, Pearl Abyss,
thegameawards.com, gamescom.global, TGS CESA, etc.). Those overrides beat stale Wikipedia
scrapes and horizon planning templates on every rebuild, and are also re-applied when the
store loads so the UI never shows a superseded date. Daily audits in `src/audit_changes.py`
detect delays, advances, cancellations, and unconfirmed→confirmed flips. Every product and
event row carries `source` and `entry_date` (first seen) in CSV/Excel exports under
`data/processed/sheets/` and on the product/event pages. The catalog loader drops corrupt
storefront stamps (e.g. years before 1971). Rows resolved from a pinned source carry an
`official_source` note that the web/app render as a green "✓ Verified date" badge.

Cover art comes from Wikipedia/Wikimedia and is cached under `data/processed/live/artwork/`.
Anything without a page picture falls back to a title-stamped placeholder, and the web/app
layer swaps in a bundled SVG if an image ever fails to load — no blank tiles.
