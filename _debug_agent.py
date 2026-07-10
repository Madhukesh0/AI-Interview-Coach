# -*- coding: utf-8 -*-
"""
Run this script to see exactly what the agent returns and how it's parsed.
Usage: python _debug_agent.py
"""
import sys, json
sys.path.insert(0, '.')

from auth import get_iam_token
from agent import _split_json_objects, _parse_sse_events, _extract_text_from_stream, _extract_thread_id
import requests, os
from dotenv import load_dotenv
load_dotenv()

INSTANCE_URL   = os.getenv("INSTANCE_URL")
AGENT_ID       = os.getenv("AGENT_ID")
ENVIRONMENT_ID = os.getenv("ENVIRONMENT_ID")

print("=== Step 1: Getting IAM token ===")
token = get_iam_token()
print("Token OK:", token[:20], "...")

print("\n=== Step 2: Calling agent ===")
url = f"{INSTANCE_URL.rstrip('/')}/v1/orchestrate/runs?stream=true&stream_timeout=120000&multiple_content=true"
payload = {
    "message": {"role": "user", "content": "Give me 1 interview question for a software engineer"},
    "agent_id": AGENT_ID,
    "environment_id": ENVIRONMENT_ID,
}
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "text/event-stream",
}

resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=130)
print("Status:", resp.status_code)

raw = resp.content.decode("utf-8", errors="replace")
print("\n=== Step 3: Raw response (first 1000 chars) ===")
print(raw[:1000])

print("\n=== Step 4: Split into JSON objects ===")
objects = _split_json_objects(raw)
print(f"Found {len(objects)} objects")
for i, obj in enumerate(objects):
    event = obj.get("event", "NO_EVENT")
    data  = obj.get("data", {})
    print(f"  [{i}] event={event}  data_keys={list(data.keys()) if isinstance(data, dict) else type(data)}")
    if event in ("message.delta", "message.created", "message.completed"):
        print("       >>> DATA:", json.dumps(data, indent=4)[:600])

print("\n=== Step 5: Extracted text ===")
text = _extract_text_from_stream(raw)
print(repr(text))

print("\n=== Step 6: Thread ID ===")
tid = _extract_thread_id(raw, "fallback")
print(tid)
