"""
Fetch continuous front-month NQ daily OHLCV from Yahoo Finance and save it in the
exact CSV format load_data.py expects: Date,Open,High,Low,Close.

Usage:
    python fetch_nq.py                 # NQ=F futures, from 2008
    python fetch_nq.py ^NDX            # cash Nasdaq-100 index (much deeper history)
    python fetch_nq.py NQ=F 2010-01-01 # custom ticker + start date

Notes:
- NQ=F is Yahoo's continuous front-month E-mini Nasdaq-100 future (a stitched
  proxy, not institutional back-adjusted). Fine for a daily breakout falsification;
  note the source in the README.
- ^NDX is the cash index (no roll artifacts, history back to the 1980s). Use it if
  NQ=F comes back too short for a split-half OOS with power.
"""
import sys
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    sys.exit("yfinance is not installed. Run:  pip install yfinance")

ticker = sys.argv[1] if len(sys.argv) > 1 else "NQ=F"
start = sys.argv[2] if len(sys.argv) > 2 else "2008-01-01"

print(f"Downloading {ticker} daily from {start} ...")
# .history() returns single-level columns (Open/High/Low/Close/Volume), index=Date
df = yf.Ticker(ticker).history(start=start, interval="1d", auto_adjust=False)

if df is None or df.empty:
    sys.exit(f"No data returned for {ticker}. Try '^NDX' for the cash index, "
             f"or check the ticker/date.")

df = df.reset_index()
# normalise the date column (strip any timezone, keep the date only)
date_col = "Date" if "Date" in df.columns else df.columns[0]
df[date_col] = pd.to_datetime(df[date_col]).dt.tz_localize(None).dt.normalize()

out = df[[date_col, "Open", "High", "Low", "Close"]].copy()
out.columns = ["Date", "Open", "High", "Low", "Close"]
out = out.dropna().sort_values("Date")

path = "NQ_continuous_daily.csv"
out.to_csv(path, index=False)
print(f"Saved {len(out)} sessions -> {path}")
print(f"Range: {out['Date'].min().date()} .. {out['Date'].max().date()}")
print(out.head(3).to_string(index=False))
