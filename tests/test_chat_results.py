"""
Test: multi-turn chat reaches evaluation and returns structured output
that is compatible with the adaptChatEval() frontend function.
"""
import urllib.request, json, sys

API = "http://localhost:8000"

def chat(msg, session, lang="hinglish"):
    payload = json.dumps({"message": msg, "session_fields": session, "language": lang}).encode()
    req = urllib.request.Request(
        f"{API}/chat", data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

turns = [
    "main kisan hu, UP mein rehta hu, 42 saal",
    "SC category, gaon mein rehta hu",
    "income 72000, family mein 5 log",
    "zameen 1.5 hectare, apni zameen hai",
    "aadhaar hai, bank account bhi hai, shaadishuda hu",
]

session = {}
eval_result = None

for i, msg in enumerate(turns, 1):
    r = chat(msg, session)
    session = r.get("fields_collected", {})
    print(f"\n--- Turn {i}: {msg[:50]} ---")
    print(f"  ACK : {r.get('acknowledgment_text','')[:70]}")
    next_text = r.get('next_question_text') or '(none)'
    print(f"  NEXT: {next_text[:60]}")
    print(f"  EVAL: {bool(r.get('evaluation'))}")
    if r.get("evaluation"):
        eval_result = r["evaluation"]
        break

if eval_result is None:
    print("\n[FAIL] No evaluation returned after all turns!")
    sys.exit(1)

# Check the keys that adaptChatEval() needs
print("\n=== Evaluation payload structure ===")
required_keys = [
    "structured", "user_explanation_hinglish",
    "eligible_hinglish", "partial_hinglish", "uncertain_hinglish",
    "next_steps_hinglish", "document_checklist_hinglish", "caveat_hinglish"
]
all_ok = True
for k in required_keys:
    present = k in eval_result
    v = eval_result.get(k)
    preview = str(v)[:70] if v else "(empty)"
    status = "✅" if present else "❌"
    print(f"  {status} {k}: {preview}")
    if not present:
        all_ok = False

# Check structured_output sub-keys
s = eval_result.get("structured", {})
print("\nstructured keys:", list(s.keys()))
print("summary:", s.get("summary"))
print("eligible count:", len(s.get("eligible_schemes", [])))
print("partial count: ", len(s.get("partially_eligible_schemes", [])))

if all_ok:
    print("\n[PASS] All adaptChatEval() keys present.")
else:
    print("\n[FAIL] Some keys missing — frontend adaptChatEval will return empty values.")
    sys.exit(1)
