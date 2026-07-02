"""
Load continuous front-month NQ daily OHLCV from CSV into the engine's format.

Expected output: a DataFrame indexed by DatetimeIndex with lowercase columns
open, high, low, close (volume optional). Tries to be forgiving about column
naming and date formats; fails loudly if it can't find OHLC.
"""

from __future__ import annotations
import pandas as pd

_ALIASES = {
    "open": ["open", "o", "Open", "OPEN"],
    "high": ["high", "h", "High", "HIGH"],
    "low": ["low", "l", "Low", "LOW"],
    "close": ["close", "c", "Close", "CLOSE", "last", "Last", "settle", "Settle"],
}
_DATE_ALIASES = ["date", "Date", "DATE", "timestamp", "Timestamp", "datetime", "time", "Time"]


def load_ohlcv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # find date column
    date_col = next((c for c in df.columns if c in _DATE_ALIASES), None)
    if date_col is None:
        # assume first column is the date/index
        date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], utc=False, errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()

    rename = {}
    for target, names in _ALIASES.items():
        hit = next((c for c in df.columns if c in names), None)
        if hit is None:
            raise ValueError(f"Could not find a '{target}' column in {list(df.columns)}")
        rename[hit] = target
    df = df.rename(columns=rename)[["open", "high", "low", "close"]].astype(float)

    # basic integrity checks
    bad = df[(df["high"] < df["low"]) |
             (df["high"] < df["open"]) | (df["high"] < df["close"]) |
             (df["low"] > df["open"]) | (df["low"] > df["close"])]
    if len(bad):
        print(f"[warn] {len(bad)} rows violate OHLC ordering; check your roll-adjustment.")
    df = df[~df.index.duplicated(keep="first")]
    return df


if __name__ == "__main__":
    import sys
    from validate import run_falsification
    if len(sys.argv) < 2:
        print("usage: python load_data.py <path_to_ohlcv.csv> [label]")
        raise SystemExit(1)
    label = sys.argv[2] if len(sys.argv) > 2 else "NQ"
    df = load_ohlcv(sys.argv[1])
    print(f"Loaded {len(df)} sessions: {df.index.min().date()} -> {df.index.max().date()}")
    run_falsification(df, label)
