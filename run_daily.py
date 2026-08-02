"""
run_daily.py

Single entry point to run the full daily pipeline:
  1. Download today's combined OI file from NSE
  2. Process it and append to the historical store

Intended to be triggered by cron / GitHub Actions scheduled workflow, e.g.:

    0 19 * * 1-5  cd /path/to/nse-mwpl-dashboard && python scripts/run_daily.py

(7 PM IST on weekdays, after NSE typically publishes the file — adjust
after observing actual publish times.)
"""

from datetime import datetime

from fetch_nse_data import get_session, download_combined_oi
from process_data import process_and_store


def main():
    today = datetime.now()
    session = get_session()
    csv_path = download_combined_oi(today, session=session)

    if csv_path is None:
        print("[info] Nothing to process today (no file published — market holiday?)")
        return

    process_and_store(csv_path)


if __name__ == "__main__":
    main()
