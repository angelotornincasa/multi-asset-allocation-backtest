"""
Multi-asset allocation backtest vs a 100% global equity benchmark.

Question: does a diversified portfolio beat holding one global equity ETF
on a risk-adjusted basis, after costs?

Strategies (all rebalanced on a fixed schedule, weights decided at the close
of the rebalance day and applied from the next day, so no look-ahead):
  - Benchmark: 100% global equity (VT, closest US-listed proxy of FTSE All-World)
  - 60/40: VT / AGG
  - Multi-asset: 50% VT, 30% AGG, 10% GLD, 10% VNQ (edit WEIGHTS below;
    weights are re-normalised if an asset is excluded via EXCLUDE)
  - Equal weight across all assets
  - Inverse volatility (252-day trailing vol; needs a warm-up, see below)

Evaluation window: the first WARMUP days of data are used only to estimate
volatilities. ALL strategies are compared on the same window that starts
after the warm-up, so inverse volatility is never judged while it still
falls back to equal weights. Stress periods that start inside the warm-up
are shown as n/a for inverse volatility.

Outputs (folder --out, default ./results):
  metrics.csv            main comparison, full evaluation window
  subperiods.csv         same metrics split in two sub-periods (SPLIT_DATE)
  robustness.csv         Sharpe and max drawdown across rebalance frequency and costs
  stress_periods.csv     total return in crisis windows
  equity_curves.png

Usage:
  pip install pandas numpy matplotlib yfinance
  python allocation_backtest.py                 # real data from Yahoo Finance
  python allocation_backtest.py --rebal Q --cost-bps 10 --rf 0.02
  python allocation_backtest.py --demo          # synthetic data, only to test the code

Simplifications to mention when presenting this: USD proxies instead of UCITS
EUR ETFs (no currency hedging analysis), constant risk-free rate (default 2%),
proportional transaction costs, no taxes, one historical sample, past
performance only.
"""
import argparse
import os

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

TICKERS = ["VT", "AGG", "GLD", "VNQ"]  # global equity, bonds, gold, real estate
WEIGHTS = {"VT": 0.50, "AGG": 0.30, "GLD": 0.10, "VNQ": 0.10}
ANN = 252
WARMUP = ANN + 21  # one year of vol history plus one month to reach the first rebalance
SPLIT_DATE = "2017-01-01"
# Fixed end date so results are reproducible. yfinance treats 'end' as exclusive,
# so the last observation is 16 Oct 2026 (the last complete trading day when this was run).
# Without it, the latest, still incomplete, trading day changes the numbers slightly on every run.
END_DATE = "2026-10-17"

# Assets removed from the test. ["GLD"] = no gold. Use [] for the full analysis.
EXCLUDE = ["GLD"]

STRESS = {
    "2008-09 crisis (Sep 2008 - 9 Mar 2009)": ("2008-09-01", "2009-03-09"),
    "COVID crash (19 Feb - 23 Mar 2020)": ("2020-02-19", "2020-03-23"),
    "2022 rate shock (full year)": ("2022-01-01", "2022-12-31"),
}


# ---------------------------------------------------------------- data
def load_returns(start, demo):
    if demo:
        rng = np.random.default_rng(42)
        idx = pd.bdate_range("2008-07-01", "2025-12-31")
        mu = np.array([0.08, 0.03, 0.06, 0.07]) / ANN
        sd = np.array([0.16, 0.05, 0.15, 0.20]) / np.sqrt(ANN)
        corr = np.array([[1, .1, .0, .7], [.1, 1, .2, .2], [.0, .2, 1, .1], [.7, .2, .1, 1]])
        cov = corr * np.outer(sd, sd)
        data = rng.multivariate_normal(mu, cov, size=len(idx))
        return pd.DataFrame(data, index=idx, columns=TICKERS)
    import yfinance as yf

    px = yf.download(TICKERS, start=start, end=END_DATE, auto_adjust=True, progress=False)["Close"]
    px = px[TICKERS].dropna()  # aligns on the youngest ETF
    return px.pct_change().dropna()


# ---------------------------------------------------------- weight rules
def fixed(weights):
    return lambda hist: pd.Series(weights, dtype=float)


def equal_weight(hist):
    return pd.Series(1.0 / hist.shape[1], index=hist.columns)


def inverse_vol(hist, window=ANN):
    if len(hist) < window:  # warm-up: not enough history, falls back to equal weights
        return equal_weight(hist)
    inv = 1.0 / hist.tail(window).std()
    return inv / inv.sum()


STRATEGIES = {
    "Benchmark 100% VT": fixed({"VT": 1.0}),
    "60/40 (VT/AGG)": fixed({"VT": 0.6, "AGG": 0.4}),
    "Multi-asset": fixed(WEIGHTS),
    "Equal weight": equal_weight,
    "Inverse volatility": inverse_vol,
}
NEEDS_WARMUP = {"Inverse volatility"}


# ------------------------------------------------------------- backtest
def backtest(rets, weight_fn, rebal="M", cost_bps=5.0):
    """Daily simulation with weight drift, periodic rebalancing and costs."""
    cols = rets.columns
    R = rets.values
    dates = rets.index
    last_of_period = rets.index.to_series().groupby(rets.index.to_period(rebal)).last()
    rebal_dates = set(last_of_period.values)

    def target(i):
        w = weight_fn(rets.iloc[: i + 1]).reindex(cols).fillna(0.0)
        return (w / w.sum()).values  # re-normalise so weights sum to 100% after removing assets

    w = target(0)
    out, pending_cost = [], 0.0
    for i in range(1, len(rets)):
        gross = float(w @ R[i])
        out.append(gross - pending_cost)
        pending_cost = 0.0
        w = w * (1 + R[i]) / (1 + gross)  # drift
        if dates[i].to_datetime64() in rebal_dates:
            t = target(i)
            pending_cost = np.abs(t - w).sum() * cost_bps / 1e4
            w = t
    return pd.Series(out, index=dates[1:])


def run_all(rets, rebal, cost_bps):
    return {n: backtest(rets, f, rebal, cost_bps) for n, f in STRATEGIES.items()}


# -------------------------------------------------------------- metrics
def metrics(r, rf=0.0):
    cum = (1 + r).cumprod()
    years = len(r) / ANN
    cagr = cum.iloc[-1] ** (1 / years) - 1
    vol = r.std() * np.sqrt(ANN)
    ex = r - rf / ANN
    downside = np.sqrt((np.minimum(ex, 0) ** 2).mean()) * np.sqrt(ANN)
    mdd = (cum / cum.cummax() - 1).min()
    monthly = r.groupby(r.index.to_period("M")).apply(lambda x: (1 + x).prod() - 1)
    return {
        "CAGR": cagr,
        "Volatility": vol,
        "Sharpe": ex.mean() * ANN / vol,
        "Sortino": ex.mean() * ANN / downside,
        "Max drawdown": mdd,
        "Calmar": cagr / abs(mdd),
        "Worst month": monthly.min(),
    }


def metrics_table(returns, start, end=None, rf=0.0):
    return pd.DataFrame({n: metrics(r.loc[start:end], rf) for n, r in returns.items()}).T


def stress_table(returns, eval_start):
    rows = {}
    for label, (a, b) in STRESS.items():
        row = {}
        for name, r in returns.items():
            seg = r.loc[a:b]
            covered = len(seg) > 0 and seg.index[0] <= pd.Timestamp(a) + pd.Timedelta(days=7)
            in_warmup = name in NEEDS_WARMUP and pd.Timestamp(a) < eval_start
            row[name] = (1 + seg).prod() - 1 if covered and not in_warmup else np.nan
        rows[label] = row
    return pd.DataFrame(rows).T


def robustness_table(rets, eval_start, rf):
    """Sharpe and max drawdown for every rebalance frequency x cost level."""
    rows = []
    for rebal in ["M", "Q", "Y"]:
        for cost in [5.0, 20.0]:
            res = run_all(rets, rebal, cost)
            for name, r in res.items():
                m = metrics(r.loc[eval_start:], rf)
                rows.append({"Rebalance": rebal, "Cost (bps)": cost, "Strategy": name,
                             "CAGR": m["CAGR"], "Sharpe": m["Sharpe"], "Max drawdown": m["Max drawdown"]})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- output
def fmt(table):
    shown = table.copy()
    for c in ["CAGR", "Volatility", "Max drawdown", "Worst month"]:
        if c in shown:
            shown[c] = shown[c].map("{:.1%}".format)
    for c in ["Sharpe", "Sortino", "Calmar"]:
        if c in shown:
            shown[c] = shown[c].map("{:.2f}".format)
    return shown


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2005-01-01")
    ap.add_argument("--rebal", default="M", choices=["M", "Q", "Y"], help="rebalance frequency")
    ap.add_argument("--cost-bps", type=float, default=5.0, help="cost per unit of turnover")
    ap.add_argument("--rf", type=float, default=0.02, help="annual risk-free rate (default 2%%)")
    ap.add_argument("--out", default=None, help="output folder (default depends on EXCLUDE)")
    ap.add_argument("--demo", action="store_true", help="synthetic data, NOT real results")
    ap.add_argument("--no-robust", action="store_true", help="skip the robustness grid (faster)")
    a, _ = ap.parse_known_args()  # ignores extra args injected by Jupyter/Colab

    if a.out is None:
        a.out = "results_no_" + "_".join(EXCLUDE).lower() if EXCLUDE else "results"
    os.makedirs(a.out, exist_ok=True)
    rets = load_returns(a.start, a.demo)
    rets = rets.drop(columns=EXCLUDE)
    if EXCLUDE:
        print(f"Assets excluded from this run: {EXCLUDE}")
    tag = "SYNTHETIC DATA - NOT REAL RESULTS" if a.demo else ""
    if a.demo:
        print(f"\n*** {tag} ***")
    eval_start = rets.index[WARMUP]
    print(f"Data: {rets.index[0].date()} -> {rets.index[-1].date()} ({len(rets)} days)")
    print(f"Evaluation window (after {WARMUP}-day warm-up): {eval_start.date()} -> {rets.index[-1].date()}")
    print(f"Rebalance={a.rebal}, cost={a.cost_bps:g} bps, risk-free rate={a.rf:.1%}")

    returns = run_all(rets, a.rebal, a.cost_bps)

    # 1) main table, same window for every strategy
    table = metrics_table(returns, eval_start, rf=a.rf)
    table.to_csv(os.path.join(a.out, "metrics.csv"))
    print("\nPerformance metrics (common evaluation window)\n", fmt(table).to_string())

    # 4) two sub-periods
    split = pd.Timestamp(SPLIT_DATE)
    sub = {}
    for label, (s, e) in {f"{eval_start.year}-{split.year - 1}": (eval_start, split - pd.Timedelta(days=1)),
                          f"{split.year}-{rets.index[-1].year}": (split, None)}.items():
        t = metrics_table(returns, s, e, a.rf)
        t.insert(0, "Period", label)
        sub[label] = t
    subperiods = pd.concat(sub.values())
    subperiods.to_csv(os.path.join(a.out, "subperiods.csv"))
    for label, t in sub.items():
        print(f"\nSub-period {label}\n", fmt(t.drop(columns="Period"))[["CAGR", "Volatility", "Sharpe", "Max drawdown"]].to_string())

    # stress periods
    stress = stress_table(returns, eval_start)
    stress.to_csv(os.path.join(a.out, "stress_periods.csv"))
    print("\nStress periods (total return; n/a = outside data or inside the inverse-vol warm-up)\n",
          stress.map(lambda x: "n/a" if pd.isna(x) else f"{x:.1%}").to_string())

    # 3) robustness grid
    if not a.no_robust:
        rob = robustness_table(rets, eval_start, a.rf)
        rob.to_csv(os.path.join(a.out, "robustness.csv"), index=False)
        piv = rob.pivot_table(index="Strategy", columns=["Rebalance", "Cost (bps)"], values="Sharpe")
        print("\nRobustness: Sharpe by rebalance frequency and cost (bps)\n", piv.round(2).to_string())
        rank = piv.rank(ascending=False).mean(axis=1).sort_values()
        print("\nAverage Sharpe rank across the 6 settings (1 = best)\n", rank.round(1).to_string())

    fig, ax = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for n, r in returns.items():
        r = r.loc[eval_start:]
        cum = (1 + r).cumprod()
        ax[0].plot(cum, label=n, lw=2 if n.startswith("Benchmark") else 1.2)
        ax[1].plot(cum / cum.cummax() - 1, lw=1.2)
    ax[0].set_title(f"Growth of 1 (rebalance={a.rebal}, cost={a.cost_bps:g} bps) {tag}")
    ax[0].legend()
    ax[1].set_title("Drawdown")
    for x in ax:
        x.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "equity_curves.png"), dpi=150)
    print(f"\nSaved results in '{a.out}/'")


if __name__ == "__main__":
    main()
