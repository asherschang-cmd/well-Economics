"""
refresh_all.py  —  run every data pull in one command

This is the orchestrator. Instead of running four scripts by hand, run this one
and it refreshes the whole data model: all three price streams, the STEO
forecast, and (if configured) rig count.

Run:  python -m data_pipeline.refresh_all
"""

from data_pipeline import pull_prices, pull_forecast


def run():
    print("=" * 60)
    print("REFRESHING WELL-ECONOMICS DATA MODEL")
    print("=" * 60)

    print("\n[1/2] Commodity prices (oil / gas / NGL)")
    pull_prices.run()

    print("\n[2/2] STEO forward price forecast")
    pull_forecast.run()

    # Rig count is optional / needs manual URL upkeep, so it's not in the
    # automatic refresh. Run `python -m data_pipeline.pull_rig_count` separately
    # once you've set its URL.

    print("\n" + "=" * 60)
    print("DONE. CSVs written locally and rows upserted to Supabase.")
    print("=" * 60)


if __name__ == "__main__":
    run()
