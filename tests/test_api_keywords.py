"""Quick API test for keyword matching on live server."""
import requests
import json

BASE = "http://localhost:8000/parse"
tests = [
    "berojgar", "berozgaar", "gaav", "gaon", "28 sal", "28 saal",
    "boy", "purush", "unmarried", "shadi ho gayi hai",
    "aadhar card hai", "haan bank hai", "jamin nahi hai",
    "mai berojgar hu", "gaav mein rehta hu", "lady", "girl",
    "shahar mein", "dehaat mein", "nokri nahi hai",
]

passed = 0
failed = 0
for t in tests:
    r = requests.post(BASE, json={"message": t})
    fields = r.json()["extracted_fields"]
    if fields:
        passed += 1
        print(f"OK   | {t:30s} -> {json.dumps(fields)}")
    else:
        failed += 1
        print(f"FAIL | {t:30s} -> (empty)")

print(f"\n{passed} passed, {failed} failed out of {len(tests)}")
