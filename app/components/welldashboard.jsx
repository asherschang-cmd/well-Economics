"use client";

import { useState, useEffect, useMemo } from "react";
import { createClient } from "@supabase/supabase-js";
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine,
} from "recharts";

/* ============================================================================
   CONFIG — mirrors assumptions.py. Keep these in sync with the Python model.
   ============================================================================ */
const CONFIG = {
  // type curve (Midland Wolfcamp A default, from type_curve.py)
  qiOil: 750, bFactor: 0.9, effDeclineYr1: 0.7, dTerminal: 0.12,
  gorScfPerBbl: 2500, nglBblPerMmcf: 90, econLimitBblD: 15, maxYears: 35,
  // economics (assumptions.py)
  capex: 8_500_000, opexPerBoe: 8.0, opexFixedMonthly: 3000,
  nri: 0.79, sevOil: 0.046, sevGas: 0.075, sevNgl: 0.046,
  oilDiff: 0.98, gasReal: 0.9, nglPctWti: 0.34,
  discountAnnual: 0.10, galPerBbl: 42, mcfPerBoe: 6,
};

/* Supabase (reads your live tables). Env vars must be NEXT_PUBLIC_ prefixed.
   Created lazily and only when both vars exist, so a missing var degrades to
   "manual price" mode instead of crashing the build. */
const SUPA_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPA_KEY = process.env.NEXT_PUBLIC_SUPABASE_KEY;
const supabase = (SUPA_URL && SUPA_KEY) ? createClient(SUPA_URL, SUPA_KEY) : null;

/* ============================================================================
   THE MODEL — same math as type_curve.py + cash_flow.py, in JS.
   ============================================================================ */
function nominalDi(effDecline, b) {
  return (Math.pow(1 - effDecline, -b) - 1) / b;
}

function buildProduction(c) {
  const Di = nominalDi(c.effDeclineYr1, c.bFactor);
  const tSwitch = (Di / c.dTerminal - 1) / (c.bFactor * Di);
  const rows = [];
  const dt = 1 / 12;
  let qSwitch = null;
  for (let m = 0; m < c.maxYears * 12; m++) {
    const t = m * dt;
    let qDaily;
    if (t <= tSwitch) {
      qDaily = c.qiOil / Math.pow(1 + c.bFactor * Di * t, 1 / c.bFactor);
      qSwitch = qDaily;
    } else {
      qDaily = qSwitch * Math.exp(-c.dTerminal * (t - tSwitch));
    }
    if (qDaily < c.econLimitBblD) break;
    const oil = qDaily * 30.4;
    const gas = (oil * c.gorScfPerBbl) / 1000;
    const ngl = (gas / 1000) * c.nglBblPerMmcf;
    rows.push({ month: m + 1, year: +t.toFixed(2), oilBblD: qDaily, oil, gas, ngl });
  }
  return rows;
}

function runEconomics(prod, c, wti, hhGas) {
  const oilPrice = wti * c.oilDiff;
  const gasPrice = hhGas * c.gasReal;
  const nglPrice = wti * c.nglPctWti;
  const monthlyRate = Math.pow(1 + c.discountAnnual, 1 / 12) - 1;

  let npv = -c.capex;
  let cum = -c.capex;
  let paybackMonth = null;
  const cfSeries = [];

  prod.forEach((r, i) => {
    const oilRev = r.oil * oilPrice;
    const gasRev = r.gas * gasPrice;
    const nglRev = r.ngl * nglPrice;
    const gross = oilRev + gasRev + nglRev;
    const net = gross * c.nri;
    const sev = c.nri * (oilRev * c.sevOil + gasRev * c.sevGas + nglRev * c.sevNgl);
    const boe = r.oil + r.ngl + r.gas / c.mcfPerBoe;
    const opex = boe * c.opexPerBoe + c.opexFixedMonthly;
    const cf = net - sev - opex;
    npv += cf / Math.pow(1 + monthlyRate, i + 1);
    cum += cf;
    if (paybackMonth === null && cum >= 0) paybackMonth = r.month;
    if (r.month % 6 === 0) cfSeries.push({ month: r.month, cash: cf / 1000 });
  });

  // IRR via bisection on monthly rate, annualized
  const cash = [-c.capex, ...prod.map((r) => {
    const oilRev = r.oil * oilPrice, gasRev = r.gas * gasPrice, nglRev = r.ngl * nglPrice;
    const net = (oilRev + gasRev + nglRev) * c.nri;
    const sev = c.nri * (oilRev * c.sevOil + gasRev * c.sevGas + nglRev * c.sevNgl);
    const boe = r.oil + r.ngl + r.gas / c.mcfPerBoe;
    return net - sev - (boe * c.opexPerBoe + c.opexFixedMonthly);
  })];
  const npvAt = (mr) => cash.reduce((s, cf, t) => s + cf / Math.pow(1 + mr, t), 0);
  let irr = null;
  if (npvAt(-0.95) * npvAt(1) < 0) {
    let lo = -0.95, hi = 1;
    for (let k = 0; k < 200; k++) {
      const mid = (lo + hi) / 2;
      if (npvAt(mid) > 0) lo = mid; else hi = mid;
    }
    irr = Math.pow(1 + (lo + hi) / 2, 12) - 1;
  }
  return { npv, irr, paybackMonth, cfSeries };
}

function breakevenWti(prod, c, hhGas) {
  const npvAtWti = (wti) => runEconomics(prod, c, wti, hhGas).npv;
  let lo = 10, hi = 200;
  if (npvAtWti(lo) > 0) return lo;
  if (npvAtWti(hi) < 0) return null;
  for (let k = 0; k < 60; k++) {
    const mid = (lo + hi) / 2;
    if (npvAtWti(mid) < 0) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
}

/* ============================================================================
   COMPONENT
   ============================================================================ */
export default function WellDashboard() {
  const [wti, setWti] = useState(70);
  const [gas, setGas] = useState(3.5);
  const [capexM, setCapexM] = useState(8.5);
  const [livePrice, setLivePrice] = useState(null);
  const [liveDate, setLiveDate] = useState(null);
  const [status, setStatus] = useState("loading");

  // pull the latest real WTI price from Supabase on load
  useEffect(() => {
    async function load() {
      if (!supabase) { setStatus("offline"); return; }
      try {
        const { data, error } = await supabase
          .from("oil_prices").select("date, price").order("date", { ascending: false }).limit(1);
        if (error) throw error;
        if (data && data.length) {
          setLivePrice(data[0].price);
          setLiveDate(data[0].date);
          setWti(Math.round(data[0].price));
          setStatus("live");
        } else setStatus("empty");
      } catch (e) { setStatus("offline"); }
    }
    load();
  }, []);

  const cfg = useMemo(() => ({ ...CONFIG, capex: capexM * 1_000_000 }), [capexM]);
  const prod = useMemo(() => buildProduction(cfg), [cfg]);
  const econ = useMemo(() => runEconomics(prod, cfg, wti, gas), [prod, cfg, wti, gas]);
  const be = useMemo(() => breakevenWti(prod, cfg, gas), [prod, cfg, gas]);

  const prodChart = useMemo(
    () => prod.filter((r) => r.month % 3 === 0).map((r) => ({ year: r.year, oil: Math.round(r.oilBblD) })),
    [prod]
  );

  const npvPositive = econ.npv >= 0;
  const fmtM = (n) => `${n >= 0 ? "" : "\u2212"}$${Math.abs(n / 1e6).toFixed(2)}MM`;

  return (
    <div style={S.page}>
      <style>{keyframes}</style>
      <div style={S.wrap}>

        {/* header */}
        <header style={S.header}>
          <div>
            <h1 style={S.title}>Well Economics</h1>
            <p style={S.sub}>Midland Wolfcamp A · single-well evaluation</p>
          </div>
          <div style={S.livePill(status)}>
            <span style={S.dot(status)} />
            {status === "live" && `WTI $${livePrice?.toFixed(2)} · ${liveDate}`}
            {status === "loading" && "connecting to data\u2026"}
            {status === "offline" && "using manual price"}
            {status === "empty" && "no price data yet"}
          </div>
        </header>

        {/* hero: the decision */}
        <section style={S.hero}>
          <div style={S.heroVerdict(npvPositive)}>
            {npvPositive ? "Drill" : "Uneconomic"}
          </div>
          <div key={econ.npv > 0} style={{ ...S.npv, color: npvPositive ? C.amber : C.oxide }}>
            {fmtM(econ.npv)}
          </div>
          <div style={S.npvLabel}>net present value at {(CONFIG.discountAnnual * 100).toFixed(0)}% discount</div>
        </section>

        {/* metric row */}
        <section style={S.metrics}>
          <Metric label="IRR" value={econ.irr ? `${(econ.irr * 100).toFixed(0)}%` : "n/a"}
                  hint="annualized return" />
          <Metric label="Breakeven" value={be ? `$${be.toFixed(0)}` : "n/a"}
                  hint="WTI where NPV = 0" tone={wti > (be || 0) ? "good" : "bad"} />
          <Metric label="Payback" value={econ.paybackMonth ? `${econ.paybackMonth} mo` : "never"}
                  hint="capital recovered" />
        </section>

        {/* controls */}
        <section style={S.controls}>
          <Slider label="Oil price (WTI)" value={wti} min={20} max={120} step={1}
                  onChange={setWti} fmt={(v) => `$${v}`} accent={C.amber} />
          <Slider label="Gas price (Henry Hub)" value={gas} min={1} max={8} step={0.1}
                  onChange={setGas} fmt={(v) => `$${v.toFixed(2)}`} accent={C.steel} />
          <Slider label="Well cost (CapEx)" value={capexM} min={5} max={14} step={0.1}
                  onChange={setCapexM} fmt={(v) => `$${v.toFixed(1)}MM`} accent={C.steel} />
        </section>

        {/* charts */}
        <section style={S.charts}>
          <div style={S.chartBox}>
            <div style={S.chartTitle}>Production forecast — oil rate</div>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={prodChart} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id="oilFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.amber} stopOpacity={0.5} />
                    <stop offset="100%" stopColor={C.amber} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="year" stroke={C.steel} tick={{ fontSize: 11 }}
                       tickFormatter={(v) => `${v}y`} />
                <YAxis stroke={C.steel} tick={{ fontSize: 11 }} width={44}
                       tickFormatter={(v) => `${v}`} />
                <Tooltip contentStyle={S.tooltip} labelFormatter={(v) => `Year ${v}`}
                         formatter={(v) => [`${v} bbl/d`, "oil"]} />
                <Area type="monotone" dataKey="oil" stroke={C.amber} strokeWidth={2}
                      fill="url(#oilFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div style={S.chartBox}>
            <div style={S.chartTitle}>Monthly cash flow ($000s)</div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={econ.cfSeries} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <XAxis dataKey="month" stroke={C.steel} tick={{ fontSize: 11 }}
                       tickFormatter={(v) => `${Math.round(v / 12)}y`} />
                <YAxis stroke={C.steel} tick={{ fontSize: 11 }} width={44} />
                <Tooltip contentStyle={S.tooltip} labelFormatter={(v) => `Month ${v}`}
                         formatter={(v) => [`$${v.toFixed(0)}k`, "cash"]} />
                <ReferenceLine y={0} stroke={C.steel} strokeDasharray="3 3" />
                <Line type="monotone" dataKey="cash" stroke={C.bone} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <footer style={S.footer}>
          Live oil price from Supabase · economics computed in-browser, mirroring the Python model ·
          type curve, prices, and fiscal terms anchored to public Permian benchmarks
        </footer>
      </div>
    </div>
  );
}

/* ---- small components ---- */
function Metric({ label, value, hint, tone }) {
  const color = tone === "good" ? C.amber : tone === "bad" ? C.oxide : C.bone;
  return (
    <div style={S.metric}>
      <div style={S.metricLabel}>{label}</div>
      <div style={{ ...S.metricValue, color }}>{value}</div>
      <div style={S.metricHint}>{hint}</div>
    </div>
  );
}

function Slider({ label, value, min, max, step, onChange, fmt, accent }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div style={S.sliderRow}>
      <div style={S.sliderHead}>
        <span style={S.sliderLabel}>{label}</span>
        <span style={{ ...S.sliderValue, color: accent }}>{fmt(value)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{ ...S.range, background: `linear-gradient(90deg, ${accent} ${pct}%, ${C.line} ${pct}%)` }} />
    </div>
  );
}

/* ============================================================================
   STYLE
   ============================================================================ */
const C = {
  ground: "#0d1418", panel: "#141e24", line: "#26343c",
  bone: "#e6e3db", steel: "#7d8b91", amber: "#e8a33d", oxide: "#c65d3b",
};
const keyframes = `
  @keyframes pop { 0% { transform: scale(0.96); opacity: .6 } 100% { transform: scale(1); opacity: 1 } }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 18px; height: 18px; border-radius: 50%;
    background: #e6e3db; cursor: pointer; border: 3px solid #0d1418; margin-top: -7px;
  }
  input[type=range]::-moz-range-thumb {
    width: 18px; height: 18px; border-radius: 50%; background: #e6e3db;
    cursor: pointer; border: 3px solid #0d1418;
  }
  @media (max-width: 720px) { .charts-row { grid-template-columns: 1fr !important; } }
`;
const S = {
  page: { minHeight: "100vh", background: C.ground, color: C.bone,
    fontFamily: "'Inter', system-ui, sans-serif", padding: "clamp(16px,4vw,48px)" },
  wrap: { maxWidth: 920, margin: "0 auto" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start",
    gap: 16, flexWrap: "wrap", marginBottom: 40 },
  title: { fontSize: "clamp(28px,5vw,40px)", fontWeight: 700, letterSpacing: "-0.03em", margin: 0 },
  sub: { color: C.steel, fontSize: 14, margin: "4px 0 0" },
  livePill: (s) => ({ display: "flex", alignItems: "center", gap: 8, fontSize: 13,
    color: s === "live" ? C.bone : C.steel, background: C.panel, border: `1px solid ${C.line}`,
    padding: "8px 14px", borderRadius: 999 }),
  dot: (s) => ({ width: 8, height: 8, borderRadius: "50%",
    background: s === "live" ? "#4ea36b" : s === "loading" ? C.amber : C.steel,
    boxShadow: s === "live" ? "0 0 8px #4ea36b" : "none" }),
  hero: { textAlign: "center", padding: "24px 0 8px" },
  heroVerdict: (ok) => ({ display: "inline-block", fontSize: 13, fontWeight: 600,
    letterSpacing: "0.02em", color: ok ? "#4ea36b" : C.oxide, border: `1px solid ${ok ? "#2f5a41" : "#5a2f28"}`,
    padding: "4px 12px", borderRadius: 999, marginBottom: 16 }),
  npv: { fontSize: "clamp(52px,12vw,104px)", fontWeight: 800, letterSpacing: "-0.04em",
    lineHeight: 1, animation: "pop 0.25s ease-out", fontVariantNumeric: "tabular-nums" },
  npvLabel: { color: C.steel, fontSize: 14, marginTop: 12 },
  metrics: { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, margin: "32px 0" },
  metric: { background: C.panel, border: `1px solid ${C.line}`, borderRadius: 12, padding: "18px 20px" },
  metricLabel: { color: C.steel, fontSize: 13, marginBottom: 8 },
  metricValue: { fontSize: "clamp(24px,4vw,32px)", fontWeight: 700, fontVariantNumeric: "tabular-nums" },
  metricHint: { color: C.steel, fontSize: 12, marginTop: 6 },
  controls: { background: C.panel, border: `1px solid ${C.line}`, borderRadius: 14,
    padding: "24px", display: "grid", gap: 22, marginBottom: 28 },
  sliderRow: {},
  sliderHead: { display: "flex", justifyContent: "space-between", marginBottom: 10 },
  sliderLabel: { fontSize: 14, color: C.bone },
  sliderValue: { fontSize: 15, fontWeight: 700, fontVariantNumeric: "tabular-nums" },
  range: { width: "100%", height: 4, borderRadius: 999, appearance: "none",
    WebkitAppearance: "none", outline: "none", cursor: "pointer" },
  charts: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 28,
    className: "charts-row" },
  chartBox: { background: C.panel, border: `1px solid ${C.line}`, borderRadius: 14, padding: "18px" },
  chartTitle: { fontSize: 13, color: C.steel, marginBottom: 14 },
  tooltip: { background: C.ground, border: `1px solid ${C.line}`, borderRadius: 8,
    color: C.bone, fontSize: 12 },
  footer: { color: C.steel, fontSize: 12, textAlign: "center", lineHeight: 1.7,
    borderTop: `1px solid ${C.line}`, paddingTop: 20 },
};
