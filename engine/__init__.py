"""
engine/__init__.py
------------------
Main orchestrator for the KALAM engine.
Loads scheme rules, runs evaluation across all schemes, and outputs the final result.
"""

import json
import hashlib
import datetime
from pathlib import Path
from typing import List, Dict
from collections import defaultdict

from models.user import UserProfile
from models.scheme import SchemeRule
from models.result import (
    KALAMOutput, SchemeResult, EligibilityStatus,
    InputValidation, GapAnalysis, AmbiguityFlag
)
from engine.eligibility import evaluate_scheme
from engine.dependency import (
    build_document_checklist_from_schemes,
    build_application_sequence,
)


# Load scheme data from JSON on startup
_SCHEMES_PATH = Path(__file__).parent.parent / "data" / "schemes.json"

def _load_schemes() -> List[SchemeRule]:
    with open(_SCHEMES_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [SchemeRule(**s) for s in raw]


# Cache schemes in memory (loaded once)
SCHEME_REGISTRY: List[SchemeRule] = _load_schemes()


def run_kalam(user: UserProfile) -> KALAMOutput:
    """
    Main entrypoint for the KALAM eligibility engine.

    Steps:
    1. Validate input
    2. Evaluate each scheme
    3. Bucket results
    4. Build document checklist
    5. Build application sequence
    6. Aggregate ambiguities
    7. Return structured output
    """

    # ----------------------------------------------------------------
    # Step 1: Input Validation
    # ----------------------------------------------------------------
    contradictions = user.get_contradictions()
    warnings = user.get_warnings()

    input_validation = InputValidation(
        status="CONTRADICTION_DETECTED" if contradictions else "OK",
        errors=[],
        warnings=warnings,
        contradictions=contradictions,
    )

    # If there are contradictions, we can still continue but with reduced confidence
    # Hard contradictions (like farmer + 0 land) will cause specific rule failures naturally

    # ----------------------------------------------------------------
    # Step 2: Evaluate all schemes
    # ----------------------------------------------------------------
    all_results: List[SchemeResult] = []
    for scheme in SCHEME_REGISTRY:
        result = evaluate_scheme(user, scheme)
        all_results.append(result)

    # ----------------------------------------------------------------
    # Step 3: Bucket results
    # ----------------------------------------------------------------
    eligible:         List[SchemeResult] = []
    partially:        List[SchemeResult] = []
    not_eligible:     List[SchemeResult] = []
    uncertain:        List[SchemeResult] = []

    for r in all_results:
        if r.status == EligibilityStatus.FULLY_ELIGIBLE:
            eligible.append(r)
        elif r.status == EligibilityStatus.PARTIALLY_ELIGIBLE:
            partially.append(r)
        elif r.status == EligibilityStatus.NOT_ELIGIBLE:
            not_eligible.append(r)
        elif r.status == EligibilityStatus.UNCERTAIN:
            uncertain.append(r)

    # ----------------------------------------------------------------
    # Step 4: Document checklist
    # ----------------------------------------------------------------
    # Build scheme_id → documents map from scheme registry
    scheme_docs: Dict[str, List[str]] = {
        s.scheme_id: s.documents_required for s in SCHEME_REGISTRY
    }

    actionable_schemes = [
        r.scheme_id for r in (eligible + partially + uncertain)
    ]
    document_checklist = build_document_checklist_from_schemes(
        actionable_schemes, scheme_docs
    )

    # ----------------------------------------------------------------
    # Step 5: Application sequence
    # ----------------------------------------------------------------
    application_sequence = build_application_sequence(
        eligible_scheme_ids=actionable_schemes,
        has_aadhaar=user.aadhaar_linked,
        has_bank=user.bank_account,
    )

    # ----------------------------------------------------------------
    # Step 6: Aggregate all ambiguity flags
    # ----------------------------------------------------------------
    all_ambiguities: List[AmbiguityFlag] = []
    for r in all_results:
        if r.status != EligibilityStatus.NOT_ELIGIBLE:
            all_ambiguities.extend(r.ambiguity_flags)

    # Deduplicate ambiguities by ambiguity_id
    seen_amb_ids = set()
    unique_ambiguities: List[AmbiguityFlag] = []
    for amb in all_ambiguities:
        if amb.ambiguity_id not in seen_amb_ids:
            seen_amb_ids.add(amb.ambiguity_id)
            unique_ambiguities.append(amb)

    # ----------------------------------------------------------------
    # Step 7: Gap analysis aggregation
    # ----------------------------------------------------------------
    gap_analyses: List[GapAnalysis] = [
        r.gap_analysis for r in (partially + uncertain)
        if r.gap_analysis is not None
    ]

    # ----------------------------------------------------------------
    # Compute hash and timestamp
    # ----------------------------------------------------------------
    profile_str = user.model_dump_json()
    profile_hash = hashlib.sha256(profile_str.encode()).hexdigest()[:16]
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return KALAMOutput(
        engine="KALAM",
        version="1.0.0",
        evaluated_at=timestamp,
        user_profile_hash=profile_hash,
        input_validation=input_validation,
        eligible_schemes=eligible,
        partially_eligible_schemes=partially,
        not_eligible_schemes=not_eligible,
        uncertain_schemes=uncertain,
        gap_analysis=gap_analyses,
        document_checklist=document_checklist,
        application_sequence=application_sequence,
        ambiguities_detected=unique_ambiguities,
        summary={
            "fully_eligible":    len(eligible),
            "partially_eligible": len(partially),
            "uncertain":         len(uncertain),
            "not_eligible":      len(not_eligible),
            "total_ambiguities": len(unique_ambiguities),
        }
    )
