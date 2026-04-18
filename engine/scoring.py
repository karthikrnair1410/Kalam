"""
engine/scoring.py
-----------------
Confidence scoring logic for KALAM.

Scoring is DETERMINISTIC and fully traceable:
- Base score starts at 1.0
- Penalties deducted for each failure type
- Ambiguity penalty layered on top
- Result clamped to [0.05, 1.0]

This module does NOT make eligibility decisions —
that is purely eligibility.py's job.
"""

from typing import List
from models.result import RuleTrace, EligibilityStatus, ConfidenceLevel


# Penalty weights
PENALTY_HARD_FAIL          = 0.80   # Hard fail collapses confidence significantly
PENALTY_PER_UNCERTAIN      = 0.12   # Each unresolved uncertain trace
PENALTY_PER_PREREQUISITE   = 0.08   # Each missing prerequisite (user can fulfill)
PENALTY_BOUNDARY_VALUE     = 0.05   # Boundary-value traces

# Minimum confidence (never report 0 — that implies certainty of ineligibility)
CONFIDENCE_FLOOR = 0.05
CONFIDENCE_CEILING = 1.0


def compute_confidence_score(
    traces: List[RuleTrace],
    hard_fails: List[RuleTrace],
    uncertain_traces: List[RuleTrace],
    prerequisite_fails: List[RuleTrace],
    ambiguity_penalty: float,
    status: EligibilityStatus,
) -> float:
    """
    Compute a 0.0–1.0 confidence score from rule evaluation results.

    The score represents how confident KALAM is in the eligibility determination,
    NOT how likely the user is to be eligible.

    - A NOT_ELIGIBLE result with HIGH confidence means we are SURE they are ineligible.
    - A FULLY_ELIGIBLE result with LOW confidence means the match is likely but uncertain.
    """
    score = CONFIDENCE_CEILING

    # Hard failures make confidence near-zero (we are confident they're ineligible)
    # But we still deduct the rest for traceability
    if hard_fails:
        score -= PENALTY_HARD_FAIL

    # Each uncertain rule reduces our confidence in the determination
    for trace in uncertain_traces:
        score -= PENALTY_PER_UNCERTAIN
        # Extra penalty for boundary values (they're inherently less reliable)
        if trace.reason and "BOUNDARY" in trace.reason:
            score -= PENALTY_BOUNDARY_VALUE

    # Prerequisites are solvable — less severe penalty
    score -= len(prerequisite_fails) * PENALTY_PER_PREREQUISITE

    # Apply ambiguity layer penalty
    score -= ambiguity_penalty

    # Clamp to floor and ceiling
    score = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEILING, score))
    return round(score, 3)


def compute_confidence_level(score: float) -> ConfidenceLevel:
    """
    Convert numeric score to HIGH/MEDIUM/LOW level.

    Thresholds:
    - HIGH:   >= 0.75  (strong match or strong rejection)
    - MEDIUM: >= 0.45  (probable match with unresolved elements)
    - LOW:    < 0.45   (significant uncertainty or multiple ambiguities)
    """
    if score >= 0.75:
        return ConfidenceLevel.HIGH
    elif score >= 0.45:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW
