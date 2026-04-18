# KALAM — Adversarial Edge Cases Documentation
*A suite of 10 edge-cases designed to stress-test the deterministic matching, boundary condition checks, and contradiction handling of the KALAM backend engine.*

Run timestamp: 2026-04-14

## Overview
All 10 adversarial cases are programmed into `tests/adversarial_tests.py` using direct `UserProfile` injection. The engine passed 10/10 tests, handling contradictions according to our documented ambiguity protocols.

---

### CASE 1: Landless Farmer Contradiction
* **Profile:** Occupation `FARMER_OWNER` but `land_owned_hectares` equals 0.
* **Goal:** Engine must detect the mismatch between the declared occupation and land ownership and correctly reject PM-KISAN.
* **Result:** **[PASS]** The engine flags a contradiction, marking PM-KISAN as `NOT_ELIGIBLE` due to landless rules, without crashing on the `FARMER_OWNER` enum selection.

### CASE 2: The Unbanked User
* **Profile:** Aadhaar is Linked, but `bank_account` is False.
* **Goal:** Direct Benefit Transfer (DBT) schemes should not fail outright. They must be moved to `PARTIALLY_ELIGIBLE`, treating the bank account as a resolvable prerequisite gap.
* **Result:** **[PASS]** Shows PMJDY (Jan Dhan Yojana) as the priority missing step. MGNREGA and other DBT schemes moved to partially eligible with explicit "bank account required" gap analysis.

### CASE 3: Widow Who Remarried
* **Profile:** `gender: FEMALE`, `marital_status: MARRIED` but testing against widow-pension rules.
* **Goal:** Schemes designed exclusively for widows (e.g., IGNDPS, State Widow Pensions) must correctly disqualify the user because of her current legal marital status.
* **Result:** **[PASS]** The engine strictly adhered to the current `MARRIED` enum state, disqualifying from widow pensions while evaluating normally for PMMVY (Maternity).

### CASE 4: The Tenant Farmer
* **Profile:** `occupation: FARMER_TENANT` with `land_leasing_status: TENANT`.
* **Goal:** Differentiate schemes that strictly mandate land title (PM-KISAN) versus schemes targeting agricultural risk broadly (PMFBY).
* **Result:** **[PASS]** PM-KISAN correctly failed with reason "Tenant excluded." PMFBY Crop Insurance correctly advanced the user as eligible/uncertain based on other criteria.

### CASE 5: Urban Migrant Labourer
* **Profile:** `area_type: URBAN` but `occupation: AGRICULTURAL_LABOURER`.
* **Goal:** Raise a warning for an unusual rural-urban combination without hard-failing, while strictly failing MGNREGA because MGNREGA explicitly requires a Rural residence.
* **Result:** **[PASS]** Raised input validation warning. MGNREGA was immediately marked `NOT_ELIGIBLE`.

### CASE 6: Complete Bootstrap (No Aadhaar, No Bank)
* **Profile:** User lacks both Aadhaar and Bank Account (Age 60, Rural).
* **Goal:** The application sequencing module must build the correct path: Aadhaar Enrollment → PMJDY Bank Account → Scheme Applications.
* **Result:** **[PASS]** The Engine successfully recognized the zero-state and outputted the core bootstrap path as prerequisites for all DBT schemes, applying age filters correctly (PMJJBY fails as age 60 > 50).

### CASE 7: High-Income Boundary
* **Profile:** Self-employed user reporting ₹3,20,000 annual income.
* **Goal:** Most schemes exclude income-tax payers. The engine must recognize this high self-reported income as a potential exclusion risk and degrade confidence without an instant fail.
* **Result:** **[PASS]** Engine moved PM-KISAN and other targeted schemes to `UNCERTAIN` citing the ambiguous professional tax and income tax exclusion clauses that cannot be verified via self-report.

### CASE 8: The Underage Applicant
* **Profile:** `Age: 14`, `Occupation: STUDENT`.
* **Goal:** Test absolute lower-age bounds across 5+ schemes.
* **Result:** **[PASS]** PMJJBY, PMSBY, APY, MGNREGA successfully flagged as `NOT_ELIGIBLE` due to the 18+ age requirement. PMJDY (min age 10) correctly passed. PMKVY (Skill India, min age 15) successfully failed by a 1-year margin.

### CASE 9: The Exact Threshold Tester
* **Profile:** `annual_income: 300000` (Urban EWS limit is exactly 3L).
* **Goal:** Verify boundary logic. `income <= 300000` must include exactly ₹3L.
* **Result:** **[PASS]** The exact 3L boundary did not disqualify the user from PMAY-Urban. Engine maintained eligibility.

### CASE 10: Age Threshold Off-by-one
* **Profile:** `Age: 41` against Atal Pension Yojana (max age 40).
* **Goal:** Ensure upper age boundaries instantly fail edge cases. 
* **Result:** **[PASS]** APY failed definitively, whereas PMJJBY (max 50) successfully evaluated the remaining logic.

---
**Conclusion:** The KALAM engine correctly interprets structured boundary conditions and resolves/flags ambiguous edge cases deterministically.
