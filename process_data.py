"""
process_data.py

Reads a daily combined-OI CSV (as downloaded by fetch_nse_data.py),
computes % of MWPL utilization, and appends the result into a single
growing historical store (data/processed/mwpl_history.csv) so the
dashboard can plot day-wise trends.

Safe to re-run: rows for a (Date, NSE Symbol) that already exist in the
history are not duplicated.
"""

import os
import pandas as pd

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
HISTORY_PATH = os.path.join(PROCESSED_DIR, "mwpl_history.csv")

BAN_THRESHOLD_PCT = 95.0


def process_file(csv_path: str) -> pd.DataFrame:
    """Load one day's raw CSV and compute derived MWPL% columns."""
    df = pd.read_csv(csv_path)

    # Normalize column names (NSE has changed casing/spacing before)
    df.columns = [c.strip() for c in df.columns]
    rename_map = {
        "Date": "Date",
        "NSE Symbol": "NSE_Symbol",
        "MWPL": "MWPL",
        "Open Interest": "Open_Interest",
        "Future Equivalent Open Interest": "Future_Equivalent_OI",
        "Limit for Next Day": "Limit_For_Next_Day",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

    # Guard against divide-by-zero / missing MWPL
    df["MWPL"] = pd.to_numeric(df["MWPL"], errors="coerce")
    df["Open_Interest"] = pd.to_numeric(df["Open_Interest"], errors="coerce")
    df["Future_Equivalent_OI"] = pd.to_numeric(
        df.get("Future_Equivalent_OI"), errors="coerce"
    )

    df["OI_pct_MWPL"] = (df["Open_Interest"] / df["MWPL"] * 100).round(2)
    df["FutOI_pct_MWPL"] = (df["Future_Equivalent_OI"] / df["MWPL"] * 100).round(2)
    df["Ban_Flag"] = df["OI_pct_MWPL"] >= BAN_THRESHOLD_PCT

    keep_cols = [
        "Date",
        "NSE_Symbol",
        "MWPL",
        "Open_Interest",
        "Future_Equivalent_OI",
        "OI_pct_MWPL",
        "FutOI_pct_MWPL",
        "Ban_Flag",
    ]
    return df[[c for c in keep_cols if c in df.columns]]


def append_to_history(new_df: pd.DataFrame) -> pd.DataFrame:
    """Append new_df to the running history file, de-duplicated on (Date, Symbol)."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    if os.path.exists(HISTORY_PATH):
        history = pd.read_csv(HISTORY_PATH, parse_dates=["Date"])
        combined = pd.concat([history, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["Date", "NSE_Symbol"], keep="last")
    else:
        combined = new_df

    combined = combined.sort_values(["Date", "NSE_Symbol"])
    combined.to_csv(HISTORY_PATH, index=False)
    print(f"[ok] History updated -> {HISTORY_PATH} ({len(combined)} total rows)")
    return combined


def process_and_store(csv_path: str) -> pd.DataFrame:
    day_df = process_file(csv_path)
    return append_to_history(day_df)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python process_data.py <path_to_daily_csv>")
        sys.exit(1)

    process_and_store(sys.argv[1])
