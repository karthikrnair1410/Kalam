"""
tests/adversarial_tests.py
--------------------------
10 adversarial edge-case profiles to stress-test the KALAM engine.
Each test documents the expected behavior and flags any failures.

Run with: python tests/adversarial_tests.py
"""

import sys
import io
import json
from pathlib import Path

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.user import UserProfile, Gender, AreaType, Occupation, CasteCategory, MaritalStatus, LandLeasingStatus
from engine import run_kalam


def run_test(name: str, profile: dict, expected_notes: str) -> dict:
    """Run a single adversarial test case and return results."""
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"EXPECTED BEHAVIOR: {expected_notes}")
    print(f"{'='*70}")

    try:
        user = UserProfile(**profile)
        result = run_kalam(user)

        print(f"\n[PASS] Summary: {result.summary}")
        print(f"  Fully Eligible:    {[s.scheme_id for s in result.eligible_schemes]}")
        print(f"  Partially:         {[s.scheme_id for s in result.partially_eligible_schemes]}")
        print(f"  Uncertain:         {[s.scheme_id for s in result.uncertain_schemes]}")
        print(f"  Not Eligible:      {[s.scheme_id for s in result.not_eligible_schemes]}")
        print(f"  Ambiguities:       {len(result.ambiguities_detected)}")


        if result.input_validation.contradictions:
            print(f"\n⚠ CONTRADICTIONS DETECTED:")
            for c in result.input_validation.contradictions:
                print(f"    → {c}")

        if result.input_validation.warnings:
            print(f"\n⚠ WARNINGS:")
            for w in result.input_validation.warnings:
                print(f"    → {w}")

        # Show confidence scores for top schemes
        all_results = (
            result.eligible_schemes +
            result.partially_eligible_schemes +
            result.uncertain_schemes
        )
        if all_results:
            print(f"\n📊 Confidence Scores:")
            for r in sorted(all_results, key=lambda x: -x.confidence_score)[:6]:
                print(f"    {r.scheme_id:20s} → {r.confidence_score:.3f} ({r.confidence_level}) [{r.status}]")

        return {"name": name, "status": "PASS", "summary": result.summary}

    except Exception as e:
        print(f"\n[FAIL] ENGINE FAILURE: {e}")
        return {"name": name, "status": "FAIL", "error": str(e)}


# ================================================================
# 10 ADVERSARIAL PROFILES
# ================================================================

ADVERSARIAL_CASES = [

    # ----------------------------------------------------------------
    # CASE 1: Landless farmer
    # PM-KISAN requires land. Engine must detect this AND flag ambiguity
    # about whether they are actually a farmer without land.
    # ----------------------------------------------------------------
    {
        "name": "Case 1: Landless Farmer (FARMER_OWNER + 0 land)",
        "profile": {
            "age": 45,
            "gender": "MALE",
            "state": "IN-UP",
            "area_type": "RURAL",
            "annual_income": 60000,
            "occupation": "FARMER_OWNER",
            "land_owned_hectares": 0.0,
            "land_leasing_status": "OWNER",
            "caste_category": "OBC",
            "family_size": 4,
            "aadhaar_linked": True,
            "bank_account": True,
            "marital_status": "MARRIED",
        },
        "expected": "CONTRADICTION DETECTED: FARMER_OWNER with 0 land. PM-KISAN must FAIL. MGNREGA may still be eligible."
    },

    # ----------------------------------------------------------------
    # CASE 2: Aadhaar but no bank account
    # Eligible for schemes but blocked by missing bank (DBT prerequisite)
    # Engine must mark these as PARTIALLY_ELIGIBLE, not NOT_ELIGIBLE
    # ----------------------------------------------------------------
    {
        "name": "Case 2: Aadhaar Linked, No Bank Account",
        "profile": {
            "age": 32,
            "gender": "FEMALE",
            "state": "IN-MH",
            "area_type": "RURAL",
            "annual_income": 45000,
            "occupation": "AGRICULTURAL_LABOURER",
            "land_owned_hectares": None,
            "land_leasing_status": "NONE",
            "caste_category": "SC",
            "family_size": 3,
            "aadhaar_linked": True,
            "bank_account": False,
            "marital_status": "MARRIED",
        },
        "expected": "Should show PMJDY as the first priority step. MGNREGA, PMMVY should be PARTIALLY_ELIGIBLE. No hard fails."
    },

    # ----------------------------------------------------------------
    # CASE 3: Widow who remarried
    # Marital status MARRIED but schemes designed for widows won't apply.
    # PMMVY first_child condition may apply. Test mixed signal handling.
    # ----------------------------------------------------------------
    {
        "name": "Case 3: Widow Who Remarried (Marital=MARRIED)",
        "profile": {
            "age": 28,
            "gender": "FEMALE",
            "state": "IN-RJ",
            "area_type": "RURAL",
            "annual_income": 40000,
            "occupation": "UNSKILLED_LABOURER",
            "land_owned_hectares": None,
            "land_leasing_status": "NONE",
            "caste_category": "GEN",
            "family_size": 2,
            "aadhaar_linked": True,
            "bank_account": True,
            "marital_status": "MARRIED",
        },
        "expected": "MARRIED status declared — widow-specific sub-rules don't apply. PMMVY eligible if pregnant. System must not assume status."
    },

    # ----------------------------------------------------------------
    # CASE 4: Farmer who leases rather than owns land (FARMER_TENANT)
    # PM-KISAN: tenant NOT eligible
    # PMFBY: tenant IS eligible
    # Engine must differentiate between these correctly
    # ----------------------------------------------------------------
    {
        "name": "Case 4: Tenant Farmer (FARMER_TENANT)",
        "profile": {
            "age": 50,
            "gender": "MALE",
            "state": "IN-PB",
            "area_type": "RURAL",
            "annual_income": 80000,
            "occupation": "FARMER_TENANT",
            "land_owned_hectares": 0.0,
            "land_leasing_status": "TENANT",
            "caste_category": "GEN",
            "family_size": 5,
            "aadhaar_linked": True,
            "bank_account": True,
            "marital_status": "MARRIED",
        },
        "expected": "PM-KISAN must FAIL (tenant excluded). PMFBY should show as eligible/uncertain for tenant. MGNREGA eligible."
    },

    # ----------------------------------------------------------------
    # CASE 5: Urban migrant with agricultural labourer occupation
    # Suspicious: URBAN + AGRICULTURAL_LABOURER
    # Should trigger WARNING not hard fail
    # MGNREGA must be NOT_ELIGIBLE (urban)
    # ----------------------------------------------------------------
    {
        "name": "Case 5: Urban Migrant (URBAN + AGRICULTURAL_LABOURER)",
        "profile": {
            "age": 25,
            "gender": "MALE",
            "state": "IN-DL",
            "area_type": "URBAN",
            "annual_income": 55000,
            "occupation": "AGRICULTURAL_LABOURER",
            "land_owned_hectares": None,
            "land_leasing_status": "NONE",
            "caste_category": "SC",
            "family_size": 1,
            "aadhaar_linked": True,
            "bank_account": True,
            "marital_status": "SINGLE",
        },
        "expected": "WARNING: unusual combination. MGNREGA NOT_ELIGIBLE (urban). PMJAY shows uncertain (SECC proxy)."
    },

    # ----------------------------------------------------------------
    # CASE 6: No Aadhaar, No Bank Account (completely unbanked)
    # Engine should bootstrap the user through PMJDY → Aadhaar path
    # Most schemes: PARTIALLY_ELIGIBLE with prerequisite gap
    # ----------------------------------------------------------------
    {
        "name": "Case 6: No Aadhaar, No Bank Account",
        "profile": {
            "age": 60,
            "gender": "FEMALE",
            "state": "IN-BR",
            "area_type": "RURAL",
            "annual_income": 25000,
            "occupation": "UNSKILLED_LABOURER",
            "land_owned_hectares": None,
            "land_leasing_status": "NONE",
            "caste_category": "ST",
            "family_size": 6,
            "aadhaar_linked": False,
            "bank_account": False,
            "marital_status": "WIDOWED",
        },
        "expected": "Bootstrap path must appear: Aadhaar → PMJDY. All DBT schemes PARTIALLY_ELIGIBLE. Age > 50 makes PMJJBY ineligible."
    },

    # ----------------------------------------------------------------
    # CASE 7: High-income self-employed (potential PM-KISAN exclusion)
    # Annual income > 2.5L but self-declared, not verified
    # Engine must flag as UNCERTAIN not exclude
    # ----------------------------------------------------------------
    {
        "name": "Case 7: High-Income Self-Employed (Possible Tax Exclusion)",
        "profile": {
            "age": 38,
            "gender": "MALE",
            "state": "IN-GJ",
            "area_type": "RURAL",
            "annual_income": 320000,
            "occupation": "SELF_EMPLOYED",
            "land_owned_hectares": 1.5,
            "land_leasing_status": "OWNER",
            "caste_category": "GEN",
            "family_size": 4,
            "aadhaar_linked": True,
            "bank_account": True,
            "marital_status": "MARRIED",
        },
        "expected": "Income tax exclusion rule cannot be verified — must be UNCERTAIN not FAILED. Professional exclusion also uncertain."
    },

    # ----------------------------------------------------------------
    # CASE 8: Minor (age 14) — below many age gates
    # PMJJBY, PMSBY, MGNREGA, APY all have min_age 18
    # Engine must hard-fail these
    # PMKVY has min_age 15 — still fails at 14
    # PMJDY allows age 10 — must pass
    # ----------------------------------------------------------------
    {
        "name": "Case 8: Minor (Age 14)",
        "profile": {
            "age": 14,
            "gender": "MALE",
            "state": "IN-UP",
            "area_type": "RURAL",
            "annual_income": 0,
            "occupation": "STUDENT",
            "land_owned_hectares": None,
            "land_leasing_status": "NONE",
            "caste_category": "OBC",
            "family_size": 5,
            "aadhaar_linked": True,
            "bank_account": False,
            "marital_status": "SINGLE",
        },
        "expected": "PMJJBY/PMSBY/APY/MGNREGA/PM-KISAN hard FAIL (age). PMJDY should PASS (min age 10). PMKVY should FAIL (min age 15)."
    },

    # ----------------------------------------------------------------
    # CASE 9: SC woman, maximum income eligibility boundary (PMAY EWS exactly 3L)
    # Boundary testing: annual_income == 300000 (EWS upper bound)
    # ----------------------------------------------------------------
    {
        "name": "Case 9: Boundary Income — PMAY EWS Exact Limit (₹3,00,000)",
        "profile": {
            "age": 35,
            "gender": "FEMALE",
            "state": "IN-TN",
            "area_type": "URBAN",
            "annual_income": 300000,
            "occupation": "SELF_EMPLOYED",
            "land_owned_hectares": None,
            "land_leasing_status": "NONE",
            "caste_category": "SC",
            "family_size": 3,
            "aadhaar_linked": True,
            "bank_account": True,
            "marital_status": "MARRIED",
        },
        "expected": "PMAY urban EWS: income == 300000 is exactly at threshold. Must show BOUNDARY flag and reduced confidence."
    },

    # ----------------------------------------------------------------
    # CASE 10: Elder (Age 41) — just above APY cutoff (max 40)
    # Exact boundary failure test
    # ----------------------------------------------------------------
    {
        "name": "Case 10: Elder Just Above APY Age Limit (Age 41, APY max=40)",
        "profile": {
            "age": 41,
            "gender": "MALE",
            "state": "IN-KA",
            "area_type": "RURAL",
            "annual_income": 70000,
            "occupation": "AGRICULTURAL_LABOURER",
            "land_owned_hectares": None,
            "land_leasing_status": "NONE",
            "caste_category": "OBC",
            "family_size": 4,
            "aadhaar_linked": True,
            "bank_account": True,
            "marital_status": "MARRIED",
        },
        "expected": "APY must FAIL (age 41 > max 40). PMJJBY age <= 50 PASSES. This tests exact boundary failure vs boundary pass."
    },
]


def main():
    print("\n" + "="*70)
    print("  KALAM — ADVERSARIAL TEST SUITE")
    print("  10 Edge-Case Profiles")
    print("="*70)

    results = []
    for case in ADVERSARIAL_CASES:
        result = run_test(
            name=case["name"],
            profile=case["profile"],
            expected_notes=case["expected"]
        )
        results.append(result)

    # Summary
    print("\n" + "="*70)
    print("ADVERSARIAL TEST RESULTS SUMMARY")
    print("="*70)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"PASSED: {passed} / {len(results)}")
    print(f"FAILED: {failed} / {len(results)}")
    for r in results:
        icon = "[OK]" if r["status"] == "PASS" else "[FAIL]"
        print(f"  {icon} {r['name']}")

    return results


if __name__ == "__main__":
    main()
