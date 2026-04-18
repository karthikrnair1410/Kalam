"""
models/user.py
--------------
Pydantic model for user profile input.
Strict typing + validation prevents garbage-in garbage-out.
"""

from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from enum import Enum


class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    TRANSGENDER = "TRANSGENDER"


class AreaType(str, Enum):
    RURAL = "RURAL"
    URBAN = "URBAN"


class Occupation(str, Enum):
    FARMER_OWNER = "FARMER_OWNER"
    FARMER_TENANT = "FARMER_TENANT"
    AGRICULTURAL_LABOURER = "AGRICULTURAL_LABOURER"
    UNSKILLED_LABOURER = "UNSKILLED_LABOURER"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    SALARIED_PRIVATE = "SALARIED_PRIVATE"
    SALARIED_GOVT = "SALARIED_GOVT"
    UNEMPLOYED = "UNEMPLOYED"
    STUDENT = "STUDENT"
    OTHER = "OTHER"


class CasteCategory(str, Enum):
    GEN = "GEN"
    OBC = "OBC"
    SC = "SC"
    ST = "ST"
    UNKNOWN = "UNKNOWN"


class MaritalStatus(str, Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    WIDOWED = "WIDOWED"
    DIVORCED = "DIVORCED"
    UNKNOWN = "UNKNOWN"


class LandLeasingStatus(str, Enum):
    OWNER = "OWNER"
    TENANT = "TENANT"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class UserProfile(BaseModel):
    """
    Strict input schema for KALAM welfare eligibility engine.
    All fields are mandatory except land_owned_hectares.
    Null/missing mandatory fields trigger INPUT_ERROR — engine does NOT assume.
    """

    age: int
    gender: Gender
    state: str                        # ISO 3166-2:IN code e.g. "IN-UP"
    area_type: AreaType
    annual_income: int                # INR per year
    occupation: Occupation
    land_owned_hectares: Optional[float] = None   # Nullable: DATA_MISSING if absent
    land_leasing_status: LandLeasingStatus
    caste_category: CasteCategory
    family_size: int
    aadhaar_linked: bool
    bank_account: bool
    marital_status: MaritalStatus

    @field_validator("age")
    @classmethod
    def age_must_be_positive(cls, v):
        if v < 0 or v > 120:
            raise ValueError(f"Age {v} is outside plausible range (0–120)")
        return v

    @field_validator("annual_income")
    @classmethod
    def income_must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError("Annual income cannot be negative")
        return v

    @field_validator("family_size")
    @classmethod
    def family_size_must_be_positive(cls, v):
        if v < 1:
            raise ValueError("Family size must be at least 1")
        return v

    @field_validator("land_owned_hectares")
    @classmethod
    def land_must_be_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Land ownership cannot be negative")
        return v

    @field_validator("state")
    @classmethod
    def state_must_be_valid_format(cls, v):
        if not v.startswith("IN-"):
            raise ValueError(
                f"State must use ISO 3166-2 format (e.g. 'IN-UP', 'IN-MH'). Got: {v}"
            )
        return v.upper()

    @model_validator(mode="after")
    def detect_contradictions(self):
        """
        Detect logically contradictory input combinations.
        Engine NEVER evaluates contradictory inputs silently.
        """
        contradictions = []

        # Farmer declares zero land
        if (
            self.occupation == Occupation.FARMER_OWNER
            and self.land_owned_hectares is not None
            and self.land_owned_hectares == 0
        ):
            contradictions.append(
                "FARMER_OWNER occupation declared but land_owned_hectares = 0. "
                "A land-owning farmer must own some land."
            )

        # Tenant farmer claims to own land
        if (
            self.land_leasing_status == LandLeasingStatus.OWNER
            and self.occupation == Occupation.FARMER_TENANT
        ):
            contradictions.append(
                "Occupation is FARMER_TENANT but land_leasing_status is OWNER. "
                "Clarify whether user owns or leases land."
            )

        if contradictions:
            # Store on model for later use
            object.__setattr__(self, "_contradictions", contradictions)

        return self

    def get_contradictions(self) -> list:
        return getattr(self, "_contradictions", [])

    def get_warnings(self) -> list:
        """
        Non-fatal suspicious combinations that reduce confidence.
        """
        warnings = []

        if (
            self.annual_income > 500000
            and self.occupation == Occupation.UNSKILLED_LABOURER
        ):
            warnings.append(
                "Income > 5L declared for UNSKILLED_LABOURER — verify if household income or individual"
            )

        if (
            self.area_type == AreaType.URBAN
            and self.occupation == Occupation.AGRICULTURAL_LABOURER
        ):
            warnings.append(
                "Urban area_type declared with AGRICULTURAL_LABOURER occupation — "
                "verify if peri-urban or urban fringe case"
            )

        if self.age < 18 and self.occupation in [
            Occupation.FARMER_OWNER,
            Occupation.SALARIED_GOVT,
            Occupation.SALARIED_PRIVATE,
        ]:
            warnings.append(
                f"Age {self.age} is below 18 but occupation implies adult workforce participation"
            )

        # Per-capita income check: flag when per-capita income is much lower than annual
        if self.family_size >= 4:
            per_capita = self.annual_income / self.family_size
            if per_capita < 27000:  # ~BPL threshold per capita
                warnings.append(
                    f"Per-capita income is Rs.{per_capita:,.0f}/year "
                    f"(Rs.{self.annual_income:,} / {self.family_size} members) — "
                    f"below BPL threshold. Some schemes use per-capita, not household income."
                )

        return warnings
