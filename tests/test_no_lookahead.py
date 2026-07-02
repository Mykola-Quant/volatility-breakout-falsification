"""
No-lookahead and accounting tests for the volatility-breakout engine.

Run: python -m pytest tests/ -q     (or just: python tests/test_no_lookahead.py)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
from volatility_breakout import Config, backtest, POINT_VALUE, TICK


def _toy(seed=0, n=400):
    rng = np.random.default_rng(seed)
    px = 15000 + np.cumsum(rng.normal(0, 30, n))
    o = px + rng.normal(0, 5, n)
    c = px + rng.normal(0, 5, n)
    h = np.maximum(o, c) + np.abs(rng.normal(0, 40, n))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 40, n))
    idx = pd.bdate_range("2015-01-02", periods=n)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)


def test_no_lookahead_eod():
    """Mutating bars AFTER a given date must not change trades that closed on/before it."""
    df = _toy()
    cfg = Config(k=0.5, exit_mode="eod")
    base = backtest(df, cfg)
    assert len(base) > 20

    split = df.index[len(df) // 2]
    early = base[base["exit_date"] <= split].reset_index(drop=True)

    df2 = df.copy()
    mask = df2.index > split
    df2.loc[mask, ["open", "high", "low", "close"]] *= 1.5  # scramble the future
    mut = backtest(df2, cfg)
    early2 = mut[mut["exit_date"] <= split].reset_index(drop=True)

    pd.testing.assert_frame_equal(early, early2, check_dtype=False)
    print("PASS: EOD trades are invariant to future bars (no lookahead).")


def test_cost_drag_sign():
    """Net P&L must always be gross minus a fixed positive round-trip cost."""
    df = _toy()
    cfg = Config(k=0.5, exit_mode="eod")
    tr = backtest(df, cfg)
    cost = cfg.rt_cost_points()
    assert cost > 0
    np.testing.assert_allclose(tr["gross_pts"] - tr["net_pts"], cost, rtol=0, atol=1e-9)
    print(f"PASS: every trade pays exactly {cost:.3f} pt round-trip cost.")


def test_gap_fill_is_conservative():
    """If the open gaps beyond the stop level, fill is at the open (worse), not the level."""
    # one engineered day: prior close known, today gaps far above buy_level
    idx = pd.bdate_range("2015-01-02", periods=30)
    base = 15000.0
    o = np.full(30, base); h = np.full(30, base + 1); l = np.full(30, base - 1); c = np.full(30, base)
    # build ATR history
    for i in range(1, 30):
        h[i] = base + 50; l[i] = base - 50; c[i] = base; o[i] = base
    # day 20: massive gap up so open >> buy_level
    o[20] = base + 500; h[20] = base + 520; l[20] = base + 480; c[20] = base + 490
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)
    cfg = Config(k=0.5, exit_mode="eod", direction="long", atr_n=10)
    tr = backtest(df, cfg)
    day20 = tr[tr["entry_date"] == idx[20]]
    if len(day20):
        # entry must be the open (gapped), not the lower buy_level
        assert day20.iloc[0]["entry_px"] >= o[20] - 1e-6, "gap fill should be at/above open"
        print("PASS: gap-up open fills the buy-stop at the open, not the cheaper level.")


if __name__ == "__main__":
    test_no_lookahead_eod()
    test_cost_drag_sign()
    test_gap_fill_is_conservative()
    print("\nAll tests passed.")
