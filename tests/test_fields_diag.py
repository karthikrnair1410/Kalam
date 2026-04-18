"""
Diagnose exactly which fields are missing after the 5 test turns.
"""
import sys
sys.path.insert(0, r"C:\Users\karth\OneDrive\Desktop\Task\kalam")
from engine.intent_mapper import map_to_fields, MANDATORY_FIELDS

turns = [
    "main kisan hu, UP mein rehta hu, 42 saal",
    "SC category, gaon mein rehta hu",
    "income 72000, family mein 5 log",
    "zameen 1.5 hectare, apni zameen hai",
    "aadhaar hai, bank account bhi hai, shaadishuda hu",
]

session = {}
for i, msg in enumerate(turns, 1):
    r = map_to_fields(msg)
    new_fields = r["fields"]
    session = {**session, **new_fields}
    print(f"--- Turn {i}: {msg[:50]}")
    print(f"  Extracted this turn: {list(new_fields.keys())}")
    print(f"  Accumulated fields:  {list(session.keys())}")
    print(f"  Warnings: {r['warnings']}")

print("\n=== FINAL MISSING MANDATORY FIELDS ===")
missing = [f for f in MANDATORY_FIELDS if f not in session or session[f] is None]
print(f"Missing: {missing}")
print(f"Collected: {session}")
