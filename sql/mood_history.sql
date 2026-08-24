CREATE DATABASE STOCKS_MMA_DB;
CREATE SCHEMA STOCKS_MMA_SCHEMA;

CREATE TABLE IF NOT EXISTS STOCKS_MMA_DB.STOCKS_MMA_SCHEMA.MOOD_HISTORY (
    run_date        DATE,
    ticker          STRING,
    volatility      FLOAT,
    volume_anomaly  FLOAT,
    momentum_pct    FLOAT,
    mood_score      FLOAT,
    mood_label      STRING,
    narrative       STRING,
    image_s3_key    STRING,
    predicted_next_day_vol FLOAT,
    actual_next_day_vol    FLOAT,
    accuracy_delta         FLOAT,
    created_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
