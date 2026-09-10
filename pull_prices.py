"""
pull_prices.py  —  pull all three commodity price streams from EIA

Fills three Supabase tables (and three CSVs):
    oil_prices  : WTI crude          ($/bbl)   series RWTC   route petroleum/pri/spt
    gas_prices  : Henry Hub gas      ($/MMBtu) series RNGWHHD route natural-gas/pri/fut
    ngl_prices  : Mont Belvieu C3    ($/gal)   series EPLLPA  route petroleum/pri/spt

Why these three: Asher's type curve is 3-stream (oil/gas/NGL), so the model
prices all three. Oil is the big driver; gas and NGL add the ~20-30% of Permian
revenue that oil-only models miss. NGL here uses Mont Belvieu propane as the
standard proxy for the NGL barrel.

Run:  python -m data_pipeline.pull_prices
"""

from datetime import date, timedelta
from data_pipeline.eia_client import fetch_eia_series
from data_pipeline.supabase_client import upsert_dataframe

# 10 years of history keeps it modelable without being unwieldy.
START = (date.today() - timedelta(days=365 * 10)).isoformat()

# Each entry: (table, csv, route, series, frequency, value column name)
STREAMS = [
    ("oil_prices", "oil_prices.csv", "petroleum/pri/spt",  "RWTC",    "weekly", "price"),
    ("gas_prices", "gas_prices.csv", "natural-gas/pri/fut", "RNGWHHD", "daily",  "price"),
    ("ngl_prices", "ngl_prices.csv", "petroleum/pri/spt",  "EPLLPA",  "weekly", "price"),
]


def run():
    for table, csv, route, series, freq, valcol in STREAMS:
        print(f"\nPulling {table} ({series})...")
        df = fetch_eia_series(route, series, frequency=freq, start=START,
                              value_name=valcol)
        # normalize column name to 'date' + 'price' for a consistent schema
        df = df.rename(columns={"date": "date"})
        df.to_csv(csv, index=False)
        print(f"  saved {len(df)} rows to {csv} "
              f"({df['date'].min()} -> {df['date'].max()})")
        try:
            n = upsert_dataframe(table, df, conflict_column="date")
            print(f"  wrote {n} rows to Supabase table '{table}'")
        except Exception as e:
            print(f"  (Supabase write skipped: {e})")
            print(f"  -> create table '{table}' with columns date (text, UNIQUE), "
                  f"price (float8), RLS off, then re-run.")


if __name__ == "__main__":
    run()
