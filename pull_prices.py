"""
pull_prices.py  —  pull all three commodity price streams from EIA

Fills three Supabase tables (and three CSVs):
    oil_prices  : WTI crude       ($/bbl)   series RWTC
    gas_prices  : Henry Hub gas   ($/MMBtu) series RNGWHHD
    ngl_prices  : Mont Belvieu C3 ($/gal)   series EER_EPLLPA_PF4_Y44MB_DPG

Why these three: Asher's type curve is 3-stream (oil/gas/NGL), so the model
prices all three. Oil is the big driver; gas and NGL add the ~20-30% of Permian
revenue that oil-only models miss. NGL here uses Mont Belvieu propane as the
standard proxy for the NGL barrel.

Each stream is pulled independently: if one fails (bad series id, EIA hiccup),
the others still run. We report a summary at the end.

Run:  python -m data_pipeline.pull_prices
"""

from datetime import date, timedelta
from data_pipeline.eia_client import fetch_eia_series
from data_pipeline.supabase_client import upsert_dataframe

START = (date.today() - timedelta(days=365 * 10)).isoformat()

# (table, csv, route, series, frequency, value column)
STREAMS = [
    ("oil_prices", "oil_prices.csv", "petroleum/pri/spt",   "RWTC",    "weekly", "price"),
    ("gas_prices", "gas_prices.csv", "natural-gas/pri/fut", "RNGWHHD", "daily",  "price"),
    ("ngl_prices", "ngl_prices.csv", "petroleum/pri/spt",   "EER_EPLLPA_PF4_Y44MB_DPG", "weekly", "price"),
]


def run():
    results = []
    for table, csv, route, series, freq, valcol in STREAMS:
        print(f"\nPulling {table} ({series})...")
        try:
            df = fetch_eia_series(route, series, frequency=freq, start=START,
                                  value_name=valcol)
        except SystemExit as e:
            # one bad stream shouldn't stop the others
            print(f"  FAILED: {e}")
            results.append((table, "FAILED", 0))
            continue

        df.to_csv(csv, index=False)
        print(f"  saved {len(df)} rows to {csv} "
              f"({df['date'].min()} -> {df['date'].max()})")
        try:
            n = upsert_dataframe(table, df, conflict_column="date")
            print(f"  wrote {n} rows to Supabase table '{table}'")
            results.append((table, "OK", n))
        except Exception as e:
            print(f"  (Supabase write skipped: {e})")
            print(f"  -> create table '{table}' with columns date (text, UNIQUE), "
                  f"price (float8), RLS off, then re-run.")
            results.append((table, "CSV only", len(df)))

    print("\n--- price pull summary ---")
    for table, status, n in results:
        print(f"  {table:12} {status:10} {n} rows")
    return results


if __name__ == "__main__":
    run()
