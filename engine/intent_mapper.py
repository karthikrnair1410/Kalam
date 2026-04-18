"""
engine/intent_mapper.py
------------------------
Maps normalized Hinglish / English text → UserProfile field values.

Design:
  - Pure regex + keyword rules. NO ML. Fully deterministic.
  - Returns a dict of extracted fields + list of unresolved tokens
  - Missing data is returned as None (NOT assumed False)
  - Ambiguous tokens are flagged explicitly

Each extractor returns (value, confidence: "HIGH"|"MEDIUM"|"LOW", evidence: str)
"""

import re
from typing import Optional, Tuple, Dict, Any, List
from engine.text_normalizer import normalize, resolve_state


# ---------------------------------------------------------------------------
# TYPE ALIAS
# ---------------------------------------------------------------------------
ExtractionResult = Dict[str, Any]   # field_name → value


# ---------------------------------------------------------------------------
# KEYWORD TABLES
# ---------------------------------------------------------------------------

# Positive / negative pattern fragments
NEGATION_WORDS = r"(?:nahi|nahin|nhi|no|not|nai|na|never|koi\s*nahi|bilkul\s*nahi|nhin)"
POSSESSION_WORDS = r"(?:hai|he|hain|ho|h|rakha|rakhi|mila|mili|ward|available|present|aaya|aya)"

# Occupation keywords → enum values
OCCUPATION_POSITIVE = {
    "FARMER_OWNER":         [
        r"\bkisan\b", r"\bfarmer\b", r"\bkheti\s*karta\b", r"\bkhet\s*maalik\b",
        r"\bkheti\s*karti\b", r"\bkrishak\b", r"\bkhetibadi\b",
        r"\bapni\s*zameen\s*pe\s*kheti\b",
        r"\bkheti\s*krta\b", r"\bkheti\s*krti\b",
        r"\bkheti\s*krtaa\b", r"\bkheti\s*krtee\b",
    ],
    "FARMER_TENANT":        [
        r"\bkiraayedaar\s*kisan\b", r"\btenant\s*farmer\b",
        r"\bleased?\s*land\b", r"\bkiraaye\s*ki\s*zameen\b",
        r"\bdusre\s*ki\s*zameen\s*pe\s*kheti\b",
        r"\bkiraaedar\s*kisan\b",
    ],
    "AGRICULTURAL_LABOURER":[
        r"\bkhet\s*mazdoor\b", r"\bagricultural\s*labourer\b",
        r"\bkhet\s*mein\s*kaam\b", r"\bkhet\s*worker\b",
        r"\bfarm\s*labour\b", r"\bfarm\s*worker\b",
        r"\bkhet\s*majdoor\b", r"\bkhet\s*mazdur\b",
    ],
    "UNSKILLED_LABOURER":   [
        r"\bmazdoor\b", r"\blabour\b", r"\blabourer\b",
        r"\bdaily\s*wage\b", r"\bdihadi\b", r"\bkaam\s*dhundh\b",
        r"\bukilled\s*worker\b", r"\bchota\s*kaam\b",
        r"\bmajdoor\b", r"\bmazdur\b", r"\bmajdur\b",
        r"\bdaily\s*wager\b", r"\bcoolies?\b",
    ],
    "SELF_EMPLOYED":        [
        r"\bself\s*employed\b", r"\bkhud\s*ka\s*kaam\b",
        r"\bbusiness\b", r"\bdukan\b", r"\bdukaandar\b",
        r"\bkhud\s*ka\s*business\b", r"\bapna\s*kaam\b",
        r"\bvyapaar\b", r"\bvyavsayi\b", r"\bkaarobar\b",
        r"\bdukan\s*chalata\b", r"\bdukan\s*chalati\b",
        r"\bshopkeeper\b", r"\bfreelancer?\b",
        r"\bapna\s*business\b", r"\bapna\s*dhandha\b",
    ],
    "SALARIED_PRIVATE":     [
        r"\bprivate\s*job\b", r"\bprivate\s*naukri\b",
        r"\bprivate\s*company\b", r"\bprivate\s*sector\b",
        r"\bjob\s*private\b", r"\bcompany\s*job\b",
        r"\bprivate\s*nokri\b",
    ],
    "SALARIED_GOVT":        [
        r"\bsarkari\s*naukri\b", r"\bgovernment\s*job\b",
        r"\bgovt\s*job\b", r"\bsarkari\b.*\bnaukri\b",
        r"\bsarkaari\b", r"\bsrkaari\s*kaam\b",
        r"\bpublic\s*sector\b",
        r"\bsarkari\s*nokri\b", r"\bgovt\s*nokri\b",
        r"\bgovernment\s*employee\b", r"\bgovt\s*employee\b",
    ],
    "UNEMPLOYED":           [
        r"\bberozgaar\b", r"\bunemployed\b", rf"\bkoi\s*kaam\s*{NEGATION_WORDS}\b",
        rf"\bkaam\s*{NEGATION_WORDS}\s*(?:hai|he|krta|karta)?\b", rf"\bnaukri\s*{NEGATION_WORDS}\b",
        rf"\bjob\s*{NEGATION_WORDS}\b", rf"\bno\s*job\b", rf"\bkoi\s*job\s*{NEGATION_WORDS}\b",
        r"\bberojgar\b", r"\bberojgaar\b", r"\bberoozgar\b",
        rf"\bnokri\s*{NEGATION_WORDS}\b",
        rf"\bkuch\s*{NEGATION_WORDS}\s*(?:karta|krta|karti|krti)?\b",
        r"\bghar\s*pe\s*baitha\b", r"\bghar\s*par\s*baitha\b",
        r"\bghar\s*pe\s*baithi\b", r"\bghar\s*par\s*baithi\b",
        r"\bjobless\b",
    ],
    "STUDENT":              [
        r"\bstudent\b", r"\bpadhai\b", r"\bschool\s*mein\b",
        r"\bcollege\s*mein\b", r"\bpadh\s*raha\b", r"\bpadh\s*rahi\b",
        r"\bparhna\b", r"\bpadhta\b", r"\bpadhti\b",
        r"\bvidyarthi\b", r"\bchhatra\b",
    ],
}

# Aadhaar patterns
# NOTE: allow "bhi" (also/too) as optional filler: "aadhaar bhi hai"
AADHAAR_HAS = [
    r"\baadhaa?r\s*(?:bhi\s*)?(?:hai|he|h)\b",
    r"\baadhaa?r\s*card\s*(?:bhi\s*)?(?:hai|he|h)\b",
    r"\baadhaa?r\s*(?:ban|bana)\s*(?:gaya|liya|hua)\b",
    r"\bhave\s*aadhaa?r\b", r"\baadhaa?r\s*(?:available|linked)\b",
    r"\bmere\s*paas\s*aadhaa?r\b",
    r"\baadhaa?r\s*(?:hai\s*)?mere\b",
    r"\baadhaa?r\s*(?:he|hai)\s*mere\s*(?:paas|pas)\b",
    r"\badhar\s*(?:card\s*)?(?:hai|he|h)\b",
    r"\badhar\s*(?:card\s*)?(?:bhi\s*)?(?:hai|he|h)\b",
    r"\bmere\s*(?:paas|pas)\s*adhar\b",
]
AADHAAR_NOT = [
    rf"\baadhaa?r\s*(?:bhi\s*)?{NEGATION_WORDS}\b",
    rf"\b{NEGATION_WORDS}\s*aadhaa?r\b",
    rf"\baadhaa?r\s*{NEGATION_WORDS}\s*(?:hai|he)\b", rf"\b{NEGATION_WORDS}\s*(?:hai|he)\s*aadhaa?r\b",
    rf"\baadhaa?r\s*card\s*{NEGATION_WORDS}\b", rf"\baadhaa?r\s*{NEGATION_WORDS}\s*banwaya\b",
    rf"\baadhaa?r\s*{NEGATION_WORDS}\s*banwa?\b",
    rf"\badhar\s*(?:card\s*)?{NEGATION_WORDS}\b",
]

# Bank patterns
# NOTE: allow "bhi" (also/too) as optional filler: "bank account bhi hai"
BANK_HAS = [
    r"\bbank\s*account\s*(?:bhi\s*)?(?:hai|he|h)\b",
    r"\bbank\s*(?:mein\s*)?khata\s*(?:bhi\s*)?(?:hai|he|h)\b",
    r"\bjan\s*dhan\s*account\b", r"\bjandhan\b",
    r"\bhave\s*(?:a\s*)?bank\b", r"\bbank\s*account\s*available\b",
    r"\bbank\s*account\s*khula\b", r"\bsaving\s*account\s*(?:bhi\s*)?(?:hai|he)\b",
    r"\bmere\s*(?:paas|pas)\s*bank\b",
    r"\bbank\s*(?:hai|he)\s*mera\b",
    r"\bhaan\s*bank\s*(?:hai|he|h)\b",
    r"\bbank\s*(?:account\s*)?(?:hai|he)\s*(?:mere|mera)\b",
]
BANK_NOT = [
    rf"\bbank\s*account\s*(?:bhi\s*)?{NEGATION_WORDS}\b",
    rf"\b{NEGATION_WORDS}\s*bank\s*(?:account)?\b",
    rf"\bbank\s*(?:mein\s*)?khata\s*{NEGATION_WORDS}\b", rf"\bbank\s*{NEGATION_WORDS}\s*(?:hai|he)\b",
    rf"\bbank\s*account\s*{NEGATION_WORDS}\s*(?:hai|he)\b",
    rf"\bbank\s*{NEGATION_WORDS}\s*(?:hai|he)\s*mera\b",
]

# Area type patterns
URBAN_PATTERNS  = [r"\bsheher\b", r"\bcity\b", r"\burban\b", r"\bnagar\b", r"\btown\b",
                   r"\bshahar\b", r"\bshehr\b", r"\bshahr\b", r"\bnagr\b"]
RURAL_PATTERNS  = [r"\bgaon\b", r"\bvillage\b", r"\brural\b", r"\bgraameen\b",
                   r"\bpind\b", r"\bkasbaa\b",
                   r"\bgaav\b", r"\bgawn\b", r"\bdehaat\b", r"\bdehat\b",
                   r"\bgramin\b", r"\bgrameen\b"]

# Gender patterns
MALE_PATTERNS   = [r"\baadmi\b", r"\bmard\b", r"\bmale\b", r"\bman\b",
                   r"\b(?:main|mai|me)\s+\w*\s*(?:hu|hun|hoon)\b",
                   r"\blarka\b", r"\bbhai\b", r"\bladka\b",
                   r"\bpurush\b", r"\bboy\b", r"\bladke\b"]
FEMALE_PATTERNS = [r"\baurat\b", r"\bmahila\b", r"\bfemale\b", r"\bwoman\b",
                   r"\bwomen\b", r"\blarki\b", r"\bbehen\b", r"\bstri\b", r"\bladki\b",
                   r"\blady\b", r"\bgirl\b", r"\bladkiyan\b"]

# Marital patterns
MARRIED_PATTERNS  = [r"\bshaadishuda\b", r"\bshaadi\s*ho\s*(?:gayi|gaya|hui)\b",
                     r"\bmarried\b", r"\bbivahit\b", r"\bshadi\s*(?:hai|he)\b",
                     r"\bshadi\s*ho\s*(?:gayi|gaya|chuki|chuka)\b",
                     r"\bshaadi\s*(?:hogayi|ho\s*gayi|ho\s*chuki)\b",
                     r"\bshadi\s*(?:hogayi|ho\s*chuki|ho\s*chuka)\b",
                     r"\bshaadishuda\b", r"\bshadishuda\b",]
SINGLE_PATTERNS   = [r"\bsingle\b", rf"\bshaadi\s*{NEGATION_WORDS}\b", r"\bawaara\b",
                     r"\bkuwaara\b", r"\bkuwaari\b", rf"\b{NEGATION_WORDS}\s*married\b",
                     r"\bunmarried\b", rf"\bshadi\s*{NEGATION_WORDS}\b"]
WIDOWED_PATTERNS  = [r"\bvidhwa\b", r"\bwidow\b", r"\bwidower\b",
                     r"\bpati\s*guzar\s*gaye\b", rf"\bpati\s*{NEGATION_WORDS}\s*raha\b",
                     r"\bvidhur\b"]
DIVORCED_PATTERNS = [r"\bdivorced?\b", r"\btalaq\b", r"\bdivorce\s*ho\s*(?:gaya|gayi)\b",
                     r"\btalakshuda\b"]

# Caste patterns
CASTE_MAP = {
    "SC": [r"\bsc\b", r"\bscheduled\s*caste\b", r"\bdalit\b", r"\bharijaan\b",
           r"\banusuchit\s*(?:jaati|jati)\b"],
    "ST": [r"\bst\b", r"\bscheduled\s*tribe\b", r"\btribal\b", r"\badivasi\b",
           r"\banusuchit\s*(?:janjati|jan\s*jati)\b"],
    "OBC":[r"\bobc\b", r"\bother\s*backward\b", r"\bpichhda\b", r"\bpichhdi\b",
           r"\bpichda\b", r"\bpichhra\b", r"\bbackward\s*class\b"],
    "GEN":[r"\bgeneral\b", r"\bgen\b", r"\bupper\s*caste\b", r"\bforward\s*caste\b",
           r"\bsavarna\b", r"\bopen\s*category\b", r"\bunreserved\b"],
}

# Land affirmative / negative
LAND_HAS = [
    r"\bzameen\s*hai\b", r"\bkheti\s*ki\s*zameen\s*hai\b",
    r"\bapni\s*zameen\b", r"\bown\s*land\b", r"\bkhud\s*ki\s*zameen\b",
    r"\bzameen\s*mere\s*naam\s*pe\b", r"\bkhet\s*hai\b",
]
LAND_NOT = [
    rf"\bzameen\s*{NEGATION_WORDS}\b", rf"\bzameen\s*mere\s*naam\s*(?:pe|par)\s*{NEGATION_WORDS}\b",
    rf"\b{NEGATION_WORDS}\s*land\b", r"\blandless\b", rf"\bkoi\s*zameen\s*{NEGATION_WORDS}\b",
    rf"\bzameen\s*{NEGATION_WORDS}\s*(?:hai|he)\b", rf"\bkhet\s*{NEGATION_WORDS}\b",
    rf"\bland\s*(?:mere\s*)?naam\s*(?:pe|par)\s*{NEGATION_WORDS}\b",
    rf"\bapni\s*zameen\s*{NEGATION_WORDS}\b", rf"\b{NEGATION_WORDS}\s*zameen\b",
    rf"\b(?:jamin|zamin|jamen|zamen)\s*{NEGATION_WORDS}\b",
    rf"\b(?:jamin|zamin|jamen|zamen)\s*{NEGATION_WORDS}\s*(?:hai|he)\b",
    rf"\bkoi\s*(?:jamin|zamin)\s*{NEGATION_WORDS}\b",
    r"\bno\s*land\b",
]
LAND_LEASED = [
    r"\bzameen\s*kiraaye\s*(?:pe|par)\b", r"\bleased?\s*land\b",
    r"\bkiraaye\s*ki\s*zameen\b", r"\bdusre\s*ki\s*zameen\b",
]


# ---------------------------------------------------------------------------
# MAIN MAPPER
# ---------------------------------------------------------------------------

def map_to_fields(raw_text: str, expected_field: str = None) -> Dict[str, Any]:
    """
    Entry point. Accepts raw Hinglish/Hindi/English text.

    Returns a dict with:
      "fields":   {field_name: value}  — only fields where we found evidence
      "warnings": [str]                — parse ambiguities
      "normalized_text": str           — what text was analysed after normalization
    """
    text, norm_warnings = normalize(raw_text)
    warnings: List[str] = list(norm_warnings)
    fields: Dict[str, Any] = {}

    # CONTEXT-AWARE BARE NUMBER HANDLING
    # If the user just typed a number in response to a specific question, map it directly.
    m_num = re.match(r"^\s*(\d+(?:\.\d+)?)\s*$", text)
    if m_num and expected_field:
        val_float = float(m_num.group(1))
        val_int = int(val_float)
        
        if expected_field == "age" and 5 <= val_int <= 120:
            fields["age"] = val_int
            text = "" # Cleared so other extractors don't redundantly process
        elif expected_field == "family_size" and 1 <= val_int <= 30:
            fields["family_size"] = val_int
            text = ""
        elif expected_field == "annual_income" and val_int >= 0:
            fields["annual_income"] = val_int
            text = ""
        elif expected_field == "land_owned_hectares" and val_float >= 0:
            fields["land_owned_hectares"] = val_float
            text = ""

    # CONTEXT-AWARE BARE YES/NO HANDLING
    # When the engine asks a yes/no question (aadhaar, bank), user often just says
    # "haan", "ha", "yes", "nahi", "nhi", "no" without mentioning the field name.
    bare_yes = re.match(r"^\s*(?:haan|ha|haa|han|yes|yep|yeah|ji|ji\s*ha|ji\s*haan)\s*$", text, re.IGNORECASE)
    bare_no = re.match(r"^\s*(?:nahi|nhi|nahin|nhin|no|nope|na|nai|ji\s*nahi)\s*$", text, re.IGNORECASE)
    if (bare_yes or bare_no) and expected_field in ("aadhaar_linked", "bank_account"):
        fields[expected_field] = bool(bare_yes)
        text = ""  # Prevent other extractors from misinterpreting

    # Run all extractors
    _extract_age(text, fields, warnings)
    _extract_gender(text, fields, warnings)
    _extract_state(text, fields, warnings)
    _extract_area_type(text, fields, warnings)
    _extract_income(text, fields, warnings)
    _extract_occupation(text, fields, warnings)
    _extract_land(text, fields, warnings)
    _extract_aadhaar(text, fields, warnings)
    _extract_bank(text, fields, warnings)
    _extract_caste(text, fields, warnings)
    _extract_marital(text, fields, warnings)
    _extract_family_size(text, fields, warnings)

    return {
        "fields": fields,
        "warnings": warnings,
        "normalized_text": text,
    }


# ---------------------------------------------------------------------------
# INDIVIDUAL EXTRACTORS
# ---------------------------------------------------------------------------

def _extract_age(text: str, fields: dict, warnings: list):
    """
    Patterns (tried in priority order):
      "umar 42 hai"         -> 42   (keyword before number)
      "42 saal ka hu"       -> 42   (number + saal + hu)
      "42 saal"             -> 42   (CRITICAL: bare number-first, most common Hinglish)
      "I am 30 years old"   -> 30
      "saal 42"             -> 42   (keyword before number variant)
    """
    patterns = [
        # 1. keyword before number: "umar 42", "age 35", "meri umar 28 saal"
        r"(?:umar|umr|umer|umra|aayu|age|mera|meri)\s*(?:ki\s*(?:umar|umr)\s*)?(?:hai\s*)?-?\s*(\d{1,3})\s*(?:saal|sal|year|yr|years)?",
        # 2. number + saal + optional ka/ki/ke + hu/hai: "35 saal ka hu"
        r"(\d{1,3})\s*(?:saal|sal|year(?:s)?)\s*(?:ka|ki|ke|purana|puraana)?\s*(?:hu|hun|hoon|hai)\b",
        # 3. CRITICAL FIX: bare "42 saal" / "28 years" / "28 sal" (number-first, no hu needed)
        r"\b(\d{1,3})\s*(?:saal|sal|year(?:s)?)\b",
        # 4. "I am 30" / "main 30" / "mai 30" / "mei 30" / "me 30"
        r"\b(?:i\s*am|main|mai|mei|me)\s+(\d{1,3})\b",
        # 5. saal/year before number: "saal 42 hai"
        r"(?:saal|sal|year(?:s)?)\s*(?:ki\s*(?:umar|umr)\s*)?(?:hai\s*)?(\d{1,3})",
        # 6. "age- 22" / "age : 30" (with punctuation)
        r"\bage\s*[-:=]\s*(\d{1,3})\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            age = int(m.group(1))
            if 5 <= age <= 120:
                fields["age"] = age
                return
            else:
                warnings.append(f"Age value {age} looks implausible — ignored")


def _extract_gender(text: str, fields: dict, warnings: list):
    # IMPORTANT: Check widowed/gender-implicit patterns FIRST
    # "vidhwa hu" should map to FEMALE, not MALE (from 'hu' pattern)
    if re.search(r"\bvidhwa\b", text, re.IGNORECASE):
        fields["gender"] = "FEMALE"
        return
    for p in FEMALE_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            fields["gender"] = "FEMALE"
            return
    # Male check: exclude 'hu' alone from triggering MALE if already has female context
    for p in MALE_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            fields["gender"] = "MALE"
            return


def _extract_state(text: str, fields: dict, warnings: list):
    # Try state resolver from text_normalizer
    state_code = resolve_state(text)
    if state_code:
        fields["state"] = state_code
    else:
        # Try "IN-XX" pattern directly
        m = re.search(r"\bIN-([A-Z]{2})\b", text, re.IGNORECASE)
        if m:
            fields["state"] = f"IN-{m.group(1).upper()}"


def _extract_area_type(text: str, fields: dict, warnings: list):
    for p in RURAL_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            fields["area_type"] = "RURAL"
            return
    for p in URBAN_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            fields["area_type"] = "URBAN"
            return


def _extract_income(text: str, fields: dict, warnings: list):
    """
    After normalization numbers are already expanded.
    Patterns:
      "income 200000 hai"
      "200000 per_year_annualized" (from monthly normalization)
      "kamata hu 72000"
      "72000 salary"
    """
    # Annualized from monthly conversion
    m = re.search(r"(\d+)\s*per_year_annualized", text)
    if m:
        fields["annual_income"] = int(m.group(1))
        return

    # Income keyword + number
    m = re.search(
        r"(?:income|salary|salery|kamai|kamata|kamati|earnings?|earn)\s*(?:hai|hain|mein|approximately|approx|is|about|karib)?\s*(?:rs\.?|rupees?|inr)?\s*(\d+)",
        text, re.IGNORECASE
    )
    if m:
        fields["annual_income"] = int(m.group(1))
        return

    # Number + income keyword
    m = re.search(
        r"(?:rs\.?|rupees?|inr)?\s*(\d{4,8})\s*(?:rs\.?|rupees?|income|salary|kamai|saalana|yearly|annual)",
        text, re.IGNORECASE
    )
    if m:
        fields["annual_income"] = int(m.group(1))
        return

    # Bare large number likely is income if in range 1000–10000000
    m = re.search(r"\b(\d{5,8})\b", text)
    if m:
        val = int(m.group(1))
        if 1000 <= val <= 10_000_000:
            fields["annual_income"] = val
            warnings.append(
                f"Inferred annual_income={val} from bare number — verify with user"
            )


def _extract_occupation(text: str, fields: dict, warnings: list):
    """
    Occupation is extracted by matching occupation keyword patterns.
    If multiple match, flag ambiguity.
    """
    matched = []
    for occ, patterns in OCCUPATION_POSITIVE.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                matched.append(occ)
                break

    if len(matched) == 1:
        fields["occupation"] = matched[0]
    elif len(matched) > 1:
        warnings.append(
            f"Multiple occupations detected: {matched}. Using first: {matched[0]}"
        )
        fields["occupation"] = matched[0]


def _extract_land(text: str, fields: dict, warnings: list):
    """
    Extracts:
      land_owned_hectares   (float or 0 if none)
      land_leasing_status   (OWNER | TENANT | NONE)
    """
    # Check for negation first
    for p in LAND_NOT:
        if re.search(p, text, re.IGNORECASE):
            fields["land_owned_hectares"] = 0.0
            fields["land_leasing_status"] = "NONE"
            return

    # Check for leased land
    for p in LAND_LEASED:
        if re.search(p, text, re.IGNORECASE):
            fields["land_leasing_status"] = "TENANT"
            # Don't overwrite if farmer_tenant already set occupation
            _extract_land_area(text, fields, warnings)
            return

    # Check for positive land ownership
    for p in LAND_HAS:
        if re.search(p, text, re.IGNORECASE):
            fields["land_leasing_status"] = "OWNER"
            _extract_land_area(text, fields, warnings)
            return

    # If occupation is FARMER_TENANT, infer land leasing
    if fields.get("occupation") == "FARMER_TENANT" and "land_leasing_status" not in fields:
        fields["land_leasing_status"] = "TENANT"


def _extract_land_area(text: str, fields: dict, warnings: list):
    """Extract numeric land area, converting acres → hectares."""
    # Hectares
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hectare|hectares|he\.?)\b", text, re.IGNORECASE)
    if m:
        fields["land_owned_hectares"] = float(m.group(1))
        return

    # Acres → hectares (1 acre = 0.4047 ha)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:acre|acres|ekad|ekad)\b", text, re.IGNORECASE)
    if m:
        acres = float(m.group(1))
        fields["land_owned_hectares"] = round(acres * 0.4047, 3)
        warnings.append(f"{acres} acres converted to {fields['land_owned_hectares']} hectares")
        return

    # Bigha (approx 0.2529 ha in UP — varies by state, note ambiguity)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:bigha|bighe)\b", text, re.IGNORECASE)
    if m:
        bigha = float(m.group(1))
        fields["land_owned_hectares"] = round(bigha * 0.2529, 3)
        warnings.append(
            f"{bigha} bigha converted using UP standard (0.2529 ha/bigha). "
            "Actual conversion varies by state — verify."
        )
        return


def _extract_aadhaar(text: str, fields: dict, warnings: list):
    for p in AADHAAR_NOT:
        if re.search(p, text, re.IGNORECASE):
            fields["aadhaar_linked"] = False
            return
    for p in AADHAAR_HAS:
        if re.search(p, text, re.IGNORECASE):
            fields["aadhaar_linked"] = True
            return


def _extract_bank(text: str, fields: dict, warnings: list):
    for p in BANK_NOT:
        if re.search(p, text, re.IGNORECASE):
            fields["bank_account"] = False
            return
    for p in BANK_HAS:
        if re.search(p, text, re.IGNORECASE):
            fields["bank_account"] = True
            return


def _extract_caste(text: str, fields: dict, warnings: list):
    for caste, patterns in CASTE_MAP.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                fields["caste_category"] = caste
                return


def _extract_marital(text: str, fields: dict, warnings: list):
    for p in WIDOWED_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            fields["marital_status"] = "WIDOWED"
            return
    for p in DIVORCED_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            fields["marital_status"] = "DIVORCED"
            return
    for p in MARRIED_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            fields["marital_status"] = "MARRIED"
            return
    for p in SINGLE_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            fields["marital_status"] = "SINGLE"
            return


def _extract_family_size(text: str, fields: dict, warnings: list):
    """
    "4 log hain ghar mein"  → 4
    "family mein 5 member"  → 5
    "ghar mein 6 log"       → 6
    "parivaar mein 3 log"   → 3
    """
    patterns = [
        r"(?:ghar|family|parivaar|gharwale|members?|log|sadasya)\s*(?:mein|me|mien|ke|in)?\s*(\d{1,2})\s*(?:log|members?|aadmi|logon)?",
        r"(\d{1,2})\s*(?:log|members?|aadmi|logon)\s*(?:hain|hai|hein|hon|ho)?\s*(?:ghar|family|parivaar|gharwale)?",
        r"(?:family\s*size|gharwale)\s*(?:hai|hain|is|are)?\s*(\d{1,2})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            size = int(m.group(1))
            if 1 <= size <= 30:
                fields["family_size"] = size
                return


# ---------------------------------------------------------------------------
# FOLLOW-UP QUESTION GENERATOR
# ---------------------------------------------------------------------------

# Questions to ask (in Hinglish) when a field is missing
FOLLOW_UP_QUESTIONS = {
    "hinglish": {
        "age":                 "Aapki umar kitni hai? (saal mein batayein)",
        "gender":              "Aap male hain ya female? (ladka / ladki / aur)",
        "state":               "Aap kis state mein rehte hain? (jaise UP, Bihar, Maharashtra)",
        "area_type":           "Aap gaon mein rehte hain ya sheher mein?",
        "annual_income":       "Aapki saalana income approx kitni hai? (rupees mein batayein)",
        "occupation":          "Aap kya kaam karte hain? (kisan / mazdoor / sarkari naukri / business / etc.)",
        "land_owned_hectares": "Kya aapke naam pe zameen hai? Agar hai to kitni? (hectare ya acre mein)",
        "land_leasing_status": "Zameen aapki khud ki hai, kiraaye pe hai, ya koi zameen nahi?",
        "caste_category":      "Aap kis category mein aate hain? (SC / ST / OBC / General)",
        "family_size":         "Aapke ghar mein kitne log hain?",
        "aadhaar_linked":      "Kya aapke paas Aadhaar card hai? (haan / nahi)",
        "bank_account":        "Kya aapka koi bank account hai? (haan / nahi)",
        "marital_status":      "Aapki marital status kya hai? (shaadishuda / single / vidhwa / divorced)",
    },
    "hi": {
        "age":                 "आपकी उम्र कितनी है? (वर्षों में बताएँ)",
        "gender":              "आप पुरुष हैं या महिला?",
        "state":               "आप किस राज्य में रहते हैं? (जैसे UP, Bihar, Maharashtra)",
        "area_type":           "आप गाँव में रहते हैं या शहर में?",
        "annual_income":       "आपकी सालाना आय लगभग कितनी है? (रुपयों में बताएँ)",
        "occupation":          "आप क्या काम करते हैं? (किसान / मज़दूर / सरकारी नौकरी / व्यापार आदि)",
        "land_owned_hectares": "क्या आपके नाम पर ज़मीन है? अगर है तो कितनी? (हेक्टेयर या एकड़ में)",
        "land_leasing_status": "ज़मीन आपकी खुद की है, किराये पर है, या कोई ज़मीन नहीं?",
        "caste_category":      "आप किस जाति वर्ग में आते हैं? (SC / ST / OBC / सामान्य)",
        "family_size":         "आपके घर में कितने लोग हैं?",
        "aadhaar_linked":      "क्या आपके पास आधार कार्ड है? (हाँ / नहीं)",
        "bank_account":        "क्या आपका कोई बैंक खाता है? (हाँ / नहीं)",
        "marital_status":      "आपकी वैवाहिक स्थिति क्या है? (शादीशुदा / अविवाहित / विधवा / तलाकशुदा)",
    },
    "en": {
        "age":                 "How old are you? (in years)",
        "gender":              "What is your gender? (male / female / other)",
        "state":               "Which state do you live in? (e.g. Uttar Pradesh, Bihar, Maharashtra)",
        "area_type":           "Do you live in a village (rural) or city (urban)?",
        "annual_income":       "What is your approximate annual household income? (in rupees)",
        "occupation":          "What is your primary occupation? (farmer / labourer / govt job / business / etc.)",
        "land_owned_hectares": "Do you own land? If yes, how much? (in hectares or acres)",
        "land_leasing_status": "Is the land yours, leased/rented, or do you have no land?",
        "caste_category":      "What is your caste category? (SC / ST / OBC / General)",
        "family_size":         "How many members are in your family?",
        "aadhaar_linked":      "Do you have an Aadhaar card? (yes / no)",
        "bank_account":        "Do you have a bank account? (yes / no)",
        "marital_status":      "What is your marital status? (married / single / widowed / divorced)",
    },
}

MANDATORY_FIELDS = [
    "age", "gender", "state", "area_type", "annual_income",
    "occupation", "land_leasing_status", "caste_category",
    "family_size", "aadhaar_linked", "bank_account", "marital_status"
]


def get_next_question(current_fields: Dict[str, Any], language: str = "hinglish") -> Optional[Tuple[str, str]]:
    """
    Returns (field_name, question_in_chosen_language) for the next missing mandatory field.
    language: 'hinglish' | 'hi' | 'en'
    """
    lang = language if language in FOLLOW_UP_QUESTIONS else "hinglish"
    for field in MANDATORY_FIELDS:
        if field not in current_fields or current_fields[field] is None:
            return (field, FOLLOW_UP_QUESTIONS[lang][field])
    return None


def get_all_missing_questions(current_fields: Dict[str, Any], language: str = "hinglish") -> List[Tuple[str, str]]:
    """Returns ALL missing field questions in priority order in the chosen language."""
    lang = language if language in FOLLOW_UP_QUESTIONS else "hinglish"
    missing = []
    for field in MANDATORY_FIELDS:
        if field not in current_fields or current_fields[field] is None:
            missing.append((field, FOLLOW_UP_QUESTIONS[lang][field]))
    return missing
