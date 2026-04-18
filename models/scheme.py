"""
models/scheme.py
----------------
Pydantic models for scheme rule data loaded from schemes.json.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class AmbiguityRecord(BaseModel):
    id: str
    description: str
    type: str          # VAGUE_CRITERIA | PROXY_MISMATCH | STATE_VARIATION | HOUSEHOLD_DATA | OPERATIONAL_GAP
    affects_field: Optional[str] = None


class OccupationMap(BaseModel):
    eligible: List[str]
    not_eligible: List[str]
    ambiguous: List[str]


class SchemeRule(BaseModel):
    scheme_id: str
    scheme_name: str
    type: str
    authority: str
    application_url: str
    rules: Dict[str, Any]
    occupation_map: OccupationMap
    documents_required: List[str]
    ambiguities: List[AmbiguityRecord]
    exclusions: Optional[Dict[str, Any]] = {}
    state_variations: Optional[Dict[str, Any]] = {}
    # Scheme-specific optional fields
    urban_rules: Optional[Dict[str, Any]] = None
    rural_rules: Optional[Dict[str, Any]] = None
    loan_categories: Optional[Dict[str, Any]] = None
    household_categories: Optional[List[str]] = None
    rural_deprivation_criteria: Optional[List[str]] = None
    urban_occupation_criteria: Optional[List[str]] = None
