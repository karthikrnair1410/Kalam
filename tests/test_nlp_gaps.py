"""
Test script to find REAL parsing gaps — things that should match but DON'T.
"""
import sys
sys.path.insert(0, r"C:\Users\karth\OneDrive\Desktop\Task\kalam")

from engine.intent_mapper import map_to_fields

# Only test cases where we EXPECT a result but currently get None
tests = [
    # --- AGE: common misspellings ---
    ("umr 30 hai", "age", 30),          # 'umr' = common shortening of 'umar'
    ("meri umer 40", "age", 40),        # 'umer' = common alternate
    ("mei 28 sal ka", "age", 28),       # 'sal' = common shortening of 'saal'
    ("age- 22", "age", 22),             # hyphen after 'age'
    ("mera aayu 35 hai", "age", 35),    # 'aayu' = Hindi for age
    ("meri umra 45 saal", "age", 45),   # 'umra' variant

    # --- GENDER: missing keywords ---
    ("purush", "gender", "MALE"),       # Hindi for male
    ("purush hu", "gender", "MALE"),
    ("lady hu", "gender", "FEMALE"),    # common English
    ("boy", "gender", "MALE"),          
    ("girl", "gender", "FEMALE"),        
    ("ladke", "gender", "MALE"),        # plural of ladka

    # --- AREA: missing variants ---
    ("gaav mein rehta hu", "area_type", "RURAL"),   # 'gaav' = common for gaon
    ("dehaat mein", "area_type", "RURAL"),           # 'dehaat' = rural in Hindi
    ("shahar mein", "area_type", "URBAN"),           # 'shahar' = common for sheher 
    ("shehr mein", "area_type", "URBAN"),            # 'shehr' variant
    ("gramin", "area_type", "RURAL"),                # 'gramin' = rural in Hindi

    # --- OCCUPATION: missing variants ---
    ("mai berojgar hu", "occupation", "UNEMPLOYED"),       # 'berojgar' common spelling
    ("nokri nahi hai", "occupation", "UNEMPLOYED"),        # 'nokri' = common for naukri
    ("kuch nahi karta", "occupation", "UNEMPLOYED"),       # 'kuch nahi karta' = I do nothing
    ("ghar pe baitha hu", "occupation", "UNEMPLOYED"),     # 'sitting at home' = unemployed

    # --- AADHAAR: misspellings + bare yes/no ---
    ("ha aadhaar he", "aadhaar_linked", True),      # 'ha'='haan', 'he'='hai'
    ("aadhar card hai", "aadhaar_linked", True),    # 'aadhar' common misspelling
    ("aadhar hai mera", "aadhaar_linked", True),
    ("adhar card hai", "aadhaar_linked", True),     # even shorter misspelling
    ("aadhaar he mere pas", "aadhaar_linked", True), # 'he' not 'hai'

    # --- BARE YES/NO CONTEXT (expected_field based) ---
    # When the engine asks "Kya aadhaar hai?" user says "haan" / "nahi" / "yes" / "ha"
    # These are tested with expected_field context
    ("haan", "aadhaar_linked_ctx", True),     # context: aadhaar_linked
    ("ha", "aadhaar_linked_ctx", True),       
    ("yes", "aadhaar_linked_ctx", True),
    ("nahi", "aadhaar_linked_ctx", False),
    ("nhi", "aadhaar_linked_ctx", False),
    ("no", "aadhaar_linked_ctx", False),
    ("haan", "bank_account_ctx", True),       # context: bank_account
    ("nahi", "bank_account_ctx", False),
    ("ha", "bank_account_ctx", True),
    ("yes", "bank_account_ctx", True),
    ("no", "bank_account_ctx", False),
    ("nhi", "bank_account_ctx", False),

    # --- BANK: misspellings ---
    ("bank account he mere", "bank_account", True),  # 'he' not 'hai'
    ("haan bank hai", "bank_account", True),

    # --- CASTE: transliterated variants ---
    ("anusuchit jaati", "caste_category", "SC"),     # 'anusuchit jaati' = scheduled caste

    # --- MARITAL: spelling variants ---
    ("shadi ho gayi hai", "marital_status", "MARRIED"),   # 'shadi' = common for 'shaadi'
    ("meri shadi ho chuki", "marital_status", "MARRIED"),
    ("unmarried", "marital_status", "SINGLE"),            # common English
    ("unmarried hu", "marital_status", "SINGLE"),

    # --- INCOME: 'lak' variant ---
    ("income 2 lak hai", "annual_income", 200000),    # 'lak' = lakh misspelling

    # --- LAND: misspellings ---
    ("jamin nahi hai", "land_leasing_status", "NONE"),  # 'jamin' = zameen misspelling
    ("zamin nahi hai", "land_leasing_status", "NONE"),  # 'zamin' variant
    ("meri koi zameen nhi", "land_leasing_status", "NONE"),  # 'nhi'
]

passed = 0
failed = 0
failures = []
for text, field_raw, expected in tests:
    # Handle context-based fields
    if field_raw.endswith("_ctx"):
        real_field = field_raw.replace("_ctx", "")
        result = map_to_fields(text, expected_field=real_field)
        actual = result["fields"].get(real_field)
    else:
        result = map_to_fields(text)
        actual = result["fields"].get(field_raw)

    if actual == expected:
        passed += 1
    else:
        failed += 1
        failures.append((text, field_raw, expected, actual))
        print(f"FAIL: \"{text}\" -> {field_raw}={actual} (expected {expected})")

print(f"\n{passed} passed, {failed} failed out of {len(tests)}")
if failures:
    print(f"\nCategories of failures:")
    cats = {}
    for t, f, e, a in failures:
        cat = f.split("_")[0] if "_" not in f else f.rsplit("_", 1)[0]
        cats.setdefault(cat, []).append(t)
    for cat, items in sorted(cats.items()):
        print(f"  {cat}: {len(items)} failures")
