"""
models/result.py
----------------
Output models for the KALAM engine.
Every field is intended to be fully traced to rules — no black boxes.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


class EligibilityStatus(str, Enum):
    FULLY_ELIGIBLE = "fully_eligible"
    PARTIALLY_ELIGIBLE = "partially_eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNCERTAIN = "uncertain"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RuleTrace(BaseModel):
    """One rule evaluation record."""
    rule: str
    status: str                         # passed | failed | uncertain | skipped
    reason: Optional[str] = None
    value_found: Optional[Any] = None
    expected: Optional[Any] = None


class AmbiguityFlag(BaseModel):
    """A specific ambiguity detected during evaluation."""
    ambiguity_id: str
    scheme_id: str
    description: str
    type: str
    affects_field: Optional[str]
    confidence_penalty: float           # how much to subtract from raw confidence


class MissingCondition(BaseModel):
    requirement: str
    how_to_fulfill: str
    authority: str
    estimated_time: str


class ConflictingCondition(BaseModel):
    rule_a: str
    rule_b: str
    description: str


class GapAnalysis(BaseModel):
    scheme_id: str
    scheme_name: str
    missing_conditions: List[MissingCondition]
    conflicting_conditions: List[ConflictingCondition]
    suggested_actions: List[str]


class SchemeResult(BaseModel):
    """Full result for one scheme evaluation."""
    scheme_id: str
    scheme_name: str
    status: EligibilityStatus
    confidence_score: float             # 0.0 – 1.0
    confidence_level: ConfidenceLevel
    confidence_reason: str
    rule_trace: List[RuleTrace]
    ambiguity_flags: List[AmbiguityFlag]
    gap_analysis: Optional[GapAnalysis] = None
    application_url: str
    authority: str


class DocumentItem(BaseModel):
    document: str
    required_for: List[str]
    priority: str                       # HIGH | MEDIUM | LOW
    reason: str


class ApplicationStep(BaseModel):
    step: int
    action: str
    scheme_or_document: str
    authority: str
    depends_on: Optional[List[str]] = []


class InputValidation(BaseModel):
    status: str                         # OK | INPUT_ERROR | CONTRADICTION_DETECTED
    errors: List[str]
    warnings: List[str]
    contradictions: List[str]


class KALAMOutput(BaseModel):
    """Top-level output from the KALAM engine."""
    engine: str = "KALAM"
    version: str = "1.0.0"
    evaluated_at: str
    user_profile_hash: str

    input_validation: InputValidation

    eligible_schemes: List[SchemeResult]
    partially_eligible_schemes: List[SchemeResult]
    not_eligible_schemes: List[SchemeResult]
    uncertain_schemes: List[SchemeResult]

    gap_analysis: List[GapAnalysis]
    document_checklist: List[DocumentItem]
    application_sequence: List[ApplicationStep]
    ambiguities_detected: List[AmbiguityFlag]

    summary: Dict[str, int]             # counts per category
