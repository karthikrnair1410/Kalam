"""
engine/eligibility.py
---------------------
Core rule evaluation engine for KALAM.

DESIGN PRINCIPLES:
1. Missing data ≠ False. Missing data → UNCERTAIN / UNRESOLVABLE.
2. Every rule evaluation must produce a RuleTrace record.
3. Rejection is only possible when a rule EXPLICITLY FAILS with known values.
4. Ambiguity NEVER silently resolves to eligible or ineligible.
"""

from typing import List, Tuple, Dict, Any, Optional
from models.user import UserProfile, Occupation, AreaType, Gender, CasteCategory
from models.scheme import SchemeRule
from models.result import (
    RuleTrace, EligibilityStatus, AmbiguityFlag, SchemeResult,
    ConfidenceLevel, GapAnalysis, MissingCondition, ConflictingCondition
)
from engine.ambiguity import detect_ambiguities, compute_total_penalty
from engine.scoring import compute_confidence_score, compute_confidence_level
from engine.gap_analysis import build_gap_analysis


def evaluate_scheme(user: UserProfile, scheme: SchemeRule) -> SchemeResult:
    """
    Evaluate a single scheme against a user profile.
    Returns a fully populated SchemeResult with trace and confidence.
    """
    traces: List[RuleTrace] = []
    hard_fails: List[RuleTrace] = []
    prerequisite_fails: List[RuleTrace] = []
    uncertain_traces: List[RuleTrace] = []

    rules = scheme.rules

    # ----------------------------------------------------------------
    # RULE 1: Age checks
    # ----------------------------------------------------------------
    min_age = rules.get("minimum_age")
    max_age = rules.get("maximum_age")

    if min_age is not None:
        if user.age >= min_age:
            trace = RuleTrace(
                rule="minimum_age",
                status="passed",
                value_found=user.age,
                expected=f">= {min_age}"
            )
            # Boundary value flag
            if user.age == min_age:
                trace.reason = f"BOUNDARY: age == {min_age}, exactly at threshold"
                uncertain_traces.append(trace)
            traces.append(trace)
        else:
            trace = RuleTrace(
                rule="minimum_age",
                status="failed",
                reason=f"User age {user.age} < required {min_age}",
                value_found=user.age,
                expected=f">= {min_age}"
            )
            traces.append(trace)
            hard_fails.append(trace)

    if max_age is not None:
        if user.age <= max_age:
            trace = RuleTrace(
                rule="maximum_age",
                status="passed",
                value_found=user.age,
                expected=f"<= {max_age}"
            )
            if user.age == max_age:
                trace.reason = f"BOUNDARY: age == {max_age}, exactly at threshold"
                uncertain_traces.append(trace)
            traces.append(trace)
        else:
            trace = RuleTrace(
                rule="maximum_age",
                status="failed",
                reason=f"User age {user.age} > maximum {max_age}",
                value_found=user.age,
                expected=f"<= {max_age}"
            )
            traces.append(trace)
            hard_fails.append(trace)

    # ----------------------------------------------------------------
    # RULE 2: Gender check
    # ----------------------------------------------------------------
    required_gender = rules.get("gender")
    if required_gender is not None:
        if user.gender.value == required_gender:
            traces.append(RuleTrace(
                rule="gender_requirement",
                status="passed",
                value_found=user.gender.value,
                expected=required_gender
            ))
        else:
            t = RuleTrace(
                rule="gender_requirement",
                status="failed",
                reason=f"Scheme requires {required_gender}, user is {user.gender.value}",
                value_found=user.gender.value,
                expected=required_gender
            )
            traces.append(t)
            hard_fails.append(t)

    # ----------------------------------------------------------------
    # RULE 3: Area type check
    # ----------------------------------------------------------------
    required_area = rules.get("area_type")
    if required_area is not None:
        if user.area_type.value == required_area:
            traces.append(RuleTrace(
                rule="area_type_requirement",
                status="passed",
                value_found=user.area_type.value,
                expected=required_area
            ))
        else:
            t = RuleTrace(
                rule="area_type_requirement",
                status="failed",
                reason=f"Scheme requires {required_area} area; user is in {user.area_type.value}",
                value_found=user.area_type.value,
                expected=required_area
            )
            traces.append(t)
            hard_fails.append(t)

    # ----------------------------------------------------------------
    # RULE 4: Occupation-based eligibility
    # ----------------------------------------------------------------
    occ_map = scheme.occupation_map
    user_occ = user.occupation.value

    if user_occ in occ_map.not_eligible:
        t = RuleTrace(
            rule="occupation_eligibility",
            status="failed",
            reason=f"Occupation {user_occ} is explicitly excluded from this scheme",
            value_found=user_occ,
            expected=f"Not in {occ_map.not_eligible}"
        )
        traces.append(t)
        hard_fails.append(t)

    elif user_occ in occ_map.eligible:
        traces.append(RuleTrace(
            rule="occupation_eligibility",
            status="passed",
            value_found=user_occ,
            expected=f"One of {occ_map.eligible}"
        ))

    elif user_occ in occ_map.ambiguous:
        t = RuleTrace(
            rule="occupation_eligibility",
            status="uncertain",
            reason=f"Occupation {user_occ} falls in ambiguous category for this scheme",
            value_found=user_occ,
            expected="Requires scheme-specific verification"
        )
        traces.append(t)
        uncertain_traces.append(t)

    else:
        # Occupation not mapped — treat as uncertain
        t = RuleTrace(
            rule="occupation_eligibility",
            status="uncertain",
            reason=f"Occupation {user_occ} is not explicitly mapped for this scheme",
            value_found=user_occ,
            expected="Unmapped — manual review required"
        )
        traces.append(t)
        uncertain_traces.append(t)

    # ----------------------------------------------------------------
    # RULE 5: Land ownership
    # ----------------------------------------------------------------
    if rules.get("land_ownership_required") or rules.get("cultivable_land_required"):
        if user.land_owned_hectares is None:
            # Missing data — cannot determine — UNCERTAIN not FAILED
            t = RuleTrace(
                rule="land_ownership_required",
                status="uncertain",
                reason="land_owned_hectares not provided — cannot evaluate land requirement",
                value_found=None,
                expected="> 0 hectares of cultivable land"
            )
            traces.append(t)
            uncertain_traces.append(t)
        elif user.land_owned_hectares <= 0:
            t = RuleTrace(
                rule="land_ownership_required",
                status="failed",
                reason=f"land_owned_hectares is {user.land_owned_hectares} — no land declared",
                value_found=user.land_owned_hectares,
                expected="> 0"
            )
            traces.append(t)
            hard_fails.append(t)
        else:
            traces.append(RuleTrace(
                rule="land_ownership_required",
                status="passed",
                value_found=user.land_owned_hectares,
                expected="> 0"
            ))

    # ----------------------------------------------------------------
    # RULE 6: Tenant farmer restriction (PM-KISAN specific)
    # ----------------------------------------------------------------
    if rules.get("tenant_farmers_eligible") is False:
        if user.occupation == Occupation.FARMER_TENANT:
            t = RuleTrace(
                rule="tenant_farmer_excluded",
                status="failed",
                reason="Scheme explicitly excludes tenant farmers; only land-owning farmers qualify",
                value_found="FARMER_TENANT",
                expected="FARMER_OWNER"
            )
            traces.append(t)
            hard_fails.append(t)
        elif user.land_leasing_status.value == "TENANT":
            t = RuleTrace(
                rule="tenant_farmer_excluded",
                status="failed",
                reason="User leases land (TENANT status) — excluded from this scheme",
                value_found=user.land_leasing_status.value,
                expected="OWNER"
            )
            traces.append(t)
            hard_fails.append(t)

    # ----------------------------------------------------------------
    # RULE 7: Aadhaar (PREREQUISITE — not a hard fail on eligibility)
    # ----------------------------------------------------------------
    if rules.get("aadhaar_required"):
        if not user.aadhaar_linked:
            t = RuleTrace(
                rule="aadhaar_required",
                status="failed",
                reason="Aadhaar not linked — required as prerequisite for this scheme",
                value_found=False,
                expected=True
            )
            traces.append(t)
            prerequisite_fails.append(t)  # Goes to conditional, not hard fail
        else:
            traces.append(RuleTrace(
                rule="aadhaar_required",
                status="passed",
                value_found=True,
                expected=True
            ))

    # ----------------------------------------------------------------
    # RULE 8: Bank account (PREREQUISITE)
    # ----------------------------------------------------------------
    if rules.get("bank_account_required"):
        if not user.bank_account:
            t = RuleTrace(
                rule="bank_account_required",
                status="failed",
                reason="Bank account not held — required as prerequisite (DBT channel)",
                value_found=False,
                expected=True
            )
            traces.append(t)
            prerequisite_fails.append(t)
        else:
            traces.append(RuleTrace(
                rule="bank_account_required",
                status="passed",
                value_found=True,
                expected=True
            ))

    # ----------------------------------------------------------------
    # RULE 9: Income-based checks (PMAY urban categories)
    # ----------------------------------------------------------------
    urban_rules = scheme.urban_rules
    if urban_rules and user.area_type == AreaType.URBAN:
        income_cats = urban_rules.get("income_categories", {})
        income_matched = False
        for cat, bounds in income_cats.items():
            min_inc = bounds.get("min_income", 0)
            max_inc = bounds.get("max_income", float("inf"))
            if min_inc <= user.annual_income <= max_inc:
                traces.append(RuleTrace(
                    rule=f"urban_income_category_{cat}",
                    status="passed",
                    value_found=user.annual_income,
                    expected=f"{min_inc} – {max_inc}"
                ))
                income_matched = True
                break
        if not income_matched:
            t = RuleTrace(
                rule="urban_income_category",
                status="failed",
                reason=f"Income {user.annual_income} does not fit any PMAY urban income bracket",
                value_found=user.annual_income,
                expected="Within EWS/LIG/MIG-I/MIG-II brackets"
            )
            traces.append(t)
            hard_fails.append(t)

    # ----------------------------------------------------------------
    # RULE 10: Exclusion — income tax payers (PM-KISAN)
    # ----------------------------------------------------------------
    exclusions = scheme.exclusions or {}
    if exclusions.get("income_tax_payers"):
        # Income tax threshold: > 2.5L typically, but not always verifiable
        if user.annual_income > 250000:
            t = RuleTrace(
                rule="exclusion_income_tax_payer",
                status="uncertain",
                reason=(
                    f"Income {user.annual_income} > 2,50,000 may classify as income-tax payer. "
                    "Self-declared income cannot be verified — flagged as uncertain."
                ),
                value_found=user.annual_income,
                expected="<= 250000 (approximate IT exemption threshold)"
            )
            traces.append(t)
            uncertain_traces.append(t)
        else:
            traces.append(RuleTrace(
                rule="exclusion_income_tax_payer",
                status="passed",
                value_found=user.annual_income,
                expected="<= 250000"
            ))

    # ----------------------------------------------------------------
    # RULE 11: Government employee exclusion
    # ----------------------------------------------------------------
    if exclusions.get("government_employees_excluded"):
        if user.occupation == Occupation.SALARIED_GOVT:
            exceptions = exclusions.get("government_employee_exceptions", [])
            t = RuleTrace(
                rule="exclusion_government_employee",
                status="uncertain",
                reason=(
                    f"SALARIED_GOVT occupation declared. Scheme excludes govt employees "
                    f"EXCEPT: {exceptions}. Input schema cannot determine employee grade."
                ),
                value_found="SALARIED_GOVT",
                expected=f"Not a govt employee (exceptions: {exceptions})"
            )
            traces.append(t)
            uncertain_traces.append(t)

    # ----------------------------------------------------------------
    # RULE 12: Excluded professionals (PM-KISAN)
    # ----------------------------------------------------------------
    excluded_profs = exclusions.get("excluded_professionals", [])
    if excluded_profs and user.occupation == Occupation.SELF_EMPLOYED:
        t = RuleTrace(
            rule="exclusion_professional",
            status="uncertain",
            reason=(
                f"SELF_EMPLOYED occupation — scheme excludes professionals "
                f"({excluded_profs}). Cannot determine profession type from input."
            ),
            value_found="SELF_EMPLOYED",
            expected=f"Not a doctor/engineer/lawyer/CA"
        )
        traces.append(t)
        uncertain_traces.append(t)

    # ----------------------------------------------------------------
    # RULE 13: Universal access schemes (PMBJP, BBBP, PMJDY)
    # ----------------------------------------------------------------
    if rules.get("universal_access") or rules.get("income_criteria") == "none":
        traces.append(RuleTrace(
            rule="universal_access",
            status="passed",
            reason="This scheme has universal access — no income/caste/occupation restrictions",
            value_found="universal",
            expected="universal"
        ))

    # ----------------------------------------------------------------
    # RULE 14: Minimum age for PMJDY (10 years)
    # ----------------------------------------------------------------
    # Already handled by generic min_age rule above

    # ----------------------------------------------------------------
    # RULE 15: Maternity / gender-specific additional check (PMMVY)
    # ----------------------------------------------------------------
    if rules.get("pregnant_or_lactating"):
        if user.gender != Gender.FEMALE:
            t = RuleTrace(
                rule="pregnant_or_lactating_requirement",
                status="failed",
                reason="Scheme is for pregnant/lactating women only",
                value_found=user.gender.value,
                expected="FEMALE"
            )
            traces.append(t)
            hard_fails.append(t)
        else:
            traces.append(RuleTrace(
                rule="pregnant_or_lactating_requirement",
                status="uncertain",
                reason="User is FEMALE — pregnancy/lactation status not in input schema; assumed possible",
                value_found="FEMALE",
                expected="Pregnant or lactating"
            ))

    # ----------------------------------------------------------------
    # RULE 16: Girl child required (SSY)
    # ----------------------------------------------------------------
    if rules.get("girl_child_required"):
        # We cannot verify from input if user has a girl child under 10.
        # Always flag as UNCERTAIN — never claim eligible outright.
        t = RuleTrace(
            rule="girl_child_required",
            status="uncertain",
            reason=(
                "This scheme requires a girl child below 10 years of age. "
                "Input schema does not capture dependent children — eligibility cannot be confirmed."
            ),
            value_found="unknown",
            expected="Has girl child under 10"
        )
        traces.append(t)
        uncertain_traces.append(t)

    # ----------------------------------------------------------------
    # RULE 17: Awareness campaign only (BBBP)
    # ----------------------------------------------------------------
    if rules.get("awareness_campaign_only"):
        t = RuleTrace(
            rule="awareness_campaign_flag",
            status="uncertain",
            reason=(
                "This is a government awareness campaign (Beti Bachao Beti Padhao), "
                "NOT a direct benefit transfer scheme. No cash/subsidy is disbursed to individuals. "
                "Benefits are indirect — awareness drives, school programs, and community actions."
            ),
            value_found="awareness_campaign",
            expected="Not a DBT scheme"
        )
        traces.append(t)
        uncertain_traces.append(t)

    # ----------------------------------------------------------------
    # RULE 18: MGNREGA high-income warning
    # ----------------------------------------------------------------
    if scheme.scheme_id == "MGNREGA" and user.annual_income > 200000:
        t = RuleTrace(
            rule="income_practical_warning",
            status="uncertain",
            reason=(
                f"Income Rs.{user.annual_income:,} is significantly above the poverty line. "
                "MGNREGA has no statutory income cap, but practically targets the poorest rural households. "
                "High-income applicants may face scrutiny at Gram Sabha level."
            ),
            value_found=user.annual_income,
            expected="Practically for BPL/low-income households"
        )
        traces.append(t)
        uncertain_traces.append(t)

    # ----------------------------------------------------------------
    # RULE 19: PMAY income boundary detection
    # ----------------------------------------------------------------
    if scheme.scheme_id == "PMAY" and user.area_type == AreaType.URBAN:
        boundary_values = [300000, 600000, 1200000, 1800000]
        for bv in boundary_values:
            if user.annual_income == bv:
                t = RuleTrace(
                    rule="pmay_income_boundary",
                    status="uncertain",
                    reason=(
                        f"BOUNDARY: income == Rs.{bv:,} — exactly at an EWS/LIG/MIG category threshold. "
                        "Category assignment may vary by verifying authority."
                    ),
                    value_found=user.annual_income,
                    expected=f"Near boundary {bv}"
                )
                traces.append(t)
                uncertain_traces.append(t)
                break

    # ----------------------------------------------------------------
    # RULE 20: PM-SYM monthly income limit check
    # ----------------------------------------------------------------
    if rules.get("income_limit") and rules.get("income_limit_type") == "monthly":
        monthly_limit = rules["income_limit"]
        estimated_monthly = user.annual_income / 12
        if estimated_monthly > monthly_limit:
            t = RuleTrace(
                rule="monthly_income_limit",
                status="uncertain",
                reason=(
                    f"Estimated monthly income Rs.{estimated_monthly:,.0f} (annual/{12}) exceeds "
                    f"scheme limit of Rs.{monthly_limit:,}/month. However, monthly income is self-declared "
                    "and may differ from annual/12 calculation — flagged as uncertain."
                ),
                value_found=estimated_monthly,
                expected=f"<= {monthly_limit}/month"
            )
            traces.append(t)
            uncertain_traces.append(t)
        else:
            traces.append(RuleTrace(
                rule="monthly_income_limit",
                status="passed",
                value_found=estimated_monthly,
                expected=f"<= {monthly_limit}/month"
            ))

    # ----------------------------------------------------------------
    # DETECT AMBIGUITIES
    # ----------------------------------------------------------------
    ambiguity_flags = detect_ambiguities(user, scheme)
    ambiguity_penalty = compute_total_penalty(ambiguity_flags)

    # ----------------------------------------------------------------
    # DETERMINE FINAL STATUS
    # ----------------------------------------------------------------
    if hard_fails:
        status = EligibilityStatus.NOT_ELIGIBLE
    elif prerequisite_fails and not uncertain_traces:
        status = EligibilityStatus.PARTIALLY_ELIGIBLE  # Eligible but needs prerequisites
    elif prerequisite_fails and uncertain_traces:
        status = EligibilityStatus.PARTIALLY_ELIGIBLE
    elif uncertain_traces:
        status = EligibilityStatus.UNCERTAIN
    else:
        status = EligibilityStatus.FULLY_ELIGIBLE

    # ----------------------------------------------------------------
    # COMPUTE CONFIDENCE
    # ----------------------------------------------------------------
    confidence_score = compute_confidence_score(
        traces=traces,
        hard_fails=hard_fails,
        uncertain_traces=uncertain_traces,
        prerequisite_fails=prerequisite_fails,
        ambiguity_penalty=ambiguity_penalty,
        status=status,
    )
    confidence_level = compute_confidence_level(confidence_score)
    confidence_reason = _build_confidence_reason(
        confidence_score, hard_fails, uncertain_traces, prerequisite_fails, ambiguity_flags
    )

    # ----------------------------------------------------------------
    # BUILD GAP ANALYSIS (for partial/uncertain)
    # ----------------------------------------------------------------
    gap = None
    if status in (EligibilityStatus.PARTIALLY_ELIGIBLE, EligibilityStatus.UNCERTAIN):
        gap = build_gap_analysis(user, scheme, prerequisite_fails, uncertain_traces)

    return SchemeResult(
        scheme_id=scheme.scheme_id,
        scheme_name=scheme.scheme_name,
        status=status,
        confidence_score=round(confidence_score, 3),
        confidence_level=confidence_level,
        confidence_reason=confidence_reason,
        rule_trace=traces,
        ambiguity_flags=ambiguity_flags,
        gap_analysis=gap,
        application_url=scheme.application_url,
        authority=scheme.authority,
    )


def _build_confidence_reason(
    score: float,
    hard_fails: List[RuleTrace],
    uncertain: List[RuleTrace],
    prereqs: List[RuleTrace],
    ambiguities: List[AmbiguityFlag],
) -> str:
    reasons = []
    if hard_fails:
        reasons.append(f"{len(hard_fails)} rule(s) explicitly failed")
    if prereqs:
        failed_prereq_names = [t.rule for t in prereqs]
        reasons.append(f"Prerequisites missing: {', '.join(failed_prereq_names)}")
    if uncertain:
        reasons.append(f"{len(uncertain)} uncertain rule(s) could not be resolved from input")
    if ambiguities:
        total_penalty = sum(a.confidence_penalty for a in ambiguities)
        reasons.append(
            f"{len(ambiguities)} ambiguity flag(s) applied penalty of -{round(total_penalty, 2)}"
        )
    if not reasons:
        reasons.append("All rules passed with high confidence")
    return "; ".join(reasons)
