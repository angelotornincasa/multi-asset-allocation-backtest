# Multi-Asset Allocation Backtest: does diversification beat one global equity ETF?

A Python backtest comparing five allocation strategies against a 100% global equity benchmark, on a risk-adjusted basis and after transaction costs.

**Main finding:** diversification reduced the maximum drawdown by roughly 7 to 15 percentage points, but its risk-adjusted advantage came from gold. Without gold, no diversified strategy beat the equity-only benchmark on Sharpe ratio, and in 2017-2026 the benchmark was the best strategy.

## Question

Does a diversified portfolio (equities, bonds, gold, real estate) beat holding a single global equity ETF on a risk-adjusted basis, after costs, and is the result stable across time and assumptions?

## Data

Daily adjusted prices from Yahoo Finance (`yfinance`), US-listed ETFs used as proxies:

| Asset | Ticker |
|---|---|
| Global equities (proxy for FTSE All-World) | VT |
| US aggregate bonds | AGG |
| Gold | GLD |
| US real estate (REITs) | VNQ |

The sample starts on 27 June 2008 (the launch of VT) and ends on 16 October 2026 (a fixed end date, so that results are reproducible; later runs of the script give the same numbers unless Yahoo Finance revises its adjusted prices).

## Strategies

All strategies are rebalanced on a fixed schedule. Weights are decided at the close of the rebalance day and applied from the next day, so there is no look-ahead bias. Weights drift between rebalances, and costs are charged on turnover.

1. **Benchmark:** 100% VT
2. **60/40:** 60% VT, 40% AGG
3. **Multi-asset:** 50% VT, 30% AGG, 10% GLD, 10% VNQ
4. **Equal weight:** equal share in each asset
5. **Inverse volatility:** weights proportional to 1 / volatility, using a 252-day trailing window (a simplified, risk-parity-style rule that ignores correlations)

**Warm-up:** the first 273 days are used only to estimate volatilities. All strategies are compared on the same window, starting on 29 July 2009. Inverse volatility is shown as n/a for stress periods that start inside the warm-up.

**Metrics:** CAGR, volatility, Sharpe, Sortino, maximum drawdown, Calmar, worst month. Sharpe and Sortino use a constant 2% risk-free rate. Default costs are 5 basis points per unit of turnover.

## Results

Evaluation window: 29 Jul 2009 to 16 Oct 2026, monthly rebalancing, 5 bps costs.

### With all four assets

| Strategy | CAGR | Volatility | Sharpe | Sortino | Max drawdown | Calmar | Worst month |
|---|---|---|---|---|---|---|---|
| Benchmark 100% VT | 11.0% | 17.4% | 0.57 | 0.79 | -34.2% | 0.32 | -14.8% |
| 60/40 (VT/AGG) | 7.8% | 10.6% | 0.57 | 0.79 | -22.3% | 0.35 | -9.1% |
| Multi-asset | 8.5% | 10.8% | 0.62 | 0.86 | -22.7% | 0.37 | -9.5% |
| Equal weight | 8.6% | 10.6% | 0.65 | 0.90 | -21.8% | 0.40 | -8.7% |
| Inverse volatility | 6.1% | 6.8% | 0.61 | 0.85 | -19.3% | 0.31 | -6.0% |

### Without gold (GLD removed, weights re-normalised)

| Strategy | CAGR | Volatility | Sharpe | Sortino | Max drawdown | Calmar | Worst month |
|---|---|---|---|---|---|---|---|
| Benchmark 100% VT | 11.0% | 17.4% | 0.57 | 0.79 | -34.2% | 0.32 | -14.8% |
| 60/40 (VT/AGG) | 7.8% | 10.6% | 0.57 | 0.79 | -22.3% | 0.35 | -9.1% |
| Multi-asset | 8.3% | 11.6% | 0.57 | 0.80 | -24.8% | 0.33 | -10.5% |
| Equal weight (1/3 each) | 8.2% | 12.0% | 0.55 | 0.76 | -26.8% | 0.31 | -11.6% |
| Inverse volatility | 5.0% | 6.8% | 0.46 | 0.63 | -20.9% | 0.24 | -6.9% |

### Sharpe ratio by sub-period

| Strategy | 2009-2016 (with gold) | 2017-2026 (with gold) | 2009-2016 (no gold) | 2017-2026 (no gold) |
|---|---|---|---|---|
| Benchmark 100% VT | 0.47 | 0.65 | 0.47 | 0.65 |
| 60/40 (VT/AGG) | 0.53 | 0.60 | 0.53 | 0.60 |
| Multi-asset | 0.60 | 0.64 | 0.60 | 0.55 |
| Equal weight | 0.66 | 0.63 | 0.73 | 0.42 |
| Inverse volatility | 0.75 | 0.55 | 0.76 | 0.33 |

### Stress periods (total return, with gold)

| Period | VT | 60/40 | Multi-asset | Equal weight | Inverse vol |
|---|---|---|---|---|---|
| 2008-09 crisis (Sep 2008 to 9 Mar 2009) | -47.9% | -31.1% | -32.5% | -29.9% | n/a (warm-up) |
| COVID crash (19 Feb to 23 Mar 2020) | -33.8% | -21.6% | -22.6% | -21.0% | -13.0% |
| 2022 rate shock (full year) | -18.0% | -15.8% | -15.5% | -14.5% | -13.4% |

### Robustness

Rebalancing monthly, quarterly or yearly, and costs of 5 or 20 bps, change Sharpe ratios by at most 0.05. The ranking of strategies is stable across these six settings, because turnover is low.

## Interpretation

- **Drawdown protection:** diversified strategies had a maximum drawdown of roughly 19% to 27% against 34% for the equity benchmark, at a cost of about 2.4 to 6.0 percentage points of annual return.
- **The gold effect:** with gold, equal weight, multi-asset and inverse volatility had higher Sharpe ratios than the benchmark (0.61 to 0.65 vs 0.57). Without gold, none did. The risk-adjusted advantage came from gold's strong performance in this sample, not from diversification itself.
- **Real estate:** without gold, equal weight protected worse than 60/40 in crises (-40.5% vs -31.1% in 2008, per the no-gold run), because REITs move with equities when it matters.
- **Stability over time:** diversification helped Sharpe in 2009-2016 but not in 2017-2026, when the equity benchmark was the best strategy.
- **2022:** stocks and bonds fell together, so the 60/40 portfolio offered little protection (-15.8% vs -18.0%).
- Sharpe differences of 0.01 to 0.03 are too small to rank strategies reliably.

## Limitations

- One historical sample (2008-2026), including a long period of falling rates that favoured bonds, and a strong gold rally.
- USD-listed ETF proxies; no currency analysis for a euro-based investor and no UCITS vehicles.
- Constant risk-free rate (2%); no taxes; proportional costs only.
- Removing gold was a test chosen after seeing the full-sample results; it is a sensitivity check, not proof that gold is or is not a good diversifier in general.
- Inverse volatility ignores correlations, so it is not true risk parity.
- Past performance does not predict future results.

## How to run

```bash
pip install pandas numpy matplotlib yfinance
python allocation_backtest.py            # uses the EXCLUDE setting at the top of the file
python allocation_backtest.py --rebal Q --cost-bps 20 --rf 0.02
python allocation_backtest.py --demo     # synthetic data, only to test that the code runs
```

At the top of the script, `EXCLUDE = ["GLD"]` runs the no-gold test and writes to `results_no_gld/`. Set `EXCLUDE = []` for the full analysis (output in `results/`).

Each run saves `metrics.csv`, `subperiods.csv`, `robustness.csv`, `stress_periods.csv` and `equity_curves.png`.

## Author

Angelo Tornincasa, MSc Economics and Finance, LUISS Guido Carli.
