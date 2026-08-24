# Market Mood Agent

A self-running creative agent that reads real market data, computes a "mood," generates an abstract art piece + narrative via AWS Bedrock, and tracks its own accuracy over time.

Built for the AWS Weekend Challenge (Deadline: **Aug 24, 2026, 1:00 PM PT**). Originally scoped to extend an existing `real-time-stock-data-pipeline` (Kafka/KRaft → Postgres → Snowflake `STOCKS_MDS`) — that database turned out not to exist in this Snowflake account, so this project pulls its own real OHLCV data instead (see data-source note below).

> **Region note:** this project runs in `us-east-1`, not the originally planned `us-west-2`/`ap-southeast-1`. `amazon.nova-canvas-v1:0` (image generation) is only available in `us-east-1` among the regions checked — confirmed via `aws bedrock list-foundation-models`. Bedrock text calls (Nova Lite) and S3/Snowflake I/O all run in `us-east-1` too, to keep everything in one region.

> **Data-source note:** `STOCKS_MDS` (the assumed existing pipeline database) doesn't exist in this Snowflake account (`HESRRAE-PAB97201`) — confirmed via `SHOW DATABASES`. Source OHLCV data instead comes from `yfinance` (Yahoo Finance, free, no API key), loaded into `STOCKS_MMA_DB.STOCKS_MMA_SCHEMA.OHLCV_DAILY` via `scripts/load_ohlcv.py`. It's still real market data, just sourced directly rather than via the Kafka pipeline.

---

## Architecture

```
OHLCV_DAILY (Snowflake, STOCKS_MMA_DB — loaded via yfinance)
        │
Airflow DAG: market_mood_agent
        │
        ├─ 1. query_mood_signals    → pull volatility, volume anomaly, momentum
        ├─ 2. compute_mood_score    → weighted score (-1 to +1) + label
        ├─ 3. generate_narrative    → Bedrock (Nova Lite / Claude) 2–3 sentence mood text
        ├─ 4. generate_art          → Bedrock Nova Canvas, abstract image from narrative
        ├─ 5. persist                → image → S3, metrics+narrative → S3 JSON + MOOD_HISTORY table
        └─ 6. score_yesterday        → compare yesterday's mood vs today's realized volatility
                                        → logs accuracy delta (this is the "gets better" mechanism)
```

**Given the tight deadline, this is scoped to ship, not to be exhaustive:**
- No new Lambda — Airflow task calls `bedrock-runtime` directly via boto3. Still qualifies (Bedrock + S3 + existing AWS stack satisfies "deploy on at least one AWS service").
- One ticker/basket to start (e.g. SPY or your existing tracked symbols).
- Backfill 5–10 days of *real* historical data (loaded via `yfinance` into `OHLCV_DAILY`), so the accuracy-over-time chart is genuine on day one instead of needing to wait a week.

---

## Time-boxed plan (execute in order)

### Phase 0 — Setup (15 min)
- [x] Dockerized Airflow (+ its own Postgres metadata DB) via `docker-compose.yml` / `Dockerfile` — see below, no Kafka needed (this project only reads from Snowflake, doesn't consume the stream directly)
- [x] AWS CLI access confirmed; Bedrock model access confirmed for Nova Lite + Nova Canvas in `us-east-1`
- [x] `boto3` + rest of `requirements.txt` installed into the Airflow image
- [x] AWS creds mounted read-only into the container (`~/.aws` → `/home/airflow/.aws`), Snowflake creds in `.env`
- [ ] Create new S3 bucket in `us-east-1` (the existing pipeline's bucket is region-locked to us-west-2): `aws s3 mb s3://s3-market-mood-agent-us-east-1 --region us-east-1`
- [ ] Create S3 prefix: `s3://s3-market-mood-agent-us-east-1/market-mood/`

### Phase 1 — Snowflake schema (15 min)
- [x] Create `MOOD_HISTORY` table — in its own dedicated database/schema (`STOCKS_MMA_DB.STOCKS_MMA_SCHEMA`):
  ```sql
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
  ```
- [x] Create `OHLCV_DAILY` table (source data, since `STOCKS_MDS` doesn't exist) — see `sql/ohlcv_daily.sql`
- [x] Load real OHLCV data via `scripts/load_ohlcv.py` (`yfinance`, ticker from `TARGET_TICKERS`) — **loaded 20 trading days of SPY data**, clears the ≥10 day requirement
  > Both `OHLCV_DAILY` (source) and `MOOD_HISTORY` (output) now live in the same `STOCKS_MMA_DB.STOCKS_MMA_SCHEMA` — one database, one connection, no cross-database queries needed.

### Phase 2 — Mood scoring logic (30–45 min)
- [x] `mood/signals.py` — `fetch_ohlcv()` pulls from `OHLCV_DAILY`; `compute_signals()` returns volatility (10-day stddev of daily returns), volume anomaly (vs mean of the fetched window), momentum (5-day % change)
- [x] `mood/score.py` — `compute_mood_score()`: weighted sum (momentum 0.5, volatility -0.3, volume anomaly ±0.2 signed by momentum direction), clipped to [-1, 1] → label via threshold buckets (euphoric ≥0.4 / bearish ≤-0.4 / anxious ≤-0.1 / volatile if normalized volatility >0.75 / else calm)
- [x] Unit-tested via `scripts/test_mood.py` against real `OHLCV_DAILY` rows — SPY 2026-08-21: volatility 0.00494, volume_anomaly -0.155, momentum -0.899%, **score -0.063, label "calm"**
  > Required adding `PYTHONPATH=/opt/airflow` to `docker-compose.yml` so `mood/` is importable from scripts outside its own directory — same fix will be needed for the DAG in Phase 4.

### Phase 3 — Bedrock integration (45–60 min)
- [x] `mood/narrative.py` — `bedrock-runtime` client in `us-east-1`, `invoke_model` on `amazon.nova-lite-v1:0`, prompt built from score + raw signals → 2-3 sentence narrative
- [x] `mood/art.py` — **switched from Nova Canvas to `stability.stable-image-core-v1:1`** (see note below), prompt built from narrative + a per-label visual-cue dictionary (color palette, brushwork, composition) → returns PNG bytes
- [x] Tested both standalone via `scripts/test_bedrock.py` against real signals — narrative + a real 1024x1024 abstract painting generated successfully, saved to `logs/test_art.png`

  > **What broke:** `amazon.nova-canvas-v1:0` — the model the whole plan was built around — is marked `LEGACY` by AWS in every region that offers it (`us-east-1`, `ap-northeast-1`), with invoke access auto-revoked after 30 days of account inactivity. AWS also retired the old "Model access" console page (models now auto-enable on first invoke) — but that auto-enable path explicitly does **not** apply to legacy models, confirmed by re-invoking and getting the identical `ResourceNotFoundException`. There is no active Amazon text-to-image model in this account at all (Titan Image Generator isn't in the catalog either). The fix: Stability AI's `stable-image-core-v1:1` is a genuine active text-to-image model, but only in `us-west-2`, not `us-east-1` where the rest of this project runs — so `mood/art.py` opens a second `bedrock-runtime` client scoped to `us-west-2` (`BEDROCK_IMAGE_REGION` env var) while narrative + S3 + Snowflake stay in `us-east-1`. Request/response schema is also completely different from Nova Canvas's `taskType`/`textToImageParams` format — Stability uses a flat `{prompt, aspect_ratio, mode, output_format}` body.

### Phase 4 — Airflow DAG (45–60 min)
- [x] `dags/market_mood_agent.py` — TaskFlow API, tasks 1–6 wired as described in architecture above
- [x] Task 5 (`persist`): write image + metrics JSON to S3, **`MERGE` into `MOOD_HISTORY`** (upsert on `run_date` + `ticker`, not a plain `INSERT` — see note below)
- [x] Task 6 (`score_yesterday`): pulls the most recent prior row's `predicted_next_day_vol`, compares to today's realized volatility, `UPDATE`s `accuracy_delta` on that row. No-ops gracefully on the first-ever run (no prior row to score).
- [x] Schedule: `30 21 * * 1-5` UTC (~4:30 PM ET), `catchup=False`
- [x] Triggered manual DAG runs via `airflow dags trigger` (CLI + confirmed in UI) — all 6 tasks green, verified real rows in `MOOD_HISTORY` via Snowsight

  > **What broke:** two things. (1) Newly-added DAGs are **paused by default** in Airflow — `airflow dags trigger` still queues a `DagRun`, but the scheduler never creates its `TaskInstance`s while paused, so the run sits at `queued` forever with no error anywhere. Fixed with `airflow dags unpause market_mood_agent`. (2) Running the DAG twice (once manually, once from an auto-created catch-up run right after unpausing) wrote **two identical rows** into `MOOD_HISTORY` for the same `run_date`/`ticker` — the original `persist` task used a plain `INSERT` with no uniqueness constraint. Fixed by switching to a Snowflake `MERGE` (upsert keyed on `run_date` + `ticker`) and manually deduping the one pair of rows that had already landed. Verified idempotency by triggering a third run and confirming the row count stayed at 1.

### Phase 5 — Backfill (30 min)
- [x] `scripts/backfill.py` — loops over the last 10 trading days in `OHLCV_DAILY`, runs steps 1–3 for each, generates art for 3 representative days only (first/middle/last) to save Bedrock cost/time, populates `MOOD_HISTORY` via the same `mood/persist.py` helpers the live DAG uses
- [x] Backfilled 10 real trading days of SPY — genuine variation in mood (anxious/calm mix, not a flat line), and 9 of 10 days have a real `accuracy_delta` (predicted vol from day N vs. realized vol on day N+1); only the most recent day is correctly left unscored, to be closed out by tomorrow's live DAG run

  > Required extending `mood/signals.py` with an `as_of_date` parameter — without it, every backfilled day would compute its volatility/momentum using the *full* 20-day window (including future days relative to that backfill date), which would silently leak future data into past predictions and make the accuracy chart meaningless. Also refactored the DAG's inline `persist`/`score_yesterday` SQL into `mood/persist.py` so the DAG and the backfill script share one code path instead of two copies that could drift.

### Phase 6 — Gallery / proof surface (30–45 min)
- [x] `streamlit_app.py` — mood score + accuracy line charts at the top, daily gallery below (art + narrative + predicted/actual/delta per day), newest first
- [x] Runs as its own `docker-compose` service (`streamlit`), reusing the same built image and `mood/` package — `docker compose up -d streamlit`, then open `http://localhost:8501`
- [x] Verified the app's actual data path (Snowflake query + S3 image fetch) works against real data, not just that the page loads
- [ ] Take screenshots now — you'll need these for the Builder Center article regardless of final polish

  > Note: the Airflow base image's entrypoint intercepts unrecognized commands and prepends `airflow` to them — `command: streamlit run ...` silently became `airflow streamlit run ...` and printed Airflow's CLI help instead of starting Streamlit. Fixed by wrapping in `bash -c "..."`, which the entrypoint passes through untouched.

### Phase 7 — Builder Center article (45–60 min)
- [ ] 500+ words, cover: what you built, why (tie to your existing pipeline), how (architecture), **what broke** (be specific — this is what makes these articles credible)
- [ ] Include repo link or live link
- [ ] Publish between Aug 21–24 window

### Phase 8 — Submit (10 min)
- [ ] Verify: deployed on ≥1 AWS service ✅ (Bedrock + S3 + your existing stack)
- [ ] Verify: article published, 500+ words ✅
- [ ] Verify: repo/live link included ✅
- [ ] Submit via link in AWS Developers post comments before **Aug 24, 1:00 PM PT**

---

## Repo structure

```
market-mood-agent/
├── dags/
│   └── market_mood_agent.py
├── mood/
│   ├── signals.py
│   ├── score.py
│   ├── narrative.py
│   ├── art.py
│   └── persist.py             # shared S3/Snowflake persistence, used by both the DAG and backfill.py
├── scripts/
│   ├── load_ohlcv.py
│   ├── test_mood.py
│   ├── test_bedrock.py
│   └── backfill.py
├── streamlit_app.py          # optional gallery
├── sql/
│   └── mood_history.sql
├── Dockerfile                 # apache/airflow base + requirements.txt
├── docker-compose.yml         # airflow (standalone) + airflow-postgres (metadata DB)
├── .env.example               # copy to .env, fill in Snowflake creds
└── README.md
```

## Environment variables / config

```
AWS_REGION=us-east-1
S3_BUCKET=s3-market-mood-agent-us-east-1
SNOWFLAKE_DATABASE=STOCKS_MMA_DB
SNOWFLAKE_SCHEMA=STOCKS_MMA_SCHEMA
BEDROCK_TEXT_MODEL_ID=amazon.nova-lite-v1:0
BEDROCK_IMAGE_MODEL_ID=stability.stable-image-core-v1:1
BEDROCK_IMAGE_REGION=us-west-2       # narrative/S3/Snowflake stay in AWS_REGION (us-east-1); only the image call crosses to us-west-2
TARGET_TICKERS=SPY   # start with one, expand later
```

## Cut-list if time runs short

Priority order — cut from the bottom if the clock is against you:
1. ~~Multiple tickers~~ → one ticker only
2. ~~Streamlit gallery~~ → screenshots of raw S3 output are enough for the article
3. ~~Full 10-day backfill~~ → 3–5 days is enough to show a trend line
4. ~~score_yesterday accuracy loop~~ → only cut this as an absolute last resort — it's the single thing that differentiates this from a generic prompt-wrapper submission
