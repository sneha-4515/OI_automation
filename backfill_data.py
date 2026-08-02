"""
backfill_data.py

Fetches and processes NSE combined-OI data for a RANGE of past days,
instead of just today. Use this once to populate history before you
started running run_daily.py, or any time you've missed a few days.

Examples
--------
# Backfill the last 30 calendar days (default)
python backfill_data.py

# Backfill the last 90 days
python backfill_data.py --days 90

# Backfill an explicit date range (inclusive, DD-MM-YYYY)
python backfill_data.py --start 01-01-2025 --end 31-01-2025

Notes
-----
- Weekends/holidays are skipped automatically: download_combined_oi()
  already returns None on days NSE didn't publish a file, and this
  script just logs and moves on.
- A small delay is added between requests so we don't hammer NSE.
- Already-downloaded days are skipped (see the `[skip]` messages) —
  safe to re-run/interrupt and resume.
- NSE's public archive typically only keeps a limited window of past
  files (commonly a year or so). Very old dates may simply come back
  empty — that's expected, not a bug.
"""

import argparse
import time
from datetime import datetime, timedelta

from fetch_nse_data import get_session, download_combined_oi
from process_data import process_and_store


def daterange(start: datetime, end: datetime):
    """Yield every calendar day from start to end, inclusive."""
    days = (end - start).days
    for i in range(days + 1):
        yield start + timedelta(days=i)


def backfill(start: datetime, end: datetime, delay_seconds: float = 1.5):
    session = get_session()

    total = (end - start).days + 1
    ok, skipped_weekend, no_file, failed = 0, 0, 0, 0

    for i, day in enumerate(daterange(start, end), start=1):
        label = day.strftime("%d-%b-%Y (%a)")

        if day.weekday() >= 5:  # Sat/Sun — NSE never publishes on these
            print(f"[{i}/{total}] {label} -> skipped (weekend)")
            skipped_weekend += 1
            continue

        print(f"[{i}/{total}] {label} -> fetching...")
        try:
            csv_path = download_combined_oi(day, session=session)
        except Exception as e:
            print(f"[{i}/{total}] {label} -> ERROR downloading: {e}")
            failed += 1
            time.sleep(delay_seconds)
            continue

        if csv_path is None:
            print(f"[{i}/{total}] {label} -> no file published (holiday?)")
            no_file += 1
            time.sleep(delay_seconds)
            continue

        try:
            process_and_store(csv_path)
            ok += 1
        except Exception as e:
            print(f"[{i}/{total}] {label} -> ERROR processing: {e}")
            failed += 1

        time.sleep(delay_seconds)

    print("\n=== Backfill summary ===")
    print(f"  Processed successfully : {ok}")
    print(f"  Skipped (weekend)      : {skipped_weekend}")
    print(f"  No file (holiday etc.) : {no_file}")
    print(f"  Failed                 : {failed}")


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill NSE MWPL history for past days.")
    parser.add_argument(
        "--days", type=int, default=None,
        help="Backfill the last N calendar days up to and including today (default: 30 if no --start/--end given).",
    )
    parser.add_argument("--start", type=str, default=None, help="Start date, format DD-MM-YYYY")
    parser.add_argument("--end", type=str, default=None, help="End date, format DD-MM-YYYY (default: today)")
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="Seconds to wait between each day's request (default: 1.5)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    today = datetime.now()

    if args.start:
        start = datetime.strptime(args.start, "%d-%m-%Y")
        end = datetime.strptime(args.end, "%d-%m-%Y") if args.end else today
    else:
        days = args.days or 30
        start = today - timedelta(days=days - 1)
        end = today

    print(f"Backfilling from {start.strftime('%d-%b-%Y')} to {end.strftime('%d-%b-%Y')}...\n")
    backfill(start, end, delay_seconds=args.delay)


if __name__ == "__main__":
    main()
