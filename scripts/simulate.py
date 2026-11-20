"""Replay deterministic synthetic events; retrying a run proves idempotency."""
import argparse
import json
import os
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000")
parser.add_argument("--run-id", default="demo")
args = parser.parse_args()
key = os.environ.get("SENTINEL_API_KEY")
if not key:
    parser.error("Set SENTINEL_API_KEY")
for i in range(12):
    payload = {"event_id": f"{args.run_id}-{i:02}", "camera_id": f"cam-{i % 3 + 1}",
               "kind": ["intrusion", "motion", "camera_offline"][i % 3],
               "confidence": 0.95 if i % 2 == 0 else 0.6,
               "zone": "restricted" if i % 2 == 0 else "lobby",
               "occurred_at": f"2026-01-01T10:00:{i:02}+00:00"}
    req = Request(args.url + "/api/events", data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json", "X-API-Key": key})
    with urlopen(req, timeout=5) as response:
        body = json.load(response)
        print(response.status, payload["event_id"], body["event"]["severity"],
              "duplicate=" + str(body["duplicate"]))
