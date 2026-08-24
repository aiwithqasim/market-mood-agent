import json
import os

import boto3

MODEL_ID = os.environ.get("BEDROCK_TEXT_MODEL_ID", "amazon.nova-lite-v1:0")


def get_client():
    return boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION"])


def build_prompt(ticker: str, score: float, label: str, signals: dict) -> str:
    return (
        f"You are a market mood narrator. Write exactly 2-3 sentences describing today's "
        f"trading mood for {ticker}, given these metrics:\n"
        f"- mood score: {score:.3f} (range -1 bearish to +1 euphoric)\n"
        f"- mood label: {label}\n"
        f"- volatility (10-day stddev of daily returns): {signals['volatility']:.4f}\n"
        f"- volume anomaly (vs recent average): {signals['volume_anomaly']:.2%}\n"
        f"- momentum (5-day price change): {signals['momentum_pct']:.2f}%\n\n"
        f"Write it as an evocative, human description of the market's 'mood', not a dry "
        f"stats summary. No preamble, just the narrative."
    )


def generate_narrative(ticker: str, score: float, label: str, signals: dict) -> str:
    prompt = build_prompt(ticker, score, label, signals)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 300, "temperature": 0.7, "topP": 0.9},
    }

    client = get_client()
    response = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    payload = json.loads(response["body"].read())
    return payload["output"]["message"]["content"][0]["text"].strip()
