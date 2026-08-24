import base64
import json
import os

import boto3

MODEL_ID = os.environ.get("BEDROCK_IMAGE_MODEL_ID", "stability.stable-image-core-v1:1")
IMAGE_REGION = os.environ.get("BEDROCK_IMAGE_REGION", "us-west-2")

VISUAL_CUES = {
    "euphoric": "bright vibrant golds and warm oranges, upward sweeping dynamic brushstrokes, radiant energy",
    "calm": "soft blues and pale neutrals, smooth flowing gentle curves, tranquil balanced composition",
    "anxious": "jagged fragmented forms, muted greys and sickly yellow-greens, tense uneven composition",
    "volatile": "chaotic clashing colors, sharp angular shards, high contrast, fractured composition",
    "bearish": "deep reds and dark blacks, heavy downward-falling forms, oppressive weighted composition",
}


def get_client():
    return boto3.client("bedrock-runtime", region_name=IMAGE_REGION)


def build_prompt(narrative: str, label: str) -> str:
    cues = VISUAL_CUES.get(label, VISUAL_CUES["calm"])
    return (
        f"Abstract expressionist painting capturing a '{label}' market mood. {cues}. "
        f"Mood inspiration: {narrative}"
    )


def generate_art(narrative: str, label: str) -> bytes:
    prompt = build_prompt(narrative, label)
    body = {
        "prompt": prompt[:1024],
        "aspect_ratio": "1:1",
        "mode": "text-to-image",
        "output_format": "png",
    }

    client = get_client()
    response = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    payload = json.loads(response["body"].read())
    image_b64 = payload["images"][0]
    return base64.b64decode(image_b64)
