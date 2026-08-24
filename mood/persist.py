import json
import os

import boto3

from mood.signals import get_connection


def get_s3_client():
    return boto3.client("s3", region_name=os.environ["AWS_REGION"])


def upload_metrics(ticker: str, run_date: str, signals: dict, mood: dict, narrative: str) -> str:
    key = f"market-mood/{ticker}/{run_date}/metrics.json"
    get_s3_client().put_object(
        Bucket=os.environ["S3_BUCKET"],
        Key=key,
        Body=json.dumps({**signals, **mood, "narrative": narrative}),
        ContentType="application/json",
    )
    return key


def upload_image(ticker: str, run_date: str, image_bytes: bytes) -> str:
    key = f"market-mood/{ticker}/{run_date}/art.png"
    get_s3_client().put_object(
        Bucket=os.environ["S3_BUCKET"], Key=key, Body=image_bytes, ContentType="image/png"
    )
    return key


def upsert_mood_history(
    ticker: str,
    run_date: str,
    signals: dict,
    mood: dict,
    narrative: str,
    image_s3_key: str | None,
    predicted_next_day_vol: float,
) -> None:
    conn = get_connection()
    conn.cursor().execute(
        """
        MERGE INTO MOOD_HISTORY AS target
        USING (SELECT %s AS run_date, %s AS ticker) AS source
        ON target.run_date = source.run_date AND target.ticker = source.ticker
        WHEN MATCHED THEN UPDATE SET
            volatility = %s, volume_anomaly = %s, momentum_pct = %s,
            mood_score = %s, mood_label = %s, narrative = %s,
            image_s3_key = %s, predicted_next_day_vol = %s
        WHEN NOT MATCHED THEN INSERT (
            run_date, ticker, volatility, volume_anomaly, momentum_pct,
            mood_score, mood_label, narrative, image_s3_key, predicted_next_day_vol
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            run_date, ticker,
            signals["volatility"], signals["volume_anomaly"], signals["momentum_pct"],
            mood["score"], mood["label"], narrative, image_s3_key, predicted_next_day_vol,
            run_date, ticker,
            signals["volatility"], signals["volume_anomaly"], signals["momentum_pct"],
            mood["score"], mood["label"], narrative, image_s3_key, predicted_next_day_vol,
        ),
    )
    conn.commit()


def get_previous_predicted(ticker: str, before_date: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT run_date, predicted_next_day_vol
        FROM MOOD_HISTORY
        WHERE ticker = %s AND run_date < %s AND predicted_next_day_vol IS NOT NULL
        ORDER BY run_date DESC
        LIMIT 1
        """,
        (ticker, before_date),
    )
    return cur.fetchone()


def update_accuracy(ticker: str, run_date: str, actual_next_day_vol: float, accuracy_delta: float) -> None:
    conn = get_connection()
    conn.cursor().execute(
        """
        UPDATE MOOD_HISTORY
        SET actual_next_day_vol = %s, accuracy_delta = %s
        WHERE ticker = %s AND run_date = %s
        """,
        (actual_next_day_vol, accuracy_delta, ticker, run_date),
    )
    conn.commit()
