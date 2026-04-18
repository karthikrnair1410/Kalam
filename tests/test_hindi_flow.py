"""Test pure Hindi (Devanagari) input through the chat API."""
import requests
import json

BASE = "http://localhost:8000/chat"

def chat(msg, session, lang="hi"):
    r = requests.post(BASE, json={"message": msg, "session_fields": session, "language": lang})
    return r.json()

# --- Test 1: Pure Hindi parse test ---
print("=" * 70)
print("PARSE TEST: Pure Hindi keywords")
print("=" * 70)
PARSE = "http://localhost:8000/parse"
hindi_tests = [
    ("मैं किसान हूँ", "occupation", "FARMER_OWNER"),
    ("मेरी उम्र 35 साल है", "age", 35),
    ("मैं बेरोजगार हूँ", "occupation", "UNEMPLOYED"),
    ("गाँव में रहता हूँ", "area_type", "RURAL"),
    ("शहर में रहता हूँ", "area_type", "URBAN"),
    ("मेरे पास आधार है", "aadhaar_linked", True),
    ("आधार नहीं है", "aadhaar_linked", False),
    ("बैंक खाता है", "bank_account", True),
    ("बैंक खाता नहीं है", "bank_account", False),
    ("शादीशुदा", "marital_status", "MARRIED"),
    ("विधवा हूँ", "marital_status", "WIDOWED"),
    ("मैं महिला हूँ", "gender", "FEMALE"),
    ("मैं पुरुष हूँ", "gender", "MALE"),
    ("मेरी सालाना आय 2 लाख है", "annual_income", 200000),
    ("ज़मीन नहीं है", "land_leasing_status", "NONE"),
    ("मेरे पास ज़मीन है", "land_leasing_status", "OWNER"),
    ("परिवार में 5 लोग हैं", "family_size", 5),
    ("अनुसूचित जाति", "caste_category", "SC"),
    ("अनुसूचित जनजाति", "caste_category", "ST"),
    ("देहात में रहता हूँ", "area_type", "RURAL"),
    ("मेरी आयु 40 वर्ष है", "age", 40),
    ("छात्र हूँ", "occupation", "STUDENT"),
    ("सरकारी नौकरी", "occupation", "SALARIED_GOVT"),
    ("खेती करता हूँ", "occupation", "FARMER_OWNER"),
    ("मजदूर हूँ", "occupation", "UNSKILLED_LABOURER"),
]

passed = 0
failed = 0
for text, field, expected in hindi_tests:
    r = requests.post(PARSE, json={"message": text})
    data = r.json()
    actual = data["extracted_fields"].get(field)
    if actual == expected:
        passed += 1
        print(f"  OK   | {text:30s} -> {field}={actual}")
    else:
        failed += 1
        print(f"  FAIL | {text:30s} -> {field}={actual} (expected {expected})")
        print(f"         normalized: {data.get('normalized_text','?')[:60]}")

print(f"\n  {passed} passed, {failed} failed out of {len(hindi_tests)}")

# --- Test 2: Full Hindi chat flow ---
print("\n" + "=" * 70)
print("CHAT FLOW TEST: Pure Hindi conversation")
print("=" * 70)

session = {}

steps = [
    ("मैं बेरोजगार हूँ, गाँव में रहता हूँ, उम्र 30 साल", "Initial multi-field"),
    ("पुरुष", "Gender"),
    ("उत्तर प्रदेश", "State"),  # might need UP fallback
    ("50000", "Income (bare number)"),
    ("ज़मीन नहीं है", "Land"),
    ("अनुसूचित जाति", "Caste SC"),
    ("5", "Family size"),
    ("हाँ", "Aadhaar (bare haan in Hindi)"),
    ("नहीं", "Bank (bare nahi in Hindi)"),
    ("अविवाहित", "Marital (unmarried in Hindi)"),
]

all_ok = True
for msg, label in steps:
    d = chat(msg, session)
    session = d["fields_collected"]
    next_f = d.get("next_question_field", "DONE")
    has_eval = d.get("evaluation") is not None
    print(f"  [{label:25s}] '{msg}' -> next={next_f}, fields={len(session)}" +
          (" -> EVALUATION!" if has_eval else ""))
    
    # Check for loop: if fields didn't increase and no evaluation
    if not has_eval and len(session) == 0:
        print(f"    >>> WARNING: No fields extracted!")
        all_ok = False

print(f"\n  Final fields: {json.dumps(session, indent=2, ensure_ascii=False)}")
print(f"\n  {'ALL HINDI STEPS COMPLETED!' if d.get('evaluation') else 'INCOMPLETE - check above for issues'}")
