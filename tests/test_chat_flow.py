"""End-to-end chat flow test simulating a complete profile collection with Hinglish variations."""
import requests
import json

BASE = "http://localhost:8000/chat"

def chat(msg, session, lang="hinglish"):
    r = requests.post(BASE, json={"message": msg, "session_fields": session, "language": lang})
    d = r.json()
    return d

# Step 1: Initial message with multiple fields
session = {}
print("=" * 70)
print("STEP 1: 'mai berojgar hu, gaav mein rehta hu, 28 sal ka hu'")
d = chat("mai berojgar hu, gaav mein rehta hu, 28 sal ka hu", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d['next_question_field']}")
print(f"  Ack: {d['acknowledgment_hinglish'][:100]}")

# Step 2: Answer gender
print("\n" + "=" * 70)
print("STEP 2: 'boy'")
d = chat("boy", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d['next_question_field']}")

# Step 3: Answer state
print("\n" + "=" * 70)
print("STEP 3: 'UP'")
d = chat("UP", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d['next_question_field']}")

# Step 4: Income with 'lak'
print("\n" + "=" * 70)
print("STEP 4: '2 lak'")
d = chat("2 lak", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d['next_question_field']}")

# Step 5: Land with jamin
print("\n" + "=" * 70)
print("STEP 5: 'jamin nahi hai'")
d = chat("jamin nahi hai", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d['next_question_field']}")

# Step 6: Caste
print("\n" + "=" * 70)
print("STEP 6: 'SC'")
d = chat("SC", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d['next_question_field']}")

# Step 7: Family size - bare number
print("\n" + "=" * 70)
print("STEP 7: '4'")
d = chat("4", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d['next_question_field']}")

# Step 8: Aadhaar - BARE 'haan' (THE CRITICAL LOOP FIX)
print("\n" + "=" * 70)
print("STEP 8: 'haan' (for aadhaar)")
d = chat("haan", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d['next_question_field']}")
aadhaar_ok = session.get("aadhaar_linked") == True
print(f"  >>> AADHAAR EXTRACTED? {'YES' if aadhaar_ok else 'NO - STILL LOOPING!'}")

# Step 9: Bank - BARE 'nhi' (ANOTHER CRITICAL LOOP FIX)
print("\n" + "=" * 70)
print("STEP 9: 'nhi' (for bank)")
d = chat("nhi", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d['next_question_field']}")
bank_ok = session.get("bank_account") == False
print(f"  >>> BANK EXTRACTED? {'YES' if bank_ok else 'NO - STILL LOOPING!'}")

# Step 10: Marital - unmarried
print("\n" + "=" * 70)
print("STEP 10: 'unmarried'")
d = chat("unmarried", session)
session = d["fields_collected"]
print(f"  Fields: {json.dumps(session)}")
print(f"  Next Q: {d.get('next_question_field', 'NONE - ALL DONE')}")
has_eval = d.get("evaluation") is not None
print(f"  >>> EVALUATION TRIGGERED? {'YES' if has_eval else 'NO'}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
checks = [
    ("age=28", session.get("age") == 28),
    ("gender=MALE", session.get("gender") == "MALE"),
    ("area=RURAL", session.get("area_type") == "RURAL"),
    ("occupation=UNEMPLOYED", session.get("occupation") == "UNEMPLOYED"),
    ("state=IN-UP", session.get("state") == "IN-UP"),
    ("income=200000", session.get("annual_income") == 200000),
    ("land=NONE", session.get("land_leasing_status") == "NONE"),
    ("caste=SC", session.get("caste_category") == "SC"),
    ("family=4", session.get("family_size") == 4),
    ("aadhaar=True (bare haan)", aadhaar_ok),
    ("bank=False (bare nhi)", bank_ok),
    ("marital=SINGLE", session.get("marital_status") == "SINGLE"),
    ("evaluation triggered", has_eval),
]
all_pass = True
for label, ok in checks:
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  {status}: {label}")

print(f"\n{'ALL CHECKS PASSED - NO LOOPS!' if all_pass else 'SOME CHECKS FAILED'}")
