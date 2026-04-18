"""
engine/dependency.py
--------------------
Dependency and application sequencing engine for KALAM.

Builds a directed graph of:
  - Document prerequisites (Aadhaar → Bank account → DBT schemes)
  - Scheme sequencing (PMJDY before PM-KISAN)

Outputs an ordered list of steps from the dependency graph using topological sort.
"""

from typing import List, Dict, Set, Optional
from collections import defaultdict, deque
from models.result import ApplicationStep, DocumentItem, SchemeResult, EligibilityStatus


# ----------------------------------------------------------------
# Document priority tiers
# TIER 1: Foundation documents (unlock everything)
# TIER 2: Mid-level documents (unlock many schemes)
# TIER 3: Scheme-specific documents
# ----------------------------------------------------------------
DOCUMENT_PRIORITY_TIERS = {
    # TIER 1 — Foundation
    "aadhaar":                     ("HIGH",   1),
    "aadhaar_or_other_kyc":        ("HIGH",   1),
    "bank_passbook":               ("HIGH",   1),

    # TIER 2 — Frequently required
    "land_records":                ("HIGH",   2),
    "ration_card":                 ("HIGH",   2),
    "income_certificate":          ("MEDIUM", 2),
    "caste_certificate":           ("MEDIUM", 2),
    "self_declaration_no_house":   ("MEDIUM", 2),

    # TIER 3 — Scheme specific
    "mother_child_protection_card":("MEDIUM", 3),
    "girl_child_birth_certificate": ("MEDIUM", 3),
    "crop_sowing_certificate":     ("LOW",    3),
    "business_proof":              ("LOW",    3),
    "valid_prescription":          ("LOW",    3),
    "bpl_certificate":             ("LOW",    3),
    "job_card":                    ("LOW",    3),
    "identity_proof":              ("LOW",    3),
    "ration_card_or_family_id":    ("LOW",    3),
}

# Scheme dependency graph: scheme_id → [required_before scheme_ids]
# i.e., PMJDY must be done BEFORE these schemes
SCHEME_DEPENDENCIES: Dict[str, List[str]] = {
    "PMJDY":    [],                    # No dependency — it IS the foundation
    "PM_KISAN": ["PMJDY"],             # Needs bank account (PMJDY provides it)
    "MGNREGA":  ["PMJDY"],
    "PMAY":     ["PMJDY"],
    "PMJJBY":   ["PMJDY"],
    "PMSBY":    ["PMJDY"],
    "APY":      ["PMJDY"],
    "PMMVY":    ["PMJDY"],
    "PMMY":     ["PMJDY"],
    "PMFBY":    ["PMJDY"],
    "PMUY":     ["PMJDY"],
    "PMJAY":    [],                    # No bank prerequisite; uses SECC listing
    "PMBJP":    [],                    # Universal — no prerequisites
    "BBBP":     [],                    # No direct benefit; no prerequisites
    "SSY":      ["PMJDY"],
    "PMKVY":    [],                    # Aadhaar preferred, not mandatory
    "JJM":      [],                    # Infrastructure — no personal prerequisites
    "PMKSY":    [],
    "ESHRAM":    [],                    # No bank prerequisite; Aadhaar-based portal
    "PMSYM":     ["PMJDY"],             # Needs bank account for pension
}


def build_document_checklist(
    all_results: List[SchemeResult],
) -> List[DocumentItem]:
    """
    Aggregate required documents across all eligible/partial/uncertain schemes.
    Deduplicate and sort by priority tier.
    """
    # Map: document_name → list of scheme_ids requiring it
    doc_to_schemes: Dict[str, List[str]] = defaultdict(list)

    for result in all_results:
        if result.status == EligibilityStatus.NOT_ELIGIBLE:
            continue  # Don't include docs for ineligible schemes
        # We'd need the scheme object here; reconstruct from scheme_id
        # Documents are tracked per-scheme in the gap analysis
        # Instead, collect from the raw scheme data via a lookup injected at call site

    # This function receives pre-aggregated doc_to_schemes from the main runner
    # Actual aggregation happens in the main runner which has scheme objects
    return []


def build_document_checklist_from_schemes(
    eligible_scheme_ids: List[str],
    scheme_docs: Dict[str, List[str]],  # scheme_id → [document names]
) -> List[DocumentItem]:
    """
    Build prioritised document checklist.

    Args:
        eligible_scheme_ids: schemes the user is eligible/partially eligible for
        scheme_docs: mapping of scheme_id to its required documents
    """
    doc_to_schemes: Dict[str, List[str]] = defaultdict(list)

    for scheme_id in eligible_scheme_ids:
        for doc in scheme_docs.get(scheme_id, []):
            doc_to_schemes[doc].append(scheme_id)

    # Sort documents:
    # 1. By priority tier (1=HIGH, 2=MEDIUM, 3=LOW)
    # 2. Within tier, by number of schemes requiring it (descending)
    doc_items: List[DocumentItem] = []

    for doc_name, required_by in doc_to_schemes.items():
        priority_info = DOCUMENT_PRIORITY_TIERS.get(doc_name, ("LOW", 3))
        priority_label, tier = priority_info

        reason = (
            f"Required by {len(required_by)} scheme(s): {', '.join(required_by)}"
            if required_by else "Scheme-specific requirement"
        )

        doc_items.append(DocumentItem(
            document=doc_name.replace("_", " ").title(),
            required_for=required_by,
            priority=priority_label,
            reason=reason,
        ))

    # Sort: tier ascending (1 first), then count descending
    doc_items.sort(key=lambda d: (
        DOCUMENT_PRIORITY_TIERS.get(
            d.document.lower().replace(" ", "_"), ("LOW", 3)
        )[1],
        -len(d.required_for)
    ))

    return doc_items


def build_application_sequence(
    eligible_scheme_ids: List[str],
    has_aadhaar: bool,
    has_bank: bool,
) -> List[ApplicationStep]:
    """
    Build ordered application sequence using topological sort on the dependency graph.
    Bootstrap steps (Aadhaar, bank) are inserted at the beginning if missing.
    """
    steps: List[ApplicationStep] = []
    step_num = 1

    # ----------------------------------------------------------------
    # Step 0: Bootstrap — Aadhaar
    # ----------------------------------------------------------------
    if not has_aadhaar:
        steps.append(ApplicationStep(
            step=step_num,
            action="Enroll for Aadhaar at nearest Aadhaar Seva Kendra — this is the foundation for most schemes",
            scheme_or_document="Aadhaar",
            authority="UIDAI",
            depends_on=[]
        ))
        step_num += 1

    # ----------------------------------------------------------------
    # Step 1: Bootstrap — Bank account (PMJDY)
    # ----------------------------------------------------------------
    if not has_bank:
        steps.append(ApplicationStep(
            step=step_num,
            action="Open a PMJDY zero-balance bank account at any bank branch or CSC with Aadhaar",
            scheme_or_document="PMJDY",
            authority="Ministry of Finance / Nearest Bank Branch",
            depends_on=["Aadhaar"] if not has_aadhaar else []
        ))
        step_num += 1
    elif "PMJDY" in eligible_scheme_ids:
        steps.append(ApplicationStep(
            step=step_num,
            action="Verify PMJDY account features — RuPay debit card, overdraft facility up to ₹10,000 after 6 months",
            scheme_or_document="PMJDY",
            authority="Ministry of Finance",
            depends_on=[]
        ))
        step_num += 1

    # ----------------------------------------------------------------
    # Topological sort of remaining schemes
    # ----------------------------------------------------------------
    ordered = _topological_sort(eligible_scheme_ids)

    # Scheme application actions
    scheme_actions = {
        "PM_KISAN":  ("Apply for PM-KISAN at pm-kisan.gov.in or nearest CSC",                   "MoAFW / District Agriculture Office"),
        "PMFBY":     ("Enroll in PMFBY at nearest bank/CSC before crop season deadline",          "PMFBY State Nodal Agency"),
        "MGNREGA":   ("Obtain Job Card from Gram Panchayat; register for work demand",            "Gram Panchayat"),
        "PMAY":      ("Apply for PMAY at pmaymis.gov.in or nearest CSC",                         "PMAY State Nodal Agency"),
        "PMJJBY":    ("Enroll in PMJJBY at your bank by signing auto-debit consent form",         "Bank Branch"),
        "PMSBY":     ("Enroll in PMSBY at your bank by signing auto-debit consent form",          "Bank Branch"),
        "APY":        ("Enroll in APY at your bank and choose pension slab",                      "PFRDA / Bank Branch"),
        "PMMVY":     ("Apply for PMMVY at nearest Anganwadi centre or ICDS office",               "ICDS / Anganwadi Centre"),
        "PMBJP":     ("Visit nearest Janaushadhi store with prescription for subsidised medicines","PMBJP Store"),
        "PMMY":      ("Apply for MUDRA loan at nearest bank with business proof",                  "Bank Branch / MUDRA"),
        "SSY":       ("Open Sukanya Samriddhi account at Post Office or bank for daughter",       "Post Office / Bank"),
        "PMKVY":     ("Register at pmkvyofficial.org or nearest Skill India Training Centre",     "MSDE / Skill India"),
        "PMUY":      ("Apply for Ujjwala LPG connection at nearest LPG distributor with Aadhaar", "MoPNG / LPG Distributor"),
        "JJM":       ("Contact Gram Panchayat to register for functional tap water connection",   "Gram Panchayat / PHED"),
        "BBBP":      ("Contact district Women and Child Development office for BBBP programmes",  "WCD District Office"),
        "PMKSY":     ("Contact District Agriculture Office for PMKSY project near your area",     "District Agriculture Office"),
        "PMJAY":     ("Verify SECC 2011 listing at CSC; if listed, get Ayushman card with Aadhaar","NHA / CSC"),
        "ESHRAM":    ("Register at eshram.gov.in or nearest CSC with Aadhaar+bank details for e-Shram card", "Ministry of Labour / CSC"),
        "PMSYM":     ("Enroll in PM-SYM at CSC or maandhan.in with Aadhaar and bank account",               "Ministry of Labour / CSC"),
    }

    for scheme_id in ordered:
        if scheme_id in ("PMJDY",):
            continue  # Already handled above
        if scheme_id not in eligible_scheme_ids:
            continue

        action, authority = scheme_actions.get(
            scheme_id,
            (f"Apply for {scheme_id} scheme at relevant authority", "Scheme Authority")
        )
        deps = SCHEME_DEPENDENCIES.get(scheme_id, [])

        steps.append(ApplicationStep(
            step=step_num,
            action=action,
            scheme_or_document=scheme_id,
            authority=authority,
            depends_on=deps
        ))
        step_num += 1

    return steps


def _topological_sort(scheme_ids: List[str]) -> List[str]:
    """
    Kahn's algorithm topological sort on scheme dependency graph.
    Returns schemes in dependency-safe application order.
    """
    # Build in-degree map and adjacency for requested schemes only
    in_degree: Dict[str, int] = {s: 0 for s in scheme_ids}
    adjacency: Dict[str, List[str]] = defaultdict(list)

    for scheme in scheme_ids:
        deps = SCHEME_DEPENDENCIES.get(scheme, [])
        for dep in deps:
            if dep in in_degree:
                in_degree[scheme] += 1
                adjacency[dep].append(scheme)

    queue = deque([s for s in scheme_ids if in_degree[s] == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbour in adjacency[node]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    # Append any remaining (handles cycles gracefully)
    remaining = [s for s in scheme_ids if s not in result]
    result.extend(remaining)

    return result
