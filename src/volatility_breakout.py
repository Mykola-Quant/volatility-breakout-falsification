"""
Volatility breakout (Crabel / Larry Williams family) backtest engine for NQ.

Entry:  yesterday's close +/- k * ATR(N)   -> stop entries, long & short
Exits:  EOD | N-day time exit | ATR trailing stop
Costs:  pre-registered, deducted from every trade (see PREREGISTRATION.md)

Design rules (enforced, not optional):
  - No lookahead. Breakout levels for day t use only data up to t-1.
  - Intraday fills on daily bars use bar High/Low with a deterministic,
    documented tie-break when both levels are touched (level nearer the OPEN
    triggers first). This is a conservative simplification, not a tuned choice.
  - Every trade pays full round-trip cost in points.

Author: Mykola (Mykola-Quant)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional
import numpy as np
import pandas as pd

# ---- NQ contract constants (frozen) ----------------------------------------
POINT_VALUE = 20.0          # $ per index point
TICK = 0.25                 # points
COMMISSION_RT_USD = 4.20    # round-trip commission, $
SLIPPAGE_TICKS_PER_FILL = 1 # ticks of slippage per fill (2 fills per trade)

ExitMode = Literal["eod", "ndays", "trailing"]


@dataclass
class Config:
    k: float = 0.5                      # breakout multiple of ATR
    atr_n: int = 14                     # ATR lookback (true-range proxy)
    exit_mode: ExitMode = "eod"
    hold_days: int = 1                  # for exit_mode == "ndays"
    trail_atr_mult: float = 2.0         # for exit_mode == "trailing"
    weekend_flat: bool = True           # force exit on Friday close
    direction: Literal["both", "long", "short"] = "both"
    # costs
    commission_rt_usd: float = COMMISSION_RT_USD
    slippage_ticks_per_fill: int = SLIPPAGE_TICKS_PER_FILL

    def rt_cost_points(self) -> float:
        """Round-trip cost expressed in index points."""
        comm_pts = self.commission_rt_usd / POINT_VALUE
        slip_pts = 2 * self.slippage_ticks_per_fill * TICK
        return comm_pts + slip_pts


def true_range(df: pd.DataFrame) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    return true_range(df).rolling(n, min_periods=n).mean()


@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    side: int            # +1 long, -1 short
    entry_px: float
    exit_px: float
    gross_pts: float
    net_pts: float
    reason: str


def backtest(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    df: DataFrame indexed by date with columns open, high, low, close.
        Must be chronologically sorted, one row per session.
    Returns a DataFrame of trades.
    """
    df = df.sort_index().copy()
    df["atr"] = atr(df, cfg.atr_n)

    # Reference values known at open of day t (shifted, no lookahead)
    df["ref_close"] = df["close"].shift(1)
    df["ref_atr"] = df["atr"].shift(1)
    df["buy_level"] = df["ref_close"] + cfg.k * df["ref_atr"]
    df["sell_level"] = df["ref_close"] - cfg.k * df["ref_atr"]

    rows = df.reset_index()
    date_col = rows.columns[0]
    cost = cfg.rt_cost_points()

    trades: list[Trade] = []
    i = 0
    n = len(rows)
    while i < n:
        r = rows.iloc[i]
        if pd.isna(r["buy_level"]) or pd.isna(r["ref_atr"]):
            i += 1
            continue

        o, h, l = r["open"], r["high"], r["low"]
        buy, sell = r["buy_level"], r["sell_level"]

        long_hit = (cfg.direction in ("both", "long")) and (h >= buy)
        short_hit = (cfg.direction in ("both", "short")) and (l <= sell)

        # buy-stop fills at buy_level, UNLESS price gapped above it at the open,
        # in which case the realistic fill is the open (worse). Symmetric for shorts.
        long_fill = max(o, buy)
        short_fill = min(o, sell)

        side = 0
        entry_px = np.nan
        if long_hit and short_hit:
            # deterministic tie-break: whichever level is nearer the open fills first
            if abs(o - buy) <= abs(o - sell):
                side, entry_px = +1, long_fill
            else:
                side, entry_px = -1, short_fill
        elif long_hit:
            side, entry_px = +1, long_fill
        elif short_hit:
            side, entry_px = -1, short_fill

        if side == 0:
            i += 1
            continue

        # ---- resolve exit ----
        exit_px, exit_idx, reason = _resolve_exit(rows, i, side, entry_px, cfg)

        gross = side * (exit_px - entry_px)
        net = gross - cost
        trades.append(Trade(
            entry_date=r[date_col],
            exit_date=rows.iloc[exit_idx][date_col],
            side=side,
            entry_px=float(entry_px),
            exit_px=float(exit_px),
            gross_pts=float(gross),
            net_pts=float(net),
            reason=reason,
        ))
        # advance past the exit day so trades don't overlap
        i = exit_idx + 1

    if not trades:
        return pd.DataFrame(columns=[
            "entry_date", "exit_date", "side", "entry_px", "exit_px",
            "gross_pts", "net_pts", "reason"])
    return pd.DataFrame([t.__dict__ for t in trades])


def _is_friday(ts) -> bool:
    return pd.Timestamp(ts).weekday() == 4


def _resolve_exit(rows: pd.DataFrame, entry_i: int, side: int,
                  entry_px: float, cfg: Config):
    """Return (exit_px, exit_row_index, reason)."""
    date_col = rows.columns[0]
    entry_row = rows.iloc[entry_i]

    # EOD: exit at close of entry day
    if cfg.exit_mode == "eod":
        return float(entry_row["close"]), entry_i, "eod"

    # weekend flat overrides any multi-day hold if entry day is Friday
    max_i = len(rows) - 1

    if cfg.exit_mode == "ndays":
        target = entry_i + cfg.hold_days
        # walk forward, forcing Friday-close exit if weekend_flat
        for j in range(entry_i, min(target, max_i) + 1):
            rj = rows.iloc[j]
            if cfg.weekend_flat and _is_friday(rj[date_col]):
                return float(rj["close"]), j, "weekend_flat"
        j = min(target, max_i)
        return float(rows.iloc[j]["close"]), j, "ndays"

    # trailing ATR stop
    if cfg.exit_mode == "trailing":
        ref_atr = entry_row["ref_atr"]
        trail = cfg.trail_atr_mult * ref_atr
        if side == +1:
            peak = entry_row["high"]
            stop = peak - trail
        else:
            peak = entry_row["low"]
            stop = peak + trail

        for j in range(entry_i, max_i + 1):
            rj = rows.iloc[j]
            h, l, c = rj["high"], rj["low"], rj["close"]
            if side == +1:
                if l <= stop:
                    return float(stop), j, "trail"
                peak = max(peak, h)
                stop = peak - trail
            else:
                if h >= stop:
                    return float(stop), j, "trail"
                peak = min(peak, l)
                stop = peak + trail
            if cfg.weekend_flat and _is_friday(rj[date_col]):
                return float(c), j, "weekend_flat"
        return float(rows.iloc[max_i]["close"]), max_i, "end_of_data"

    raise ValueError(f"unknown exit_mode {cfg.exit_mode}")


# ---- summary stats ---------------------------------------------------------

def summarize(trades: pd.DataFrame) -> dict:
    if len(trades) == 0:
        return {"n_trades": 0}
    net = trades["net_pts"]
    wins = (net > 0).sum()
    gross_win = net[net > 0].sum()
    gross_loss = -net[net < 0].sum()
    return {
        "n_trades": int(len(trades)),
        "net_pts_total": float(net.sum()),
        "net_usd_total": float(net.sum() * POINT_VALUE),
        "mean_net_pts": float(net.mean()),
        "median_net_pts": float(net.median()),
        "win_rate": float(wins / len(trades)),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else np.inf,
        "sharpe_per_trade": float(net.mean() / net.std(ddof=1)) if net.std(ddof=1) > 0 else 0.0,
        "max_dd_pts": float(_max_drawdown(net.cumsum())),
    }


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float((equity - peak).min())
