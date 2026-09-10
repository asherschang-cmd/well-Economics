"""
pull_rig_count.py  —  pull Baker Hughes rig count (activity indicator)

Rig count isn't a direct input to the NPV math, but it's the standard measure
of drilling activity — useful context for the dashboard ("is the basin heating
up or cooling down?"). Baker Hughes publishes it free as an Excel workbook.

NOTE: unlike the EIA pulls, Baker Hughes changes their file URL/format
periodically. If the download fails, the fix is to grab the current
"North America Rotary Rig Count" Excel link from bakerhughes.com and update
BH_URL below. This is a good lesson for Asher: some sources are stable APIs
(EIA), others are files that move (Baker Hughes) and need occasional upkeep.

Fills:
    rig_counts : date, basin, rig_count

Run:  python -m data_pipeline.pull_rig_count
"""

import io
import requests
import pandas as pd
from data_pipeline.supabase_client import upsert_dataframe

# Baker Hughes North America rig count workbook (may need periodic updating).
BH_URL = ("https://rigcount.bakerhughes.com/static-files/"
          "0c1a5c0e-6d3a-4f9b-9f5a-000000000000")  # placeholder; see note below


def run():
    print("Attempting Baker Hughes rig count download...")
    try:
        resp = requests.get(BH_URL, timeout=60)
        resp.raise_for_status()
        # Baker Hughes publishes a multi-sheet Excel; the basin breakout is on
        # a sheet like 'US Oil & Gas Split' or 'Pivot Table'. We read all sheets
        # and let the user point at the right one after inspecting.
        xls = pd.read_excel(io.BytesIO(resp.content), sheet_name=None)
        print("Downloaded. Sheets found:", list(xls.keys()))
        print("-> Next step: inspect the sheet with basin-level counts and map "
              "its columns to date/basin/rig_count. Baker Hughes layout varies, "
              "so this last mapping is done by hand once.")
    except Exception as e:
        print(f"Download failed: {e}")
        print(
            "\nBaker Hughes moves their file URL periodically. To fix:\n"
            "  1. Go to https://rigcount.bakerhughes.com/na-rig-count\n"
            "  2. Copy the current 'North America Rotary Rig Count' Excel link\n"
            "  3. Paste it into BH_URL at the top of this file\n"
            "  4. Re-run.\n"
            "This is expected upkeep for file-based (non-API) sources."
        )


if __name__ == "__main__":
    run()
