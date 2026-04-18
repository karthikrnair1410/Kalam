import sys, json
sys.path.insert(0, '.')
from engine.intent_mapper import map_to_fields

tests = [
    "mere paas bank account nahi hai",
    "main kisan hu but land mere naam pe nahi hai",
    "meri income 2 lakh hai, UP mein rehta hu",
    "main 42 saal ka SC kisan hu, gaon mein rehta hu, aadhaar hai",
    "berozgaar hu, sheher mein rehta hu, family mein 4 log hain",
    "main vidhwa hu, bank account nahi hai, Bihar se hu",
    "mere paas 2 acre zameen hai, kiraaye pe kheti karta hu",
    "sarkari naukri hai, 35 saal ki umar, Maharashtra mein",
]

print()
for t in tests:
    r = map_to_fields(t)
    print(f"INPUT : {t}")
    print(f"FIELDS: {json.dumps(r['fields'], ensure_ascii=False)}")
    if r["warnings"]:
        print(f"WARN  : {r['warnings']}")
    print()
