"""
assumptions.py  —  cost and fiscal inputs for the economics model

This is the last missing ingredient. The type curve gives volumes, the data
pipeline gives prices; this file supplies what it costs to drill and operate
the well, and how revenue is split (royalties, taxes). The cash-flow engine
imports these.

Every number here is a benchmark anchored to public Permian operator data
(2025-2026 vintage, e.g. Permian Resources quarterly reports). They're
deliberately in one place so you can stress-test by changing one value and
re-running. Sources noted inline.

Units matter a lot here — read the comments.
"""

# ===========================================================================
# CAPITAL COST (CapEx) — one-time cost to drill & complete the well
# ===========================================================================
# Public D&C is ~$700-775/lateral ft on a ~10,000 ft lateral (~$7-8M), plus
# facilities/tie-in and pre-drill. Base-case all-in ~$8.5M.
CAPEX_TOTAL = 8_500_000        # dollars, spent up front (month 0)

# ===========================================================================
# OPERATING COST (OpEx) — ongoing cost to run the well
# ===========================================================================
# Operators report cash operating cost per BOE (LOE + gathering/processing +
# G&A). Permian Resources ~ $7.50-8/BOE. We apply it per BOE produced.
OPEX_PER_BOE = 8.00            # dollars per barrel-of-oil-equivalent produced
# A small fixed monthly cost keeps late-life economics realistic (a well still
# costs something to keep open even at low rates).
OPEX_FIXED_MONTHLY = 3_000     # dollars per month

# ===========================================================================
# FISCAL TERMS — how gross revenue gets split before it reaches the operator
# ===========================================================================
# Net Revenue Interest: the operator's share after royalty. ~79% 8/8ths means
# a ~21% royalty burden goes to the mineral owner.
NRI = 0.79                     # fraction of gross revenue the operator keeps

# Texas severance (production) taxes — statutory rates.
SEV_TAX_OIL = 0.046            # 4.6% of oil revenue
SEV_TAX_GAS = 0.075            # 7.5% of gas revenue
SEV_TAX_NGL = 0.046            # NGL taxed as a liquid, ~oil rate

# ===========================================================================
# PRICE REALIZATIONS — how wellhead price relates to the benchmark
# ===========================================================================
# A well rarely gets the exact benchmark price. Oil realizes near WTI; gas
# realizes below Henry Hub (basis + processing); NGL is a fraction of WTI.
OIL_DIFFERENTIAL = 0.98        # oil realized = 98% of WTI
GAS_REALIZATION = 0.90         # gas realized = 90% of Henry Hub
# NGL barrel realized as a fraction of WTI (public: ~$24/bbl on ~$70 WTI).
NGL_PCT_OF_WTI = 0.34          # NGL $/bbl = 34% of WTI $/bbl

# ===========================================================================
# DISCOUNTING
# ===========================================================================
# 10% is the industry-standard discount rate ("PV-10"). NPV is the sum of
# monthly cash flows discounted back at this annual rate.
DISCOUNT_RATE_ANNUAL = 0.10

# ===========================================================================
# UNIT CONVERSIONS (so the three streams reconcile correctly)
# ===========================================================================
GAL_PER_BBL = 42               # NGL prices come in $/gallon; 42 gal = 1 bbl
MCF_PER_BOE = 6.0              # 6 mcf of gas = 1 barrel-of-oil-equivalent


def summary():
    print("ECONOMICS ASSUMPTIONS")
    print(f"  CapEx:            ${CAPEX_TOTAL:,.0f}")
    print(f"  OpEx:             ${OPEX_PER_BOE}/BOE + ${OPEX_FIXED_MONTHLY:,}/mo")
    print(f"  NRI:              {NRI:.0%}")
    print(f"  Severance tax:    oil {SEV_TAX_OIL:.1%} / gas {SEV_TAX_GAS:.1%}")
    print(f"  Realizations:     oil {OIL_DIFFERENTIAL:.0%} WTI, "
          f"gas {GAS_REALIZATION:.0%} HH, NGL {NGL_PCT_OF_WTI:.0%} WTI")
    print(f"  Discount rate:    {DISCOUNT_RATE_ANNUAL:.0%} (PV-10)")


if __name__ == "__main__":
    summary()
