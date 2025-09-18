#!/usr/bin/env python3
"""
make_forecast_long.py

Transforms the simplified forecast into a long, analysis-ready table:

Columns:
  Date, Target, Channel, Quarter, Fcst_Actual, category

Rules:
1) ALL-CAPS lines in Column A start a new `category` block (category = snake_case of the text).
   - Special case: "TOTAL MEMBERSHIP SOLD" is treated as a data row (mapped to channel "Gross New Members Added"),
     not as a category header.
2) Column A content becomes `Channel` (with a few renames below).
3) For each requested quarter, the 1st two rows define:
   - Row 0 (per-quarter columns): "Fcst" or "Actual" for each month → `Fcst_Actual` values
   - Row 1 (per-quarter columns): Month labels like "Jul-25" → normalized to YYYY-MM → `Date`
4) You can pass multiple quarters via --quarters "Q3'25,Q4'25".
5) Includes ALL categories, not just "MEMBERSHIP SOLD" (e.g., TRIALS BREAKOUT, MEMBERSHIP TOTALS, etc.).

Usage:
python fpa_to_db/fpa_to_db.py \
  --in_csv "fpa_to_db/inputs/Simplified Q3'25 Fcst - Q3'25 Fcst.csv" \
  --quarters "Q3'25,Q4'25" \
  --out_csv "fpa_to_db/outputs/forecast_long_q3_q4_25.csv"
"""

import argparse
import re
from pathlib import Path
from datetime import datetime
import pandas as pd

CHANNEL_MAP = {
    # Map totals & key channels to names that will match db schema
    "TOTAL MEMBERSHIP SOLD":"Gross New Members Added",
    "Direct":"DTC Orders",
    "Trial Conversions":"Trial Conversions",
    "Wholesale":"Wholesale Orders",
    "Other":"Other Membership Orders",
}

# Treat this ALL-CAPS text as a data row, not a header
ALL_CAPS_DATA_ROWS = {"TOTAL MEMBERSHIP SOLD"}

def to_snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")

def month_to_yyyy_mm(s: str) -> str:
    s = s.strip()
    m = re.match(r"([A-Za-z]{3})[-/']?(\d{2,4})$", s)
    months = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12}
    if m:
        mon = months[m.group(1).lower()]
        yy = int(m.group(2))
        if yy < 100:
            yy = 2000 + yy
        return f"{yy}-{mon:02d}"
    return s

def is_all_caps_heading(s: str) -> bool:
    t = s.strip()
    if t in ALL_CAPS_DATA_ROWS:
        return False
    return t != "" and not any(ch.isdigit() for ch in t) and t == t.upper()

def extract_quarter(df: pd.DataFrame, quarter: str) -> pd.DataFrame:
    """
    Extracts one quarter's data across ALL categories.
    """
    label_col = df.columns[0]

    # quarter columns are the base header + .1 + .2
    cols = [quarter, f"{quarter}.1", f"{quarter}.2"]
    for c in cols:
        if c not in df.columns:
            raise ValueError(f"Expected column '{c}' not found in input.")

    # The top two rows (index 0 and 1) carry Fcst/Actual and Month labels
    header_fcst_actual = [df[c].iloc[0].strip() for c in cols]
    header_months = [df[c].iloc[1].strip() for c in cols]
    dates = [month_to_yyyy_mm(m) for m in header_months]
    quarter_norm = quarter.lower().replace("'", "_")

    records = []
    current_category = None

    for i in range(2, len(df)):
        label = str(df[label_col].iloc[i]).strip()

        # Start a new category on ALL CAPS headers
        if label and is_all_caps_heading(label):
            current_category = to_snake(label)
            # normalize "membership_sold" -> "memberships_sold" to match your earlier example
            if current_category == "membership_sold":
                current_category = "memberships_sold"
            continue

        # Skip if we haven't hit a category yet
        if current_category is None:
            continue

        # Read the three monthly values for this quarter
        row_vals = [str(df[c].iloc[i]).strip() for c in cols]

        # Skip empty/dash-only rows
        if all(v == "" or v == "-" for v in row_vals):
            continue

        # Skip one-off numeric lines as "labels" (stray calc lines)
        if label == "" or re.fullmatch(r"[-\d\.,%\s]+", label):
            continue

        # Map channel names if needed
        channel = CHANNEL_MAP.get(label, label)
        
        # Skip channels that equal "Other Membership Sold Breakout"
        if channel == "Other Membership Sold Breakout":
            continue

        # Emit one record per month
        for j, val in enumerate(row_vals):
            if val == "" or val == "-":
                continue
            # Fcst/Actual from header row 0
            fa = header_fcst_actual[j].strip().lower()
            if fa.startswith("fcst"):
                fa_norm = "forecast"
            elif fa.startswith("act"):
                fa_norm = "actual"
            else:
                fa_norm = fa or ""

            # Convert date string to proper datetime object (add -01 for first of month)
            date_str = dates[j] + "-01"
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Convert target to numeric value, removing any commas or formatting
            try:
                target_numeric = float(val.replace(',', '').replace('$', '').replace('%', ''))
            except (ValueError, AttributeError):
                # If conversion fails, skip this record
                continue

            records.append({
                "Date": date_obj,
                "Target": target_numeric,
                "Channel": channel,
                "Quarter": quarter_norm,
                "Fcst_Actual": fa_norm,
                "category": current_category,
            })

    return pd.DataFrame.from_records(records, columns=["Date","Target","Channel","Quarter","Fcst_Actual","category"])

def run(in_csv: Path, quarters: list[str], out_csv: Path) -> None:
    df = pd.read_csv(in_csv, dtype=str, keep_default_na=False)
    parts = []
    for q in quarters:
        part = extract_quarter(df, q)
        parts.append(part)
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["Date","Target","Channel","Quarter","Fcst_Actual","category"])
    out.to_csv(out_csv, index=False)
    print(f"Success ! Wrote {out_csv} with {len(out)} rows across quarters: {', '.join(quarters)}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_csv", required=True, help="Path to simplified forecast CSV")
    ap.add_argument("--quarters", required=True, help="Comma-separated quarter headers, e.g., \"Q3'25,Q4'25\"")
    ap.add_argument("--out_csv", required=True, help="Path to write the long-form CSV")
    args = ap.parse_args()
    quarters = [q.strip() for q in args.quarters.split(",") if q.strip()]
    run(Path(args.in_csv), quarters, Path(args.out_csv))

if __name__ == "__main__":
    main()
