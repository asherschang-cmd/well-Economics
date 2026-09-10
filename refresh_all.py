 """
refresh_all.py  —  run every data pull in one command
The orchestrator. Refreshes the whole data model: all three price streams and
the STEO forecast. Each stage is isolated — if prices have a partial failure,
the forecast still runs.
Run:  python -m data_pipeline.refresh_all
"""
from data_pipeline import pull_prices, pull_forecast
def run():
    print("=" * 60)
    print("REFRESHING WELL-ECONOMICS DATA MODEL")
    print("=" * 60)
    print("\n[1/2] Commodity prices (oil / gas / NGL)")
    try:
        pull_prices.run()
    except Exception as e:
        print(f"  price stage error: {e}")
    print("\n[2/2] STEO forward price forecast")
    try:
        pull_forecast.run()
    except Exception as e:
        print(f"  forecast stage error: {e}")
    print("\n" + "=" * 60)
    print("DONE. CSVs written locally and rows upserted to Supabase.")
    print("Rig count runs separately: python -m data_pipeline.pull_rig_count")
    print("=" * 60)
if __name__ == "__main__":
    run()
