CREATE TABLE IF NOT EXISTS STOCKS_MMA_DB.STOCKS_MMA_SCHEMA.OHLCV_DAILY (
    trade_date  DATE,
    ticker      STRING,
    open        FLOAT,
    high        FLOAT,
    low         FLOAT,
    close       FLOAT,
    volume      NUMBER,
    loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
