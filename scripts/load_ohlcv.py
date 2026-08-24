import os

import snowflake.connector
import yfinance as yf

TICKER = os.environ["TARGET_TICKERS"].split(",")[0].strip()


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


def main():
    df = yf.download(TICKER, period="20d", interval="1d", auto_adjust=True)
    df = df.dropna()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(open("/opt/airflow/sql/ohlcv_daily.sql").read())

    rows = [
        (
            idx.date().isoformat(),
            TICKER,
            float(row["Open"].iloc[0]) if hasattr(row["Open"], "iloc") else float(row["Open"]),
            float(row["High"].iloc[0]) if hasattr(row["High"], "iloc") else float(row["High"]),
            float(row["Low"].iloc[0]) if hasattr(row["Low"], "iloc") else float(row["Low"]),
            float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"]),
            int(row["Volume"].iloc[0]) if hasattr(row["Volume"], "iloc") else int(row["Volume"]),
        )
        for idx, row in df.iterrows()
    ]

    cur.executemany(
        """
        INSERT INTO OHLCV_DAILY (trade_date, ticker, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    conn.commit()
    print(f"Loaded {len(rows)} trading days of {TICKER} OHLCV data")


if __name__ == "__main__":
    main()
