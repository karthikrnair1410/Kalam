"""
engine/gap_analysis.py
-----------------------
Gap analysis engine for KALAM.

For partially_eligible and uncertain schemes:
- Identifies EXACTLY what the user is missing
- Provides actionable steps with authority and time estimates
- Identifies conflicting conditions that block eligibility
"""

from typing import List
from models.user import UserProfile, Occupation, AreaType
from models.scheme import SchemeRule
from models.result import (
    RuleTrace, GapAnalysis, MissingCondition, ConflictingCondition
)


# Authority lookup for document fulfillment
DOCUMENT_FULFILLMENT = {
    "aadhaar": MissingCondition(
        requirement="Aadhaar Card (linked and eKYC verified)",
        how_to_fulfill="Visit nearest Aadhaar Seva Kendra with identity proof (birth certificate, voter ID, etc.)",
        authority="UIDAI — Unique Identification Authority of India",
        estimated_time="1–2 weeks"
    ),
    "bank_account": MissingCondition(
        requirement="Bank Account (preferably PMJDY zero-balance account)",
        how_to_fulfill="Visit any bank branch or CSC with Aadhaar. PMJDY accounts require zero minimum balance.",
        authority="Nearest bank branch / Common Service Centre",
        estimated_time="Same day"
    ),
    "job_card": MissingCondition(
        requirement="MGNREGA Job Card",
        how_to_fulfill="Apply at Gram Panchayat office with Aadhaar and household details.",
        authority="Gram Panchayat",
        estimated_time="1–2 weeks"
    ),
    "land_records": MissingCondition(
        requirement="Land records (Khasra/Khatoni/Khesra)",
        how_to_fulfill="Obtain from District Revenue Office or check state land records portal (e.g., bhulekh.up.gov.in for UP)",
        authority="District Revenue Office / Patwari",
        estimated_time="1–3 days"
    ),
    "ration_card": MissingCondition(
        requirement="Ration Card / Family ID",
        how_to_fulfill="Apply at District Food and Civil Supplies Office with Aadhaar and family proof.",
        authority="District Food and Civil Supplies Office",
        estimated_time="2–4 weeks"
    ),
    "income_certificate": MissingCondition(
        requirement="Income Certificate",
        how_to_fulfill="Apply at Tehsil/Block office with self-declaration. Tehsildar issues the certificate.",
        authority="Tehsildar / Block Development Officer",
        estimated_time="1–2 weeks"
    ),
    "caste_certificate": MissingCondition(
        requirement="Caste Certificate (SC/ST/OBC as applicable)",
        how_to_fulfill="Apply at Tehsil/Block office with supporting documents.",
        authority="Tehsildar / District Social Welfare Office",
        estimated_time="2–4 weeks"
    ),
    "mother_child_protection_card": MissingCondition(
        requirement="Mother and Child Protection (MCP) Card",
        how_to_fulfill="Obtain from nearby Anganwadi centre or Primary Health Center at registration of pregnancy.",
        authority="ICDS Anganwadi Centre / Primary Health Centre",
        estimated_time="Same day at registration"
    ),
    "self_declaration_no_house": MissingCondition(
        requirement="Self-declaration of not owning a pucca house",
        how_to_fulfill="Self-declaration form available at PMAY application portal or CSC.",
        authority="Common Service Centre / Online Portal",
        estimated_time="Same day"
    ),
    "business_proof": MissingCondition(
        requirement="Business existence proof (for PMMY)",
        how_to_fulfill="Provide business registration, GST certificate, Udyam registration, or even self-declaration of enterprise.",
        authority="Nearest bank branch",
        estimated_time="Varies"
    ),
    "girl_child_birth_certificate": MissingCondition(
        requirement="Girl child's birth certificate",
        how_to_fulfill="Obtain from municipal corporation, panchayat, or hospital where child was born.",
        authority="Municipal Corporation / Gram Panchayat / Hospital",
        estimated_time="1–7 days"
    ),
    "bpl_certificate": MissingCondition(
        requirement="BPL Certificate or SECC listing proof",
        how_to_fulfill="Check SECC 2011 listing at nearby CSC. For BPL certificate, apply at Gram Panchayat.",
        authority="Common Service Centre / Gram Panchayat",
        estimated_time="1–3 days for verification"
    ),
    "valid_prescription": MissingCondition(
        requirement="Valid medical prescription (for prescription drugs at Janaushadhi stores)",
        how_to_fulfill="Obtain from any registered medical practitioner.",
        authority="Registered Medical Practitioner",
        estimated_time="Same day"
    ),
}

# Prerequisite rule → fulfillment key
PREREQUISITE_TO_FULFILLMENT = {
    "aadhaar_required":       "aadhaar",
    "bank_account_required":  "bank_account",
    "job_card_required":      "job_card",
}


def build_gap_analysis(
    user: UserProfile,
    scheme: SchemeRule,
    prerequisite_fails: List[RuleTrace],
    uncertain_traces: List[RuleTrace],
) -> GapAnalysis:
    """
    Build a gap analysis for schemes with missing prerequisites or uncertain conditions.
    """
    missing_conditions: List[MissingCondition] = []
    conflicting_conditions: List[ConflictingCondition] = []
    suggested_actions: List[str] = []

    # ----------------------------------------------------------------
    # Map failed prerequisites to fulfillment instructions
    # ----------------------------------------------------------------
    for trace in prerequisite_fails:
        key = PREREQUISITE_TO_FULFILLMENT.get(trace.rule)
        if key and key in DOCUMENT_FULFILLMENT:
            missing_conditions.append(DOCUMENT_FULFILLMENT[key])
        else:
            # Fallback for unmapped prerequisites
            missing_conditions.append(MissingCondition(
                requirement=trace.rule.replace("_", " ").title(),
                how_to_fulfill="Contact scheme authority for specific requirement fulfillment",
                authority=scheme.authority,
                estimated_time="Unknown"
            ))

    # ----------------------------------------------------------------
    # Add document requirements for uncertain traces
    # ----------------------------------------------------------------
    for trace in uncertain_traces:
        if trace.rule == "land_ownership_required":
            missing_conditions.append(DOCUMENT_FULFILLMENT["land_records"])

        elif "income" in trace.rule.lower():
            missing_conditions.append(DOCUMENT_FULFILLMENT["income_certificate"])

        elif "caste" in trace.rule.lower():
            missing_conditions.append(DOCUMENT_FULFILLMENT["caste_certificate"])

    # ----------------------------------------------------------------
    # Detect conflicting conditions
    # ----------------------------------------------------------------
    # Check: FARMER_OWNER + FARMER_TENANT conflict
    if (
        user.occupation == Occupation.FARMER_TENANT
        and scheme.rules.get("tenant_farmers_eligible") is False
    ):
        conflicting_conditions.append(ConflictingCondition(
            rule_a="occupation == FARMER_TENANT",
            rule_b="tenant_farmers_eligible == False",
            description=(
                "User is a tenant farmer but scheme requires land ownership. "
                "These conditions directly conflict — eligibility cannot be resolved without "
                "verifying land ownership records."
            )
        ))

    # Check: Urban user applying for rural scheme
    if (
        user.area_type == AreaType.URBAN
        and scheme.rules.get("area_type") == "RURAL"
    ):
        conflicting_conditions.append(ConflictingCondition(
            rule_a="area_type == URBAN",
            rule_b="scheme requires RURAL",
            description="User is in an urban area but scheme is exclusively for rural households."
        ))

    # ----------------------------------------------------------------
    # Generate suggested actions (in order of priority)
    # ----------------------------------------------------------------
    if not user.aadhaar_linked:
        suggested_actions.append(
            "Step 1: Enroll for Aadhaar at nearest Aadhaar Seva Kendra — this unlocks most schemes"
        )
    if not user.bank_account:
        suggested_actions.append(
            "Step 2: Open PMJDY account at any bank branch — zero balance, Aadhaar needed"
        )
    if uncertain_traces:
        unresolved = [t.rule for t in uncertain_traces]
        suggested_actions.append(
            f"Clarify the following to improve eligibility determination: {', '.join(unresolved)}"
        )
    if conflicting_conditions:
        suggested_actions.append(
            "Resolve conflicting eligibility conditions by contacting scheme authority before applying"
        )

    # Remove duplicate missing conditions by requirement name
    seen = set()
    unique_missing = []
    for mc in missing_conditions:
        if mc.requirement not in seen:
            seen.add(mc.requirement)
            unique_missing.append(mc)

    return GapAnalysis(
        scheme_id=scheme.scheme_id,
        scheme_name=scheme.scheme_name,
        missing_conditions=unique_missing,
        conflicting_conditions=conflicting_conditions,
        suggested_actions=suggested_actions,
    )
