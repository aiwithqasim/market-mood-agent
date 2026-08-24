import os

import numpy as np
import pandas as pd
import snowflake.connector


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ["SNOWFLAKE_ROLE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )


def fetch_ohlcv(ticker: str, lookback_days: int = 30, as_of_date: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    if as_of_date is None:
        cur.execute(
            """
            SELECT trade_date, open, high, low, close, volume
            FROM OHLCV_DAILY
            WHERE ticker = %s
            ORDER BY trade_date DESC
            LIMIT %s
            """,
            (ticker, lookback_days),
        )
    else:
        cur.execute(
            """
            SELECT trade_date, open, high, low, close, volume
            FROM OHLCV_DAILY
            WHERE ticker = %s AND trade_date <= %s
            ORDER BY trade_date DESC
            LIMIT %s
            """,
            (ticker, as_of_date, lookback_days),
        )
    rows = cur.fetchall()
    cols = ["trade_date", "open", "high", "low", "close", "volume"]
    df = pd.DataFrame(rows, columns=cols).sort_values("trade_date").reset_index(drop=True)
    return df


def compute_signals(df: pd.DataFrame, volatility_window: int = 10, momentum_window: int = 5) -> dict:
    df = df.copy()
    df["daily_return"] = df["close"].pct_change()

    volatility = df["daily_return"].tail(volatility_window).std()

    avg_volume = df["volume"].mean()
    today_volume = df["volume"].iloc[-1]
    volume_anomaly = (today_volume - avg_volume) / avg_volume

    momentum_slice = df["close"].tail(momentum_window)
    momentum_pct = (momentum_slice.iloc[-1] - momentum_slice.iloc[0]) / momentum_slice.iloc[0] * 100

    return {
        "run_date": df["trade_date"].iloc[-1],
        "volatility": float(volatility),
        "volume_anomaly": float(volume_anomaly),
        "momentum_pct": float(momentum_pct),
    }


def get_mood_signals(ticker: str, lookback_days: int = 30, as_of_date: str | None = None) -> dict:
    df = fetch_ohlcv(ticker, lookback_days, as_of_date)
    signals = compute_signals(df)
    signals["ticker"] = ticker
    return signals


def list_trading_dates(ticker: str) -> list[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT trade_date FROM OHLCV_DAILY WHERE ticker = %s ORDER BY trade_date",
        (ticker,),
    )
    return [row[0].isoformat() for row in cur.fetchall()]
