# Social drafts — volatility-breakout-falsification (real results)

All numbers below are from actual runs: NQ=F (Yahoo continuous front-month, 4,655
sessions 2008-2026) and ^NDX (cash Nasdaq-100, robustness). Both FALSIFIED.

---

## X / Twitter thread

**1/**
A breakout thread went semi-viral: "I've tested thousands of systems. The secret
isn't filters — it's better exits. This removes overfitting risk. Entry = close +/-
4.6x range."

I actually tested the idea. It falsifies. Here's the honest version. (thread)

**2/**
The claims, before any data:
– "tested thousands, kept the best" = textbook multiple comparisons (how you
manufacture a false positive)
– moving knobs from entry filters to exits doesn't remove them, it hides them
– k=4.6 tuned to a decimal IS the overfit being denied

**3/**
So I didn't test k=4.6. I gridded k, selected the best config on the first half of
the data, then applied that EXACT config to a held-out second half. NQ costs
modeled ($14.20/round-trip). Permutation test + bootstrap CI on the OOS half.

**4/**
Out-of-sample on NQ, same frozen config: **+92.9 pts/trade** over 82 trades. Looks
like a winner.

This is exactly where the course-seller stops and hits "post."

**5/**
Two more steps:
– permutation p = 0.21 (1 in 5 shuffles look this good)
– bootstrap 90% CI = [-94, +288] pts — a ~380-pt band straddling zero

+93/trade on 82 trades with that spread isn't a signal. It's what noise looks like
after you pick the winner in-sample.

**6/**
Robustness: reran on the cash Nasdaq-100 index (^NDX), 100 OOS trades. Same
selected config, OOS **+125.6 pts/trade**, p = 0.12, CI [-36, +295]. Prettier
number, still fails. Two independent series, same verdict: FALSIFIED.

**7/**
The thread's "never hold over weekends saves thousands"? I measured the actual
weekend carry (signed Fri-close -> Mon-open gap on held positions). It was
*positive*: +$50k on NQ=F, +$41k on ^NDX. Holding over weekends earned money — but
p=0.22/0.50, so really it's just zero. The rule saves nothing.

**8/**
Exits didn't remove overfitting — they relocated it. A gorgeous in-sample-tuned
exit gave a big OOS point estimate that dies under permutation + bootstrap.

Pre-registration, engine, costs, no-lookahead tests, GBM control — all open:
https://github.com/Mykola-Quant/volatility-breakout-falsification

---

## Reddit — r/algotrading

**Title:** Volatility breakout (close +/- k*ATR) on NQ — positive out-of-sample,
still falsified after permutation + bootstrap

There's a thread going around: close +/- 4.6xrange entries, "the secret is better
exits not filters," "this removes overfitting risk," "tested thousands of
systems." Instead of arguing, I built a pre-registered test.

Three problems before touching data: "tested thousands, kept the winner" is
multiple comparisons; moving degrees of freedom from entry filters to exits
doesn't reduce them; and k=4.6 tuned to a decimal is itself the overfit being
denied.

Setup: grid k, select the best (k, exit, weekend-flat) config on the first 50% of
data, apply that exact config to the held-out 50%. Costs modeled at 0.71 pt
(~$14.20) round-trip, deducted per trade. Three exit arms (EOD / N-day / ATR
trailing). Pre-registered decision rule: not falsified only if TRAIN>0 AND TEST>0
AND permutation p<0.10 AND bootstrap 90% CI excludes 0.

Data: Yahoo continuous front-month NQ=F, 4,655 daily sessions 2008-2026, plus the
cash ^NDX index as a robustness check (no roll artifacts).

Results. On NQ=F the TRAIN-selected config (k0.6, ATR trailing, hold through
weekends) produced an out-of-sample **+92.9 pts/trade over 82 trades** — positive,
and where most writeups would stop. But permutation p = 0.213 and the bootstrap
90% CI is [-93.7, +287.8], which straddles zero. On ^NDX the same config gave OOS
**+125.6 pts/trade over 100 trades**, p = 0.118, CI [-35.8, +295.3]. Both
FALSIFIED. Two independent series, same selected config, same failure mode: a
pretty OOS mean that's statistically indistinguishable from zero.

I also tested the "never hold over weekends saves thousands" claim directly, via
the signed weekend carry (side * (Monday_open - Friday_close) on every position
held across a weekend). It came out *positive* — +2,500 pts (~$50k) on NQ=F,
+2,028 pts (~$41k) on ^NDX — i.e. holding through weekends earned money over the
sample rather than costing "thousands." But the CIs straddle zero (p = 0.22 /
0.50), so the honest read is that the weekend carry is indistinguishable from zero
and the rule saves nothing. (A naive matched-pair on the flag is confounded — a
wide trailing stop makes toggling it change the whole holding horizon, not just
weekend exposure — so I measured the gap directly instead.)

And the "exits remove overfitting" claim: the exit-tuning that was supposed to fix
overfitting is exactly what generated the in-sample-selected OOS mirage that then
failed significance.

Sanity control: on a zero-drift GBM random walk the same protocol also returns
FALSIFIED, including cases where TRAIN selection shows +110 pts/trade that
collapses to -123 OOS; the weekend-carry test there returns exactly 0.000
(p=1.000). So the rig catches manufactured edge and invents no spurious effect.

Code, pre-registration, cost model, no-lookahead tests: https://github.com/Mykola-Quant/volatility-breakout-falsification. Curious
whether anyone here has a vol-breakout variant that survives honest split-half OOS
with permutation on index futures post-2008 — everything I test evaporates under
the significance step even when the point estimate looks great.

---

## Cross-link paragraph (repo bridge, your usual)

> Third in a sequence of pre-registered falsification tests of retail-accessible
> strategies (see `retail-crypto-alpha` for tick-level order-flow signals and
> `turtle-soup-smt-falsification` for the SMC/SMT FX model). Same discipline
> throughout: hypotheses fixed before results, split-half OOS, permutation +
> bootstrap, honest costs, negative results reported plainly.
