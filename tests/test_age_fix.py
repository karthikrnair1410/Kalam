from engine.intent_mapper import map_to_fields

cases = [
    ("main kisan hu, UP mein rehta hu, 42 saal", 42),
    ("umar 35 saal hai", 35),
    ("I am 28 years old", 28),
    ("meri umar 50 hai", 50),
    ("60 saal ka hu shaadishuda", 60),
    ("main 31 saal", 31),
    ("mere paas aadhaar nahi hai, 55 saal", 55),
]
all_pass = True
for text, expected in cases:
    r = map_to_fields(text)
    got = r["fields"].get("age")
    ok = got == expected
    print(f'  [{"PASS" if ok else "FAIL"}] "{text[:48]}" -> age={got} (expected {expected})')
    if not ok:
        all_pass = False

print()
print("[ALL PASS]" if all_pass else "[SOME FAILED]")
