# volatility-breakout-falsification

A pre-registered falsification test of the **volatility-breakout** family
(yesterday's close ± k × ATR), prompted by a viral "I've tested thousands of
breakout systems" thread that claimed you can *remove overfitting risk* by
tuning exits instead of entry filters.

This repo does **not** test the thread's literal `k = 4.6` (a single overfit
point). It tests the general family **honestly**: grid `k`, select the best
config on a training half, and validate that exact config out-of-sample on a
held-out half. Picking the best parameter on the full sample is precisely the
multiple-comparisons trap the thread describes ("tested thousands") — and it is
forbidden by the decision rule here.

Same methodology as
[`retail-crypto-alpha`](https://github.com/Mykola-Quant) and
[`turtle-soup-smt-falsification`](https://github.com/Mykola-Quant): hypotheses
fixed before results, split-half OOS, permutation + bootstrap, honest costs,
zero post-hoc tuning.

## Result (TL;DR)

**Falsified on both an NQ futures proxy and the cash Nasdaq-100 index.** The
strategy produces a *positive* out-of-sample point estimate on both series — and
that is exactly the trap. Neither survives the significance checks: the
permutation p-value stays above 0.10 and the bootstrap 90% CI includes zero on
both. A course-seller stops at "+126 pts/trade out-of-sample." The pre-registered
rule goes two steps further and shows that gain is indistinguishable from noise.

| | NQ=F (futures proxy) | ^NDX (cash index) |
|---|---|---|
| Sessions | 4,655 (2008-2026) | 4,654 (2008-2026) |
| TRAIN config selected | `k0.6 trailing m3.0 wf0` | `k0.6 trailing m3.0 wf0` |
| TRAIN net pts/trade | +29.2 (n=69) | +28.7 (n=83) |
| **TEST** net pts/trade | **+92.9 (n=82)** | **+125.6 (n=100)** |
| Permutation p | 0.213 | 0.118 |
| Bootstrap 90% CI | [-93.7, +287.8] | [-35.8, +295.3] |
| **Verdict** | **FALSIFIED** | **FALSIFIED** |

Two independent series, selected onto the *same* config, both showing a pretty
OOS number that fails permutation and bootstrap. That agreement is far stronger
than any single run.

## Hypothesis verdicts

- **H1 — edge exists after costs, OOS. -> FALSIFIED.** The OOS point estimate is
  positive on both series but not significant (permutation p = 0.213 / 0.118;
  bootstrap CI includes 0 on both). Not falsified by *absence* of a positive —
  falsified because the positive does not survive significance testing on 82-100
  trades.

- **H2 — "never hold over weekends saves thousands." -> NOT SUPPORTED (measured,
  not asserted).** Tested directly with a confound-free **weekend-carry** measure:
  take the real held positions and, for every position open across a Fri->Mon
  boundary, record the signed gap `side * (Monday_open - Friday_close)` — exactly
  the P&L the weekend-flat rule would remove.

  | | NQ=F | ^NDX |
  |---|---|---|
  | Weekend carries | 454 | 442 |
  | Mean signed gap | +5.51 pts | +4.59 pts |
  | Total carry P&L | +2,500 pts (+$50,004) | +2,028 pts (+$40,550) |
  | Permutation p | 0.223 | 0.504 |
  | Bootstrap 90% CI | [-1.9, +12.6] | [-6.6, +16.0] |

  The sign is *positive* on both series — holding through the weekend earned money
  over the sample, it didn't cost "thousands." But the CI straddles zero on both
  (p = 0.22 / 0.50), so the honest conclusion isn't "flattening loses money," it's
  that the weekend carry is statistically indistinguishable from zero and the rule
  saves nothing. The two series also behave as expected: NQ=F (a real overnight
  futures market) shows a slightly stronger carry than ^NDX (a cash index whose
  "Monday open vs Friday close" is mostly opening noise, p = 0.50).

  > Note: a naive matched-pair on the `weekend_flat` flag is confounded — with a
  > wide trailing stop, toggling the flag changes the whole holding horizon, not
  > just weekend exposure. The weekend-carry measure isolates the gap itself.

- **H3 — exit-tuning generalizes better than a fixed exit (the "exits remove
  overfitting" claim). -> NOT SUPPORTED.** The selected exit (ATR trailing, m=3.0)
  produced a large in-sample-selected TEST estimate that failed significance.
  Moving degrees of freedom onto the exit did not remove overfitting; it relocated
  it. The OOS gain is the same mirage the thread claims exits avoid.

## Why "both halves positive" is still FALSIFIED

The decision rule (frozen in `PREREGISTRATION.md`) requires **all four**: TRAIN
edge > 0, TEST edge > 0, permutation p < 0.10, and bootstrap 90% CI excluding 0.
Both series clear the first two and fail the last two. `p = 0.213` means roughly
one run in five on shuffled labels would look at least this good; a CI from -94 to
+288 pts is a ~380-point band straddling zero. A +93 pt/trade OOS mean on 82
trades with that dispersion is not a signal — it's what noise looks like when you
select the winner on a training half.

## Method

Entry: `Close_{t-1} +/- k * ATR(N)` as stop levels (long/short), no lookahead —
levels for day *t* use only data through *t-1*. Exits tested as separate arms:
end-of-day, N-day time exit, ATR trailing. Weekend-flat is a hypothesis arm, not
a fixed rule. Costs are deducted from every trade: $20/pt, $4.20 RT commission +
1 tick slippage per fill = **0.71 pt ~ $14.20/contract**. Stops that gap through
the level fill at the open (worse), never at the cheaper level.

Decision rule: chronological 50/50 split (no shuffling) -> grid-select best
`(k, exit, weekend_flat)` on TRAIN -> apply that exact config to TEST -> not
falsified only if TRAIN>0 **and** TEST>0 **and** permutation p<0.10 **and**
bootstrap CI excludes 0.

## Data

- **NQ=F** (primary): Yahoo Finance continuous front-month E-mini Nasdaq-100, a
  stitched proxy (not institutional back-adjusted). 4,655 daily sessions,
  2008-2026. 8 sessions (0.17%) had roll-related OHLC-ordering violations —
  flagged by the loader, negligible for the verdict.
- **^NDX** (robustness): Yahoo Finance cash Nasdaq-100 index, 4,654 sessions, same
  window. No roll artifacts (zero OHLC violations), used to confirm the futures
  result is not a roll-stitching artifact.

Because both are free-vendor series, a **FALSIFIED** verdict is safe to publish;
a hypothetical NOT-FALSIFIED would have required re-confirmation on institutional
data (Databento / FirstRate) before trusting it.

## No-edge control (GBM)

`make_gbm()` generates a zero-drift random walk with a free-forward intraday path
(the close is the genuine endpoint, never pinned). The protocol returns FALSIFIED
there too — even when TRAIN selection lands on a config showing +110 pt/trade that
collapses to -123 pt/trade OOS. The weekend-carry test on this gap-free control
returns exactly 0.000 pts (p = 1.000), confirming it invents no spurious effect.

## Run it

```bash
pip install -r requirements.txt
pip install yfinance                       # for the data fetcher

python fetch_nq.py                         # NQ=F -> NQ_continuous_daily.csv
python src/load_data.py NQ_continuous_daily.csv NQ

python fetch_nq.py ^NDX                    # cash index robustness check
python src/load_data.py NQ_continuous_daily.csv NDX

python src/validate.py                     # GBM no-edge control + H2 demo
python tests/test_no_lookahead.py          # invariance / cost / gap-fill tests
```

H2 weekend-carry on real data:

```python
import sys; sys.path.insert(0, "src")
from load_data import load_ohlcv
from validate import h2_weekend_test
h2_weekend_test(load_ohlcv("NQ_continuous_daily.csv"), on="test")
```

## Layout

```
PREREGISTRATION.md          hypotheses + decision rule, fixed before results
fetch_nq.py                 Yahoo Finance OHLCV fetcher (NQ=F / ^NDX)
src/volatility_breakout.py  entry/exit/cost engine (no lookahead)
src/validate.py             split-half OOS, permutation, bootstrap, GBM control, H2 test
src/load_data.py            CSV loader + CLI
tests/test_no_lookahead.py  invariance, cost, gap-fill tests
```

## License

MIT.
