# NSE MWPL Tracker Dashboard

Automatically tracks NSE's daily "Market Wide Position Limit" (MWPL) data,
computes % utilization for each symbol, and visualizes which stocks are
approaching or in the F&O ban period (>=95% of MWPL).

## Project structure

```
nse-mwpl-dashboard/
├── data/
│   ├── raw/            # daily downloaded zip/csv files land here
│   └── processed/      # mwpl_history.csv — the growing, de-duplicated dataset
├── scripts/
│   ├── fetch_nse_data.py   # downloads + extracts the daily NSE zip
│   ├── process_data.py     # computes OI%/FutOI% of MWPL, appends to history
│   ├── run_daily.py        # chains fetch -> process (use this for cron)
│   └── dashboard.py        # Streamlit app
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running manually

```bash
# Step 1: fetch + process today's file
python scripts/run_daily.py

# Step 2: launch the dashboard
streamlit run scripts/dashboard.py
```

## Automating the daily download

**Option A — cron (if self-hosting / running on your own machine or a VPS):**

```cron
0 19 * * 1-5 cd /path/to/nse-mwpl-dashboard && /path/to/venv/bin/python scripts/run_daily.py
```

**Option B — GitHub Actions (recommended for a portfolio project — free, and
gives you a visible CI history):** add `.github/workflows/daily.yml`:

```yaml
name: Daily NSE MWPL Fetch
on:
  schedule:
    - cron: "30 13 * * 1-5"   # 7:00 PM IST, weekdays (UTC time here)
  workflow_dispatch: {}

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python scripts/run_daily.py
      - run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add data/
          git commit -m "Daily MWPL data update $(date +%F)" || echo "No changes"
          git push
```

Deploy `dashboard.py` on **Streamlit Community Cloud** pointed at this repo,
and it will pick up the latest committed `data/processed/mwpl_history.csv`
each time GitHub Actions pushes a new day's data.

## Notes / things to verify before relying on this

- **Zip URL:** the URL pattern in `fetch_nse_data.py`
  (`ZIP_URL_TEMPLATE`) is based on NSE's known archive path structure. NSE
  occasionally reorganizes its archive URLs — if a download starts
  failing, open the sec-ban page in a browser, right-click the "Combined
  open interest across exchanges (.zip)" link, copy its address, and
  update the template.
- **Anti-bot protection:** NSE requires a warmed-up session (cookies from
  visiting the homepage first) or requests get a 403. This is handled in
  `get_session()`, but NSE has tightened this before (e.g. requiring
  additional headers or occasionally CAPTCHAs) — if downloads start
  failing outright, you may need a headless-browser fallback (e.g.
  Playwright) instead of plain `requests`.
- **Market holidays/weekends:** NSE won't publish a file — `run_daily.py`
  already handles this gracefully (skips processing, no error).
- **Historical backfill:** this pipeline only stores what it fetches going
  forward. If you want historical trend data before you started running
  it, NSE's archives page also hosts past days' files — you can loop
  `download_combined_oi()` over a date range to backfill.
