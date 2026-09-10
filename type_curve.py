"""
type_curve.py  —  generate a Permian oil well production forecast (3-stream)

This produces the VOLUME half of the economics model. Your price data (EIA)
gives you $/barrel; this gives you how many barrels the well makes each month,
declining over time. Revenue = volume x price, so the model needs both.

It uses Arps decline-curve analysis — the industry-standard way to model how
an oil well's production falls off. A shale well comes on strong and drops ~70%
in the first year, then tapers to a long slow tail. This models that curve plus
the associated gas and NGL a Permian well produces alongside the oil.

WHAT COMES OUT:
  - a monthly forecast (oil, gas, NGL) for the life of the well
  - saved to production_forecast.csv
  - a printed summary including EUR (estimated ultimate recovery)

Run it:
    python type_curve.py

Defaults model a Midland Basin Wolfcamp A oil well (~10,000 ft lateral,
2020-2024 vintage). Change the ASSUMPTIONS block to model a different well.
"""

import numpy as np
import pandas as pd

# ===========================================================================
# ASSUMPTIONS  — the knobs. Everything below this block is math.
# ===========================================================================

# --- Oil decline (Arps) ---
QI_OIL_BBL_D    = 750    # initial oil rate, bbl/day (IP). Midland WCA ~730-800.
B_FACTOR        = 0.90   # hyperbolic exponent. Permian oil ~0.8-1.1.
EFF_DECLINE_YR1 = 0.70   # EFFECTIVE first-year decline (70% down). This is what
                         # public benchmarks quote. We convert it to the nominal
                         # Arps constant below — see note.
D_TERMINAL      = 0.12   # terminal decline (12%/yr). Curve switches hyperbolic
                         # -> exponential here so reserves don't run to infinity.

# --- Three-stream ratios (gas & NGL that come with the oil) ---
GOR_SCF_PER_BBL  = 2500  # gas-oil ratio: cubic feet of gas per barrel of oil.
NGL_BBL_PER_MMCF = 90    # NGL yield: barrels of NGL per million cubic feet of gas.

# --- Well life cutoffs ---
ECONOMIC_LIMIT_BBL_D = 15   # stop forecast when oil falls below this rate.
MAX_YEARS            = 35    # hard cap.

# ===========================================================================
# THE MATH
# ===========================================================================
#
# Arps hyperbolic rate at time t (years):
#     q(t) = qi / (1 + b*Di*t)^(1/b)
#
# IMPORTANT SUBTLETY (this is where amateur models go wrong):
# Benchmarks quote the *effective* first-year decline De (~70%): the actual
# fractional drop from month 0 to month 12. But the Arps formula uses a
# *nominal* decline constant Di, which is NOT the same number. You must convert:
#
#     De = 1 - (1 + b*Di)^(-1/b)   solved for Di:
#     Di = ((1 - De)^(-b) - 1) / b
#
# Skip this conversion and your decline is far too shallow, inflating EUR
# several-fold. (We learned that the hard way.)
#
# SECOND SUBTLETY (the "b-factor trap"): with b near 1, hyperbolic decline
# never really ends — the well mathematically produces forever and EUR becomes
# whatever year you stopped at. Real engineers switch to exponential decline at
# a fixed terminal rate (D_TERMINAL) once the hyperbolic decline slows to it.
# We do that switch below.

def nominal_di_from_effective(eff_decline, b):
    """Convert an effective annual decline (what benchmarks quote) to the
    nominal Arps decline constant the hyperbolic formula needs."""
    return ((1 - eff_decline) ** (-b) - 1) / b


def build_forecast():
    Di = nominal_di_from_effective(EFF_DECLINE_YR1, B_FACTOR)

    # Time (years) at which hyperbolic instantaneous decline slows to D_TERMINAL:
    #   D(t) = Di / (1 + b*Di*t)  ->  solve D(t) = D_terminal
    t_switch = (Di / D_TERMINAL - 1.0) / (B_FACTOR * Di)

    rows = []
    dt = 1.0 / 12.0
    q_switch = None

    for m in range(int(MAX_YEARS * 12)):
        t = m * dt
        if t <= t_switch:
            q_daily = QI_OIL_BBL_D / (1 + B_FACTOR * Di * t) ** (1 / B_FACTOR)
            q_switch = q_daily                       # rate as we cross the switch
        else:
            q_daily = q_switch * np.exp(-D_TERMINAL * (t - t_switch))

        if q_daily < ECONOMIC_LIMIT_BBL_D:
            break

        oil_month = q_daily * 30.4                                # bbl/month
        gas_month = oil_month * GOR_SCF_PER_BBL / 1000.0          # mcf/month
        ngl_month = (gas_month / 1000.0) * NGL_BBL_PER_MMCF       # bbl NGL/month

        rows.append({
            "month": m + 1,
            "year": round(t, 2),
            "oil_bbl_d": round(q_daily, 1),
            "oil_bbl": round(oil_month, 0),
            "gas_mcf": round(gas_month, 0),
            "ngl_bbl": round(ngl_month, 0),
        })

    return pd.DataFrame(rows)


def summarize(df):
    eur_oil = df["oil_bbl"].sum()
    eur_gas = df["gas_mcf"].sum()
    eur_ngl = df["ngl_bbl"].sum()
    eur_boe = eur_oil + eur_ngl + eur_gas / 6.0     # 6 mcf = 1 boe

    print("\n=== TYPE CURVE SUMMARY (Midland Wolfcamp A default) ===")
    print(f"  Well life:       {df['year'].max():.1f} years ({len(df)} months)")
    print(f"  Peak oil rate:   {df['oil_bbl_d'].max():,.0f} bbl/d")
    print(f"  Year-1 avg:      {df[df['year'] < 1]['oil_bbl_d'].mean():,.0f} bbl/d")
    print(f"  EUR oil:         {eur_oil/1000:,.0f} MBO  (thousand bbl oil)")
    print(f"  EUR gas:         {eur_gas/1000:,.0f} MMcf")
    print(f"  EUR NGL:         {eur_ngl/1000:,.0f} MBbl")
    print(f"  EUR total:       {eur_boe/1000:,.0f} MBOE")
    ok = 400 <= eur_oil / 1000 <= 700
    print(f"\n  Sanity check: Midland WCA oil EUR should be ~400-700 MBO -> "
          f"{'PASS' if ok else 'OUT OF RANGE'}")


if __name__ == "__main__":
    df = build_forecast()
    df.to_csv("production_forecast.csv", index=False)
    print(f"Saved {len(df)}-month forecast to production_forecast.csv")
    print("\nFirst 6 months:")
    print(df.head(6).to_string(index=False))
    print("\nLast 3 months (the tail):")
    print(df.tail(3).to_string(index=False))
    summarize(df)
