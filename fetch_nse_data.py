"""
fetch_nse_data.py

Downloads the daily "Combined Open Interest across exchanges" zip file
from the NSE risk-management page and extracts the CSV inside it.

NSE blocks bare requests (no session/cookies) with a 403. The trick is:
  1. Hit the NSE homepage first with browser-like headers to establish a
     session and pick up cookies.
  2. Reuse that same session (headers + cookies) to request the zip file.

Run this daily (e.g. via cron / GitHub Actions) after NSE publishes the
file (typically evening, after market close).
"""

import os
import re
import zipfile
import io
from datetime import datetime

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
NSE_HOME_URL = "https://www.nseindia.com"
NSE_SEC_BAN_PAGE = (
    "https://www.nseindia.com/static/products-services/"
    "equity-derivatives-risk-management-sec-ban"
)
# The zip's URL pattern has moved around historically. If this stops
# working, open the sec-ban page in a browser, inspect the "Combined open
# interest across exchanges (.zip)" link, and update ZIP_URL_TEMPLATE below.
ZIP_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/archives/nsccl/mwpl/combineoi_{date_str}.zip"
)

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": NSE_SEC_BAN_PAGE,
}


def get_session() -> requests.Session:
    """Establish a session with NSE by visiting the homepage & sec-ban page first."""
    session = requests.Session()
    session.headers.update(HEADERS)

    # Warm up cookies
    session.get(NSE_HOME_URL, timeout=10)
    session.get(NSE_SEC_BAN_PAGE, timeout=10)

    return session


def download_combined_oi(date: datetime, session: requests.Session = None) -> str:
    """
    Download and extract the combined OI CSV for a given date.
    Returns the path to the extracted CSV file, or None if not available
    (e.g. weekends/holidays when NSE doesn't publish a file).
    """
    date_str = date.strftime("%d%m%Y")
    zip_url = ZIP_URL_TEMPLATE.format(date_str=date_str)

    os.makedirs(RAW_DIR, exist_ok=True)
    zip_path = os.path.join(RAW_DIR, f"combineoi_{date_str}.zip")
    csv_path = os.path.join(RAW_DIR, f"combineoi_{date_str}.csv")

    # Skip if already downloaded
    if os.path.exists(csv_path):
        print(f"[skip] {csv_path} already exists")
        return csv_path

    session = session or get_session()

    resp = session.get(zip_url, timeout=15)
    if resp.status_code != 200 or "zip" not in resp.headers.get("Content-Type", ""):
        print(f"[warn] No file available for {date_str} (status {resp.status_code})")
        return None

    with open(zip_path, "wb") as f:
        f.write(resp.content)

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # Extract whatever CSV is inside, rename to our expected path
        inner_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not inner_names:
            print(f"[warn] No CSV found inside {zip_path}")
            return None
        with zf.open(inner_names[0]) as src, open(csv_path, "wb") as dst:
            dst.write(src.read())

    print(f"[ok] Downloaded and extracted -> {csv_path}")
    return csv_path


if __name__ == "__main__":
    today = datetime.now()
    session = get_session()
    download_combined_oi(today, session=session)
