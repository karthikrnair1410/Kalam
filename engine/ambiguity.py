"""
engine/ambiguity.py
-------------------
Ambiguity detection engine for KALAM.

DESIGN PRINCIPLE:
  The engine MUST fail loudly on ambiguity.
  It must NEVER silently resolve ambiguous rules in favour of eligibility or ineligibility.
  Every ambiguity reduces confidence with a quantified penalty.
"""

from typing import List, Optional
from models.scheme import SchemeRule, AmbiguityRecord
from models.user import UserProfile, Occupation, AreaType, CasteCategory
from models.result import AmbiguityFlag


# Confidence penalties per ambiguity type
AMBIGUITY_PENALTY_MAP = {
    "VAGUE_CRITERIA":    0.15,
    "PROXY_MISMATCH":    0.25,   # hardest to resolve — requires external DB
    "STATE_VARIATION":   0.10,
    "HOUSEHOLD_DATA":    0.10,
    "OPERATIONAL_GAP":   0.05,
}

# Maximum total penalty from ambiguities (floor is 0.10 confidence for any scheme)
MAX_TOTAL_PENALTY = 0.60


def detect_ambiguities(
    user: UserProfile,
    scheme: SchemeRule,
) -> List[AmbiguityFlag]:
    """
    Evaluates all scheme-level ambiguity records against the user profile.
    Returns a list of triggered AmbiguityFlag objects with associated penalties.

    Rules:
    - If an ambiguity is triggered (its affected_field matches unknowns in user data),
      it is flagged.
    - Ambiguities that cannot be resolved from input alone are always flagged.
    - Penalty is assigned per ambiguity type from the AMBIGUITY_PENALTY_MAP.
    """
    triggered: List[AmbiguityFlag] = []

    for amb in scheme.ambiguities:
        if _is_triggered(amb, user):
            penalty = AMBIGUITY_PENALTY_MAP.get(amb.type, 0.10)
            triggered.append(
                AmbiguityFlag(
                    ambiguity_id=amb.id,
                    scheme_id=scheme.scheme_id,
                    description=amb.description,
                    type=amb.type,
                    affects_field=amb.affects_field,
                    confidence_penalty=penalty,
                )
            )

    return triggered


def _is_triggered(amb: AmbiguityRecord, user: UserProfile) -> bool:
    """
    Determine if a specific ambiguity is triggered for this user.

    Logic:
    - PROXY_MISMATCH: always triggered (cannot avoid external DB dependency)
    - STATE_VARIATION: always triggered (we cannot query per-state overrides at runtime)
    - HOUSEHOLD_DATA: always triggered (household usage not in input schema)
    - OPERATIONAL_GAP: always triggered (operational issues are external to user input)
    - VAGUE_CRITERIA: triggered if the affected field has a value that touches the vague boundary
    """

    if amb.type in ("PROXY_MISMATCH", "STATE_VARIATION", "HOUSEHOLD_DATA", "OPERATIONAL_GAP"):
        # These ambiguities cannot be resolved from user input regardless of values
        return True

    if amb.type == "VAGUE_CRITERIA":
        return _vague_criteria_triggered(amb, user)

    # Default: flag it if we can't categorise
    return True


def _vague_criteria_triggered(amb: AmbiguityRecord, user: UserProfile) -> bool:
    """
    VAGUE_CRITERIA is triggered when the user's profile touches the boundary
    of the vague rule.
    """
    field = amb.affects_field

    if field is None:
        # Scheme-level vagueness with no specific field → always triggered
        return True

    if field == "occupation":
        # Vague rules around occupation — triggered if occupation is in a boundary category
        boundary_occupations = {
            Occupation.SELF_EMPLOYED,
            Occupation.SALARIED_GOVT,
            Occupation.FARMER_TENANT,
        }
        return user.occupation in boundary_occupations

    if field == "land_leasing_status":
        # Triggered if user has any tenant/lessee relationship
        return user.land_leasing_status.value in ("TENANT", "UNKNOWN")

    if field == "annual_income":
        # Triggered if declared income is self-reported and could be inaccurate
        # We always flag this as income self-reporting is inherently uncertain
        return True

    if field == "caste_category":
        return user.caste_category in (CasteCategory.UNKNOWN, CasteCategory.SC, CasteCategory.ST)

    if field == "marital_status":
        return True  # always flag when marital status is relevant

    if field == "state":
        return True  # state variations always apply

    if field == "area_type":
        return True  # rural/urban classification can be disputed

    if field == "family_size":
        return True  # household definitions vary

    # Default: triggered
    return True


def compute_total_penalty(flags: List[AmbiguityFlag]) -> float:
    """
    Sum penalties, cap at MAX_TOTAL_PENALTY.
    Multiple ambiguities compound but never exceed the cap.
    """
    total = sum(f.confidence_penalty for f in flags)
    return min(total, MAX_TOTAL_PENALTY)
