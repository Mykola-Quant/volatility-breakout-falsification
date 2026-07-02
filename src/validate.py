"""
Validation harness for the volatility-breakout falsification test.

Decision rule (see PREREGISTRATION.md):
  chronological 50/50 split -> grid-select best config on TRAIN -> apply that
  exact config to TEST -> not falsified only if TRAIN>0 AND TEST>0 AND
  permutation p<0.10 AND bootstrap 90% CI excludes 0.

Also:
  - GBM no-edge control (must return FALSIFIED).
  - h2_weekend_test(): a strict matched-pair test of the weekend-flat rule.
"""

from __future__ import annotations
from itertools import product
import numpy as np
import pandas as pd

from volatility_breakout import Config, backtest, summarize, POINT_VALUE


K_GRID = [0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2]
EXIT_GRID = [
    ("eod", {}),
    ("ndays", {"hold_days": 1}),
    ("ndays", {"hold_days": 2}),
    ("ndays", {"hold_days": 3}),
    ("trailing", {"trail_atr_mult": 1.0}),
    ("trailing", {"trail_atr_mult": 2.0}),
    ("trailing", {"trail_atr_mult": 3.0}),
]
WEEKEND_GRID = [True, False]


def split_chrono(df, frac=0.5):
    cut = int(len(df) * frac)
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def enumerate_configs():
    for k, (mode, kw), wf in product(K_GRID, EXIT_GRID, WEEKEND_GRID):
        yield Config(k=k, exit_mode=mode, weekend_flat=wf, **kw)


def cfg_label(c: Config) -> str:
    extra = f"H{c.hold_days}" if c.exit_mode == "ndays" else (
        f"m{c.trail_atr_mult}" if c.exit_mode == "trailing" else "")
    return f"k{c.k}_{c.exit_mode}{extra}_wf{int(c.weekend_flat)}"


def grid_search(df, min_trades=30):
    best = None; rows = []
    for cfg in enumerate_configs():
        s = summarize(backtest(df, cfg))
        rows.append({"cfg": cfg_label(cfg), **s})
        if s.get("n_trades", 0) >= min_trades:
            score = s["mean_net_pts"]
            if best is None or score > best[1]:
                best = (cfg, score, s)
    return best, pd.DataFrame(rows)


def permutation_test(net_pts, n_iter=5000, seed=7):
    """Sign-flip permutation test. p = P(permuted mean >= observed mean)."""
    rng = np.random.default_rng(seed)
    obs = net_pts.mean(); n = len(net_pts); count = 0
    for _ in range(n_iter):
        if (net_pts * rng.choice([-1.0, 1.0], size=n)).mean() >= obs:
            count += 1
    return (count + 1) / (n_iter + 1)


def bootstrap_ci(net_pts, n_iter=10000, alpha=0.10, seed=11):
    rng = np.random.default_rng(seed); n = len(net_pts)
    means = np.empty(n_iter)
    for i in range(n_iter):
        means[i] = net_pts[rng.integers(0, n, n)].mean()
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def run_falsification(df, label="real"):
    print(f"\n{'='*64}\n  FALSIFICATION RUN: {label}   (n_sessions={len(df)})\n{'='*64}")
    train, test = split_chrono(df)
    best, _ = grid_search(train)
    if best is None:
        print("  No config reached the minimum trade count on TRAIN. Inconclusive.")
        return None
    cfg, _, train_summary = best
    print(f"\n  Best TRAIN config: {cfg_label(cfg)}")
    print(f"    TRAIN mean net pts/trade: {train_summary['mean_net_pts']:+.3f}  "
          f"(n={train_summary['n_trades']}, PF={train_summary['profit_factor']:.2f})")

    test_trades = backtest(test, cfg)
    test_summary = summarize(test_trades)
    if test_summary.get("n_trades", 0) < 10:
        print("  Too few TEST trades to judge. Inconclusive.")
        return None

    net = test_trades["net_pts"].to_numpy()
    p = permutation_test(net); lo, hi = bootstrap_ci(net)
    print(f"\n  OOS (TEST) result with the SAME frozen config:")
    print(f"    mean net pts/trade: {test_summary['mean_net_pts']:+.3f}  (n={test_summary['n_trades']})")
    print(f"    total net: {test_summary['net_pts_total']:+.1f} pts "
          f"(${test_summary['net_usd_total']:+,.0f} / contract)")
    print(f"    win rate: {test_summary['win_rate']:.1%}  PF: {test_summary['profit_factor']:.2f}")
    print(f"    permutation p-value: {p:.3f}")
    print(f"    bootstrap 90% CI of mean net pts: [{lo:+.3f}, {hi:+.3f}]")

    train_pos = train_summary["mean_net_pts"] > 0
    test_pos = test_summary["mean_net_pts"] > 0
    sig = p < 0.10; ci_excl = lo > 0
    not_falsified = train_pos and test_pos and sig and ci_excl
    print(f"\n  DECISION (frozen rule):")
    print(f"    TRAIN edge>0: {train_pos} | TEST edge>0: {test_pos} | "
          f"perm p<0.10: {sig} | bootstrap CI excludes 0: {ci_excl}")
    print(f"    >>> {'NOT FALSIFIED (edge survives)' if not_falsified else 'FALSIFIED (no robust edge)'}")
    return {"config": cfg_label(cfg), "train": train_summary, "test": test_summary,
            "perm_p": p, "boot_ci": (lo, hi), "not_falsified": not_falsified}


# ---- H2: strict matched-pair test of the weekend-flat rule ------------------

def _twosided_signflip_p(x, n_iter=10000, seed=13):
    """Two-sided sign-flip permutation p-value for mean(x) != 0."""
    rng = np.random.default_rng(seed)
    obs = abs(x.mean()); n = len(x); count = 0
    for _ in range(n_iter):
        if abs((x * rng.choice([-1.0, 1.0], size=n)).mean()) >= obs:
            count += 1
    return (count + 1) / (n_iter + 1)


def h2_weekend_test(df, k=0.6, exit_mode="trailing", exit_kwargs=None,
                    on="test", n_iter=10000, seed=13):
    """
    Direct, confound-free test of the weekend-flat rule.

    A matched-pair on weekend_flat is confounded: with a wide trailing stop,
    toggling the flag changes the whole holding HORIZON (hold-through positions
    can run for weeks), not just weekend exposure. So instead we measure the
    thing the thread actually claims: what does carrying a position across the
    weekend cost or earn?

    We run the real (non-overlapping) hold-through strategy, then for every trade
    that is open across a Fri->Mon boundary we record the signed weekend gap
    contribution:  side * (Monday_open - Friday_close). These are the P&L bits
    the weekend-flat rule would remove.

    Thread's claim ("never hold over weekends saves thousands") => this carry is
    net NEGATIVE. We test mean != 0 (two-sided permutation) with a bootstrap CI:
      - CI entirely < 0  -> holding over weekends hurts; flattening helps  (H2 SUPPORTED)
      - CI entirely > 0  -> holding over weekends earns; flattening costs   (H2 REFUTED)
      - CI straddles 0    -> no weekend effect; "saves thousands" is empty  (H2 NOT SUPPORTED)
    """
    exit_kwargs = exit_kwargs or {"trail_atr_mult": 3.0}
    train, test = split_chrono(df)
    data = {"test": test, "train": train, "full": df}[on].sort_index()

    cfg_hold = Config(k=k, exit_mode=exit_mode, weekend_flat=False, **exit_kwargs)
    trades = backtest(data, cfg_hold)  # real strategy, non-overlapping

    dates = data.index
    opens = data["open"]; closes = data["close"]
    gaps = []
    for _, tr in trades.iterrows():
        seg = dates[(dates >= tr["entry_date"]) & (dates <= tr["exit_date"])]
        for a, b in zip(seg[:-1], seg[1:]):
            # a->b spans a weekend if a is Friday or the calendar gap is >= 3 days
            if pd.Timestamp(a).weekday() == 4 or (pd.Timestamp(b) - pd.Timestamp(a)).days >= 3:
                gaps.append(tr["side"] * (opens.at[b] - closes.at[a]))
    gaps = np.asarray(gaps, dtype=float)

    lbl = f"k{k}_{exit_mode}{exit_kwargs}"
    print(f"\n{'='*64}\n  H2 WEEKEND-CARRY TEST ({on} half)   config={lbl}\n{'='*64}")
    if len(gaps) < 5:
        print(f"  Only {len(gaps)} weekend carries -- too few to test.")
        return None

    mean_g = gaps.mean()
    total_g = gaps.sum()
    p = _twosided_signflip_p(gaps, n_iter=n_iter, seed=seed)
    lo, hi = bootstrap_ci(gaps, n_iter=n_iter, seed=seed)

    print(f"  weekend carries: {len(gaps)}   (positions held across a Fri->Mon)")
    print(f"  mean signed weekend gap: {mean_g:+.3f} pts/carry")
    print(f"  total weekend carry P&L: {total_g:+.1f} pts  (${total_g*POINT_VALUE:+,.0f} / contract)")
    print(f"  two-sided permutation p: {p:.3f}")
    print(f"  bootstrap 90% CI of mean: [{lo:+.3f}, {hi:+.3f}]")

    if hi < 0:
        verdict = "SUPPORTED (holding over weekends hurts; flattening saves money)"
    elif lo > 0:
        verdict = "REFUTED (holding over weekends EARNS money; flattening would cost you)"
    else:
        verdict = "NOT SUPPORTED (weekend carry is indistinguishable from zero; 'saves thousands' is empty)"
    print(f"\n  H2 VERDICT: {verdict}")
    return {"n_carries": len(gaps), "mean_gap": float(mean_g),
            "total_pts": float(total_g), "perm_p": p, "ci": (lo, hi), "verdict": verdict}


# ---- GBM synthetic sanity check -------------------------------------------

def make_gbm(n_days=3000, ann_vol=0.20, start=15000.0, seed=3, steps_per_day=80):
    rng = np.random.default_rng(seed)
    dt = 1 / 252; sigma_d = ann_vol * np.sqrt(dt)
    sig_step = sigma_d / np.sqrt(steps_per_day)
    dates = pd.bdate_range("2010-01-04", periods=n_days)
    o = np.empty(n_days); h = np.empty(n_days); l = np.empty(n_days); c = np.empty(n_days)
    log_open = np.log(start)
    for i in range(n_days):
        incr = rng.normal(0.0, sig_step, steps_per_day)
        path = log_open + np.concatenate([[0.0], np.cumsum(incr)])
        o[i] = np.exp(path[0]); c[i] = np.exp(path[-1])
        h[i] = np.exp(path.max()); l[i] = np.exp(path.min())
        log_open = path[-1]
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=dates)


if __name__ == "__main__":
    print("GBM no-edge control (expect FALSIFIED at the protocol level).\n")
    gbm = make_gbm(steps_per_day=400, n_days=3500)
    run_falsification(gbm, label="GBM synthetic (no-edge control)")
    h2_weekend_test(gbm, on="test")  # on no-edge data the weekend rule should do nothing
