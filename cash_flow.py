"""
cash_flow.py  —  the economics engine: NPV, IRR, breakeven

This is the payoff. It combines everything:
    production (type_curve.py)  x  prices  -  costs (assumptions.py)
    -> monthly cash flow -> NPV, IRR, and breakeven WTI price.

It runs a single flat-price scenario by default (one WTI, one gas, one NGL
price held constant), which is how analysts pressure-test a well: "at $70 oil,
does this well make money, and how much?"

    python cash_flow.py                  # base case at default prices
    python cash_flow.py --wti 60         # stress at $60 oil

The three key outputs:
  NPV       - net present value: today's-dollars profit after every cost.
              Positive = value-creating. Uses a 10% discount rate (PV-10).
  IRR       - internal rate of return: the annualized % return of the
              investment. Compare against a hurdle rate (~15-20%).
  Breakeven - the WTI oil price at which NPV = 0. Below it the well loses money.
"""

import argparse
import numpy as np
import pandas as pd

import assumptions as A


def build_cash_flow(production_csv, wti, hh_gas, run_quiet=False):
    """
    Given a production forecast and flat prices, compute the monthly cash flow.
    wti     : flat WTI oil price ($/bbl)
    hh_gas  : flat Henry Hub gas price ($/MMBtu ~ $/mcf for our purposes)
    Returns the monthly DataFrame with a 'cash_flow' column.
    """
    prod = pd.read_csv(production_csv)

    # --- realized prices per unit (apply differentials & conversions) ------
    oil_price = wti * A.OIL_DIFFERENTIAL                 # $/bbl
    gas_price = hh_gas * A.GAS_REALIZATION               # $/mcf
    ngl_price_bbl = wti * A.NGL_PCT_OF_WTI               # $/bbl (fraction of WTI)

    # --- gross revenue per month, by stream --------------------------------
    prod["oil_rev"] = prod["oil_bbl"] * oil_price
    prod["gas_rev"] = prod["gas_mcf"] * gas_price
    prod["ngl_rev"] = prod["ngl_bbl"] * ngl_price_bbl    # ngl_bbl already in bbl
    prod["gross_rev"] = prod["oil_rev"] + prod["gas_rev"] + prod["ngl_rev"]

    # --- net revenue after royalty (NRI) -----------------------------------
    prod["net_rev"] = prod["gross_rev"] * A.NRI

    # --- severance taxes (on the operator's net revenue, by stream) --------
    prod["sev_tax"] = A.NRI * (
        prod["oil_rev"] * A.SEV_TAX_OIL
        + prod["gas_rev"] * A.SEV_TAX_GAS
        + prod["ngl_rev"] * A.SEV_TAX_NGL
    )

    # --- operating costs ---------------------------------------------------
    # BOE for per-BOE opex: oil + ngl + gas/6
    prod["boe"] = prod["oil_bbl"] + prod["ngl_bbl"] + prod["gas_mcf"] / A.MCF_PER_BOE
    prod["opex"] = prod["boe"] * A.OPEX_PER_BOE + A.OPEX_FIXED_MONTHLY

    # --- monthly cash flow (before CapEx) ----------------------------------
    prod["cash_flow"] = prod["net_rev"] - prod["sev_tax"] - prod["opex"]

    return prod


def compute_npv(monthly_cf, capex, annual_rate):
    """NPV = -CapEx + sum of monthly cash flows discounted at the monthly rate."""
    monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
    months = np.arange(1, len(monthly_cf) + 1)
    discounted = monthly_cf.values / (1 + monthly_rate) ** months
    return -capex + discounted.sum()


def compute_irr(monthly_cf, capex):
    """
    IRR = the annual rate where NPV = 0. We solve for the monthly rate that
    zeroes the cash-flow stream (CapEx at month 0), then annualize it.
    """
    cash = np.concatenate([[-capex], monthly_cf.values])

    def npv_at(monthly_rate):
        t = np.arange(len(cash))
        with np.errstate(over="ignore", divide="ignore"):
            return np.sum(cash / (1 + monthly_rate) ** t)

    # bisection between a safe lower bound and a high monthly rate
    lo, hi = -0.95, 1.0
    if npv_at(lo) * npv_at(hi) > 0:
        return None  # no sign change -> IRR undefined (well never pays back or always profitable)
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv_at(mid) > 0:
            lo = mid
        else:
            hi = mid
    monthly_irr = (lo + hi) / 2
    return (1 + monthly_irr) ** 12 - 1   # annualize


def compute_breakeven_wti(production_csv, hh_gas, capex, annual_rate):
    """Find the WTI price at which NPV = 0, by bisection."""
    def npv_at_wti(wti):
        cf = build_cash_flow(production_csv, wti, hh_gas, run_quiet=True)
        return compute_npv(cf["cash_flow"], capex, annual_rate)

    lo, hi = 10.0, 200.0
    if npv_at_wti(lo) > 0:
        return lo   # profitable even at $10
    if npv_at_wti(hi) < 0:
        return None  # unprofitable even at $200
    for _ in range(100):
        mid = (lo + hi) / 2
        if npv_at_wti(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def run(production_csv="production_forecast.csv", wti=70.0, hh_gas=3.50):
    cf = build_cash_flow(production_csv, wti, hh_gas)

    npv = compute_npv(cf["cash_flow"], A.CAPEX_TOTAL, A.DISCOUNT_RATE_ANNUAL)
    irr = compute_irr(cf["cash_flow"], A.CAPEX_TOTAL)
    breakeven = compute_breakeven_wti(production_csv, hh_gas,
                                      A.CAPEX_TOTAL, A.DISCOUNT_RATE_ANNUAL)

    # payback month: first month cumulative cash flow exceeds CapEx
    cum = cf["cash_flow"].cumsum()
    payback_idx = (cum >= A.CAPEX_TOTAL).idxmax() if (cum >= A.CAPEX_TOTAL).any() else None
    payback_months = int(cf.loc[payback_idx, "month"]) if payback_idx is not None else None

    print("=" * 55)
    print(f"WELL ECONOMICS  (WTI=${wti:.0f}, HH gas=${hh_gas:.2f})")
    print("=" * 55)
    print(f"  Gross revenue (life):  ${cf['gross_rev'].sum()/1e6:,.1f} MM")
    print(f"  Net revenue (life):    ${cf['net_rev'].sum()/1e6:,.1f} MM")
    print(f"  Total opex (life):     ${cf['opex'].sum()/1e6:,.1f} MM")
    print(f"  CapEx:                 ${A.CAPEX_TOTAL/1e6:,.1f} MM")
    print("-" * 55)
    print(f"  NPV (PV-10):           ${npv/1e6:,.2f} MM")
    print(f"  IRR:                   {irr*100:,.0f}%" if irr else "  IRR: n/a")
    print(f"  Breakeven WTI:         ${breakeven:,.0f}/bbl" if breakeven else "  Breakeven: n/a")
    print(f"  Payback:               {payback_months} months" if payback_months else "  Payback: never")
    print("=" * 55)

    # sanity check
    print("\n  Sanity: a Permian well at $70 WTI should be economic")
    print(f"          (positive NPV, IRR ~20-80%, breakeven ~$35-55).")
    return {"npv": npv, "irr": irr, "breakeven": breakeven}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--wti", type=float, default=70.0)
    p.add_argument("--gas", type=float, default=3.50)
    p.add_argument("--prod", type=str, default="production_forecast.csv")
    args = p.parse_args()
    run(args.prod, args.wti, args.gas)
