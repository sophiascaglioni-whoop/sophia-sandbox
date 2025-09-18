# README

This will convert the input a wide, Excel-format FP&A team forecast (exported as a .csv) into the output, a long-format table (also in .csv format) that we can use in lieu of an Airbyte connection to load the forecast into Sigma.

**this is probably a temporary solution**

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

Usage (in terminal zsh shell):
python fpa_to_db/fpa_to_db.py \
  --in_csv "fpa_to_db/inputs/Simplified Q3'25 Fcst - Q3'25 Fcst.csv" \
  --quarters "Q3'25,Q4'25" \
  --out_csv "fpa_to_db/outputs/forecast_long_q3_q4_25.csv"
"""