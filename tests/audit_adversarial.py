"""
Adversarial Audit: 15 edge-case profiles for critical evaluation.
"""
import sys, io, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.user import UserProfile, Gender, AreaType, Occupation, CasteCategory, MaritalStatus, LandLeasingStatus
from engine import run_kalam

CASES = [
    # 1. Landless farmer contradiction
    {"name": "Landless Farmer Owner", "p": dict(age=45, gender="MALE", state="IN-UP", area_type="RURAL", annual_income=60000, occupation="FARMER_OWNER", land_owned_hectares=0.0, land_leasing_status="OWNER", caste_category="OBC", family_size=4, aadhaar_linked=True, bank_account=True, marital_status="MARRIED")},
    # 2. Migrant worker: Delhi urban + agricultural labourer
    {"name": "Urban Agri Labourer (Migrant)", "p": dict(age=28, gender="MALE", state="IN-DL", area_type="URBAN", annual_income=48000, occupation="AGRICULTURAL_LABOURER", land_owned_hectares=None, land_leasing_status="NONE", caste_category="SC", family_size=1, aadhaar_linked=True, bank_account=True, marital_status="SINGLE")},
    # 3. Widow remarried
    {"name": "Widow Who Remarried", "p": dict(age=30, gender="FEMALE", state="IN-RJ", area_type="RURAL", annual_income=35000, occupation="UNSKILLED_LABOURER", land_owned_hectares=None, land_leasing_status="NONE", caste_category="GEN", family_size=3, aadhaar_linked=True, bank_account=True, marital_status="MARRIED")},
    # 4. Aadhaar but no bank
    {"name": "Aadhaar Yes, Bank No", "p": dict(age=40, gender="FEMALE", state="IN-MH", area_type="RURAL", annual_income=50000, occupation="AGRICULTURAL_LABOURER", land_owned_hectares=None, land_leasing_status="NONE", caste_category="SC", family_size=5, aadhaar_linked=True, bank_account=False, marital_status="MARRIED")},
    # 5. Conflicting: Tenant with OWNER land status
    {"name": "Tenant+Owner Conflict", "p": dict(age=50, gender="MALE", state="IN-PB", area_type="RURAL", annual_income=80000, occupation="FARMER_TENANT", land_owned_hectares=2.0, land_leasing_status="OWNER", caste_category="GEN", family_size=5, aadhaar_linked=True, bank_account=True, marital_status="MARRIED")},
    # 6. Extremely low income, urban
    {"name": "Ultra-Low Income Urban", "p": dict(age=22, gender="MALE", state="IN-DL", area_type="URBAN", annual_income=12000, occupation="UNEMPLOYED", land_owned_hectares=None, land_leasing_status="NONE", caste_category="SC", family_size=6, aadhaar_linked=False, bank_account=False, marital_status="SINGLE")},
    # 7. Minor (14) student
    {"name": "Minor Student (14)", "p": dict(age=14, gender="MALE", state="IN-UP", area_type="RURAL", annual_income=0, occupation="STUDENT", land_owned_hectares=None, land_leasing_status="NONE", caste_category="OBC", family_size=5, aadhaar_linked=True, bank_account=False, marital_status="SINGLE")},
    # 8. Elderly widow, no Aadhaar, no bank, tribal
    {"name": "Elderly Tribal Widow (No Docs)", "p": dict(age=68, gender="FEMALE", state="IN-JH", area_type="RURAL", annual_income=18000, occupation="UNSKILLED_LABOURER", land_owned_hectares=None, land_leasing_status="NONE", caste_category="ST", family_size=2, aadhaar_linked=False, bank_account=False, marital_status="WIDOWED")},
    # 9. High-income self-employed (possible tax exclusion)
    {"name": "High Income Self-Employed", "p": dict(age=38, gender="MALE", state="IN-GJ", area_type="RURAL", annual_income=420000, occupation="SELF_EMPLOYED", land_owned_hectares=1.5, land_leasing_status="OWNER", caste_category="GEN", family_size=4, aadhaar_linked=True, bank_account=True, marital_status="MARRIED")},
    # 10. Exact boundary: Age 50 (PMJJBY max)
    {"name": "Exact Age Boundary (50)", "p": dict(age=50, gender="MALE", state="IN-KA", area_type="RURAL", annual_income=70000, occupation="AGRICULTURAL_LABOURER", land_owned_hectares=None, land_leasing_status="NONE", caste_category="OBC", family_size=4, aadhaar_linked=True, bank_account=True, marital_status="MARRIED")},
    # 11. Exact boundary: Age 41 (APY max=40)
    {"name": "Age 41 vs APY max 40", "p": dict(age=41, gender="MALE", state="IN-KA", area_type="RURAL", annual_income=70000, occupation="AGRICULTURAL_LABOURER", land_owned_hectares=None, land_leasing_status="NONE", caste_category="OBC", family_size=4, aadhaar_linked=True, bank_account=True, marital_status="MARRIED")},
    # 12. Govt employee (exclusion test)
    {"name": "Govt Employee Exclusion", "p": dict(age=35, gender="MALE", state="IN-UP", area_type="URBAN", annual_income=600000, occupation="SALARIED_GOVT", land_owned_hectares=None, land_leasing_status="NONE", caste_category="GEN", family_size=3, aadhaar_linked=True, bank_account=True, marital_status="MARRIED")},
    # 13. Transgender person
    {"name": "Transgender User", "p": dict(age=25, gender="TRANSGENDER", state="IN-TN", area_type="URBAN", annual_income=90000, occupation="SELF_EMPLOYED", land_owned_hectares=None, land_leasing_status="NONE", caste_category="OBC", family_size=1, aadhaar_linked=True, bank_account=True, marital_status="SINGLE")},
    # 14. Income exactly at PMAY EWS limit (300000)
    {"name": "PMAY EWS Boundary (3L)", "p": dict(age=35, gender="FEMALE", state="IN-TN", area_type="URBAN", annual_income=300000, occupation="SELF_EMPLOYED", land_owned_hectares=None, land_leasing_status="NONE", caste_category="SC", family_size=3, aadhaar_linked=True, bank_account=True, marital_status="MARRIED")},
    # 15. Everything missing except minimum mandatory
    {"name": "Zero land, zero income, urban, no docs", "p": dict(age=19, gender="MALE", state="IN-BR", area_type="URBAN", annual_income=0, occupation="UNEMPLOYED", land_owned_hectares=0.0, land_leasing_status="NONE", caste_category="UNKNOWN", family_size=1, aadhaar_linked=False, bank_account=False, marital_status="SINGLE")},
]

def run_all():
    results = []
    for i, case in enumerate(CASES, 1):
        print(f"\n{'='*80}")
        print(f"CASE {i}: {case['name']}")
        print(f"{'='*80}")
        try:
            user = UserProfile(**case["p"])
            result = run_kalam(user)
            
            # Contradictions/Warnings
            if result.input_validation.contradictions:
                print(f"  CONTRADICTIONS: {result.input_validation.contradictions}")
            if result.input_validation.warnings:
                print(f"  WARNINGS: {result.input_validation.warnings}")
            
            print(f"  Summary: E={result.summary['fully_eligible']} P={result.summary['partially_eligible']} U={result.summary['uncertain']} N={result.summary['not_eligible']}")
            print(f"  Ambiguities: {result.summary['total_ambiguities']}")
            
            # Eligible
            for s in result.eligible_schemes:
                print(f"    [ELIGIBLE]  {s.scheme_id:12s} conf={s.confidence_score:.3f} ({s.confidence_level})")
            for s in result.partially_eligible_schemes:
                print(f"    [PARTIAL]   {s.scheme_id:12s} conf={s.confidence_score:.3f} ({s.confidence_level})")
                if s.gap_analysis:
                    for mc in s.gap_analysis.missing_conditions:
                        print(f"      MISSING: {mc.requirement} -> {mc.how_to_fulfill[:60]}...")
            for s in result.uncertain_schemes:
                print(f"    [UNCERTAIN] {s.scheme_id:12s} conf={s.confidence_score:.3f} ({s.confidence_level})")
            for s in result.not_eligible_schemes[:5]:
                fails = [t.rule for t in s.rule_trace if t.status == "failed"]
                print(f"    [NOT ELIG]  {s.scheme_id:12s} conf={s.confidence_score:.3f} fails={fails}")
            
            # Doc checklist
            print(f"  Doc checklist: {len(result.document_checklist)} items")
            for d in result.document_checklist[:3]:
                print(f"    [{d.priority}] {d.document} -> {d.required_for}")
            
            # Application sequence
            print(f"  App sequence: {len(result.application_sequence)} steps")
            for step in result.application_sequence[:3]:
                print(f"    Step {step.step}: {step.action[:70]}...")
            
            results.append({"name": case["name"], "status": "OK", "summary": result.summary})
        
        except Exception as e:
            print(f"  [CRASH] {type(e).__name__}: {e}")
            results.append({"name": case["name"], "status": "CRASH", "error": str(e)})
    
    # Final summary
    print(f"\n{'='*80}")
    print("AUDIT SUMMARY")
    print(f"{'='*80}")
    crashed = [r for r in results if r["status"] == "CRASH"]
    ok = [r for r in results if r["status"] == "OK"]
    print(f"  OK: {len(ok)} / {len(results)}")
    print(f"  CRASHED: {len(crashed)} / {len(results)}")
    for c in crashed:
        print(f"    CRASH: {c['name']} -> {c['error']}")

if __name__ == "__main__":
    run_all()
