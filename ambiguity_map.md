# KALAM — Scheme Ambiguity Map
*A systematic documentation of contradictions, proxy overlaps, and logic gaps across the 18 Central Government Welfare Schemes integrated into the KALAM engine.*

## 1. Structural Contradictions

### 1.1 The "Unemployed" vs "MGNREGA" Conflict
*   **The Conflict:** MGNREGA requires individuals to hold a Job Card and perform unskilled manual labor. However, if a user strictly characterizes themselves as "UNEMPLOYED" (no ongoing job), they are technically not an active laborer. Yet, MGNREGA is specifically designed for the unemployed seeking work.
*   **Engine Resolution:** We treat `UNEMPLOYED` as an eligible occupation for MGNREGA alongside `UNSKILLED_LABOURER`. If they lack a Job Card, we mark them as `PARTIALLY_ELIGIBLE`.

### 1.2 PM-KISAN Tenant Farmer Contradiction
*   **The Conflict:** PM-KISAN guidelines stipulate the benefit is for "landholding farmer families." Tenant farmers (`FARMER_TENANT`) who lease land but do not hold the title/Khasra are excluded centrally. However, certain states (like AP) have attempted to integrate tenants into similar state-level variants, causing immense confusion at the implementation level.
*   **Engine Resolution:** Explicitly strict-fails `FARMER_TENANT` for PM-KISAN with a rule trace noting the exact reason, while leaving them eligible for PMFBY (Crop Insurance).

## 2. Proxy Ambiguities & Data Gaps

### 2.1 The SECC 2011 Database Proxy
*   **Schemes Affected:** Ayushman Bharat (PM-JAY), PMAY-G
*   **The Conflict:** Eligibility for these schemes is strictly determined by presence in the Socio-Economic Caste Census (SECC 2011) database. The KALAM engine cannot query this database directly based on user chat input. 
*   **Engine Resolution:** KALAM employs *Proxy Indicators* (e.g., Rural + SC/ST + Income < 1L + Agricultural Labourer). Whenever proxy matching triggers, the engine forces the `Confidence Score` down to **Medium (50%)** and attaches an `AMBIGUOUS` flag, instructing the user to verify at a Common Service Centre (CSC) since the ultimate source of truth is external. 

### 2.2 Income Tax Exclusion Clause
*   **Schemes Affected:** PM-KISAN, PM-SYM, APY
*   **The Conflict:** These schemes explicitly exclude "income tax payers." A user reporting an annual income of ₹2,00,000 might still pay tax (from prior years or other unrecorded assets). Conversely, a user reporting ₹4,00,000 might claim agricultural exemption and pay no tax. 
*   **Engine Resolution:** KALAM maps reported `annual_income` > ₹2,50,000 as a `HIGH RISK` for exclusion but does not definitively fail the user unless they explicitly state tax compliance. It outputs a warning and drops confidence to `Uncertain/Medium`.

## 3. Boundary Definitions & Overlaps

### 3.1 Unorganized Worker Definition Overlap
*   **Schemes Affected:** E-Shram, PM-SYM (Shram Yogi Maan-dhan)
*   **The Conflict:** "Unorganized worker" is loosely defined. It includes self-employed, wage workers, and home-based workers. A retail shop owner (Self-Employed) making ₹15,000/month might technically qualify, but local authorities frequently reject them in favor of manual laborers.
*   **Engine Resolution:** The engine groups `UNSKILLED_LABOURER`, `AGRICULTURAL_LABOURER`, and `SELF_EMPLOYED` (with income < ₹1.8L) as eligible, but warns self-employed users that classification is determined locally by the issuing authority.

### 3.2 Age Boundary Exclusivity
*   **Schemes Affected:** PMJJBY (18-50) vs APY (18-40)
*   **The Conflict:** A user who is exactly 50 or exactly 40 testing the boundary. In many schemes, the maximum age defines the *entry* cutoff, but benefits continue after.
*   **Engine Resolution:** KALAM treats max age bounds as **Inclusive** (e.g., `< 51` mathematically) for entry evaluation, meaning a user declaring age 50 passes PMJJBY.

## 4. Rule Evaluation Protocol
Whenever the engine encounters the ambiguities defined above, it:
1. Rejects the binary Pass/Fail approach.
2. Returns a `CONDITIONAL` or `UNCERTAIN` classification.
3. Automatically applies a `Confidence Penalty`.
4. Outputs the `AMBIGUITY_NOTES` to the Explainability module so the user knows *why* the machine is unsure.
