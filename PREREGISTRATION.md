# Pre-Registration — Volatility Breakout (Crabel/Williams family) on NQ

**Status:** registered before running on real data.
**Repo working title:** `volatility-breakout-falsification`
**Date registered:** 2026-06-29

---

## 0. Origin of the claim

A social thread ("I've tested thousands of breakout systems…") proposes:

- Entry: yesterday's close ± **4.6 × true range** → long/short stop levels.
- Exit: trailing stop *or* time-based.
- Risk rule: never hold over weekends.
- Claim: edge comes from *exits*, not *filters*; this "removes overfitting risk".

We do **not** test the literal `k = 4.6` parameter (it is almost certainly a
single overfit point, and `4.6 × daily TR` would rarely trigger). We test the
**general family** — close-anchored volatility breakout — honestly: grid `k`,
select on a training half, validate the selected `k` out-of-sample on a held-out
half. Picking the best `k` on the full sample is exactly the multiple-comparisons
trap the thread describes ("tested thousands") and is forbidden here.

The thread's central claim — that moving degrees of freedom from entry filters
to exits *removes* overfitting risk — is logically false (exits are parameters
too). H3 tests it empirically rather than rhetorically.

---

## 1. Instrument & data

- **Instrument:** E-mini Nasdaq-100 (NQ), continuous front-month, back-adjusted
  on roll. Daily OHLCV minimum; intraday optional (not required for daily
  breakout).
- **Point value:** $20 / point. Tick = 0.25 pt = $5.
- **Session:** RTH-anchored daily bars (yesterday's *close* = the reference).
- **Sample:** whatever continuous history is supplied (target ≥ 8 years so the
  split-half OOS has power). Roll-adjusted; no survivorship issue (single index).

## 2. Strategy specification (frozen)

For trading day *t*, using only information available at the open of *t*:

```
R_{t-1}    = true range proxy = ATR(N) computed on bars up to t-1   (N pre-registered below)
buy_level  = Close_{t-1} + k * R_{t-1}
sell_level = Close_{t-1} - k * R_{t-1}
```

- Long entry: if `High_t >= buy_level`, fill at `buy_level` (stop order).
- Short entry: if `Low_t  <= sell_level`, fill at `sell_level`.
- Both-touched same day: the level **closer to the day's open** is assumed to
  trigger first (deterministic tie-break, documented, not optimized).
- Direction: both long and short tested.

## 3. Exit engine (frozen)

Three pre-registered exit modes, tested as separate arms (NOT cherry-picked):

- **EOD:** exit at close of the entry day (pure intraday; never holds anything).
- **N-day time exit:** exit at close of day `t + H`, `H ∈ {1, 2, 3}` pre-set.
- **ATR trailing:** trail by `m × ATR(N)` from peak favorable excursion;
  `m ∈ {1.0, 2.0, 3.0}` pre-set.

Stop on entry day for non-EOD modes: opposite breakout level (the CISD analogue).

## 4. Weekend rule (tested, not assumed)

`weekend_flat ∈ {True, False}` is a **hypothesis arm**, not a fixed rule. H2
asks whether forcing a Friday-close exit improves risk-adjusted return vs.
holding through. The thread asserts it "saves thousands"; we measure it.

## 5. Cost model (frozen, applied to every fill)

Per round-trip:

- Commission: **$4.20** RT ($2.10 / side).
- Slippage: **1 tick (0.25 pt) per fill**, 2 fills → 0.50 pt RT.
- Total RT cost ≈ commission/$20 + 0.50 = 0.21 + 0.50 = **0.71 pt ≈ $14.20 / contract**.

Costs are deducted from every trade's gross P&L. No "frictionless" headline numbers.

## 6. Hypotheses (pre-registered, directional)

- **H1 — Edge exists:** the volatility-breakout family produces net-positive
  expectancy after costs on NQ, out-of-sample.
- **H2 — Weekend rule helps:** `weekend_flat=True` beats `False` on risk-adjusted
  return (Sharpe / return-per-trade), OOS.
- **H3 — Exits beat filters (overfit claim):** the best exit-tuned arm generalizes
  OOS *better* than a fixed-exit baseline (i.e., exit tuning does not itself
  overfit). The thread's core claim.

## 7. Decision rule (frozen — this is what makes it a falsification test)

1. **Chronological split:** first 50% = TRAIN, last 50% = TEST. No shuffling.
2. **Selection:** choose the single best `(k, exit_mode, weekend_flat)` config on
   TRAIN by net return-per-trade.
3. **Validation:** apply that *exact* config to TEST.
4. A hypothesis is **NOT falsified** only if **both** of:
   - TRAIN net edge > 0 **and** TEST net edge > 0, **and**
   - TEST edge significant at **p < 0.10** by permutation (label-shuffle) test,
   - **and** bootstrap 90% CI of TEST return-per-trade excludes 0.
5. Any post-hoc parameter change after seeing TEST = void run, re-register.

## 8. Cost / benchmark sanity check

Before trusting any positive result, the engine is run on **GBM synthetic data**
(random walk, NQ-like vol, zero drift). Expected outcome: net P&L ≈ **−cost drag**,
no significant edge at any `k`. If synthetic shows edge → engine has lookahead /
a bug, and all real-data results are void until fixed.

## 9. What would change our mind

A genuine positive requires: positive net edge in *both* halves at the *same*
config, surviving permutation and bootstrap, AND not reproducible on GBM. Absent
all of that, the default conclusion is the same as the prior projects: no edge
after costs.
