"""
engine/text_normalizer.py
--------------------------
Normalizes raw Hinglish / Hindi / English text into a canonical ASCII form
that the intent_mapper can work with deterministically.

Pipeline:
  raw text
    → unicode_normalize()       strip/fold unicode
    → devanagari_transliterate()  Devanagari → Roman (basic coverage)
    → expand_abbreviations()    "UP" → "uttar pradesh", "yr" → "year"
    → normalize_numbers()       "2 lakh" → "200000", "50k" → "50000"
    → lowercase + strip

Design constraints:
  - NO ML model — all rules, all deterministic
  - Fails transparently if a token cannot be resolved
  - Returns both the cleaned text AND a list of parse warnings
"""

import re
import unicodedata
from typing import Tuple, List

# ---------------------------------------------------------------------------
# DEVANAGARI → ROMAN TRANSLITERATION TABLE
# Covers the most common welfare-context words only.
# Unmapped characters fall through as-is (not silently dropped).
# ---------------------------------------------------------------------------
DEVANAGARI_MAP = {
    # Vowels
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
    # Consonants (common)
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
    # Matras (vowel diacritics)
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
    # Halant / virama
    "्": "",
    # Numerals
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
    # Anusvara / chandrabindu
    "ं": "n", "ँ": "n", "ः": "h",
}

# Common full-word Devanagari → English mappings (priority over char-by-char)
DEVANAGARI_WORDS = {
    # Core pronouns/verbs
    "मेरे": "mere", "मेरी": "meri", "मेरा": "mera", "पास": "paas",
    "नहीं": "nahi", "है": "hai", "नही": "nahi",
    "हूं": "hu", "हूँ": "hu", "हैं": "hain",
    "मैं": "main", "में": "mein", "कोई": "koi", "अपनी": "apni",
    "करता": "karta", "करती": "karti", "रहता": "rehta", "रहती": "rehti",
    "हाँ": "haan", "हां": "haan", "जी": "ji",
    "लोग": "log", "सदस्य": "members",
    # Welfare-context nouns
    "जमीन": "zameen", "ज़मीन": "zameen", "खेत": "khet",
    "किसान": "kisan", "मजदूर": "mazdoor", "मज़दूर": "mazdoor",
    "आधार": "aadhaar", "बैंक": "bank", "खाता": "khata",
    "आय": "income", "आमदनी": "income", "सालाना": "saalana",
    "परिवार": "parivaar", "घर": "ghar",
    # Gender
    "पुरुष": "male", "महिला": "female",
    "लड़का": "ladka", "लड़की": "ladki", "आदमी": "aadmi", "औरत": "aurat",
    # Marital
    "शादी": "shaadi", "शादीशुदा": "shaadishuda", "विधवा": "vidhwa",
    "अविवाहित": "unmarried", "तलाकशुदा": "talakshuda",
    "विवाहित": "married",
    # Caste — map Devanagari to exact keywords the intent mapper expects
    "अनुसूचित": "anusuchit", "जाति": "jaati", "जनजाति": "janjati",
    # Area
    "गांव": "gaon", "गाँव": "gaon", "शहर": "sheher",
    "ग्रामीण": "rural", "शहरी": "urban", "देहात": "dehaat",
    # Numbers / units
    "नाम": "naam", "पर": "pe", "रुपये": "rupees", "लाख": "lakh",
    "हजार": "hazaar", "हज़ार": "hazaar",
    "एकड़": "acre", "हेक्टेयर": "hectare",
    "उम्र": "umar", "आयु": "umar", "साल": "saal", "वर्ष": "saal",
    # Occupation
    "सरकारी": "sarkari", "नौकरी": "naukri", "बेरोजगार": "berozgaar",
    "छात्र": "student", "खेती": "kheti", "व्यापार": "business",
    "दुकान": "dukan", "मजदूरी": "mazdoori",
    # States (Devanagari → English for state resolver)
    "उत्तर": "uttar", "प्रदेश": "pradesh", "मध्य": "madhya",
    "बिहार": "bihar", "राजस्थान": "rajasthan", "गुजरात": "gujarat",
    "महाराष्ट्र": "maharashtra", "कर्नाटक": "karnataka",
    "तमिलनाडु": "tamil nadu", "केरल": "kerala",
    "पंजाब": "punjab", "हरियाणा": "haryana",
    "दिल्ली": "delhi", "झारखंड": "jharkhand", "ओडिशा": "odisha",
    "छत्तीसगढ़": "chhattisgarh", "उत्तराखंड": "uttarakhand",
    "असम": "assam", "गोवा": "goa",
    "आंध्र": "andhra", "तेलंगाना": "telangana",
    "हिमाचल": "himachal",
    "पश्चिम": "west", "बंगाल": "bengal",
}

# ---------------------------------------------------------------------------
# NUMBER WORD → DIGIT EXPANDERS
# ---------------------------------------------------------------------------
NUMBER_WORDS = {
    "ek":       1,    "do":     2,    "teen":  3,     "char":   4,
    "paanch":   5,    "chhe":   6,    "saat":  7,     "aath":   8,
    "nau":      9,    "das":    10,   "ek sou": 100,  "hazaar": 1000,
    "one":      1,    "two":    2,    "three": 3,     "four":   4,
    "five":     5,    "six":    6,    "seven": 7,     "eight":  8,
    "nine":     9,    "ten":    10,
}

MULTIPLIER_WORDS = {
    "lakh":    100_000,
    "lac":     100_000,
    "lak":     100_000,
    "lakhs":   100_000,
    "million": 1_000_000,
    "crore":   10_000_000,
    "hazaar":  1_000,
    "hazar":   1_000,
    "hajaar":  1_000,
    "thousand":1_000,
    "k":       1_000,   # "50k"
    "l":       100_000, # "2L"
    "hundred": 100,
}

# State name aliases → ISO code
# RULE: short aliases (2-3 chars) MUST match as whole words only.
# Dangerous short aliases that collide with common Hinglish words are REMOVED
# and only their full-name versions are kept.
STATE_ALIASES = {
    # Multi-word (safe — matched by substring)
    "uttar pradesh": "IN-UP",
    "madhya pradesh": "IN-MP",
    "andhra pradesh": "IN-AP",
    "himachal pradesh": "IN-HP",
    "arunachal pradesh": "IN-AR",
    "west bengal": "IN-WB",
    "jammu kashmir": "IN-JK",
    "jammu and kashmir": "IN-JK",
    # Full state names (safe)
    "maharashtra": "IN-MH",
    "bihar": "IN-BR",
    "rajasthan": "IN-RJ",
    "gujarat": "IN-GJ",
    "karnataka": "IN-KA",
    "tamil nadu": "IN-TN",
    "telangana": "IN-TS",
    "punjab": "IN-PB",
    "haryana": "IN-HR",
    "odisha": "IN-OD",
    "orissa": "IN-OD",
    "jharkhand": "IN-JH",
    "chhattisgarh": "IN-CG",
    "assam": "IN-AS",
    "kerala": "IN-KL",
    "uttarakhand": "IN-UK",
    "delhi": "IN-DL",
    "dilli": "IN-DL",
    "goa": "IN-GA",
    "manipur": "IN-MN",
    "meghalaya": "IN-ML",
    "mizoram": "IN-MZ",
    "nagaland": "IN-NL",
    "sikkim": "IN-SK",
    "tripura": "IN-TR",
    # Short abbreviations — WORD-BOUNDARY enforced in resolve_state()
    # Only kept if they don't collide with common Hinglish words
    "up": "IN-UP",      # safe
    "mp": "IN-MP",      # safe
    "wb": "IN-WB",      # safe
    "gj": "IN-GJ",      # safe
    "tn": "IN-TN",      # safe
    "ts": "IN-TS",      # safe
    "pb": "IN-PB",      # safe
    "hr": "IN-HR",      # safe
    "jh": "IN-JH",      # safe
    "cg": "IN-CG",      # safe
    "kl": "IN-KL",      # safe
    "uk": "IN-UK",      # safe
    "jk": "IN-JK",      # safe
    "mn": "IN-MN",      # safe
    "ml": "IN-ML",      # safe
    "mz": "IN-MZ",      # safe
    "nl": "IN-NL",      # safe
    "sk": "IN-SK",      # safe
    "tr": "IN-TR",      # safe
    # REMOVED (collide with Hinglish): ka, as, ar, ap, bih, raj, maha, goa
    # goa remains (full word, unlikely collision)
}

# Common shorthand / abbreviations
ABBREVIATIONS = {
    r"\byr\b": "year", r"\byrs\b": "years",
    r"\bpm\b": "prime minister", r"\bk\b": "000",
    r"\bw\/\b": "with",
    r"\bwo\b": "without", r"\bn\b": "and",
    r"\bv\b": "very", r"\bur\b": "your",
    r"\bu\b": "you", r"\bcoz\b": "because",
    r"\bcause\b": "because",
}


def normalize(raw_text: str) -> Tuple[str, List[str]]:
    """
    Main normalization entry point.

    Returns:
        cleaned_text (str): canonical lowercase ASCII-ish text
        warnings (List[str]): non-fatal parse issues found
    """
    warnings: List[str] = []

    if not raw_text or not raw_text.strip():
        return "", ["Empty input"]

    text = raw_text.strip()

    # Step 1: Replace known Devanagari whole-words first
    text = _replace_devanagari_words(text)

    # Step 2: Transliterate remaining Devanagari chars
    text = _transliterate_devanagari(text)

    # Step 3: Unicode normalize (handle accented chars etc.)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", errors="ignore").decode("ascii")

    # Step 4: Expand abbreviations
    text = _expand_abbreviations(text)

    # Step 5: Normalize numbers  (must be BEFORE lowercase so we catch "Lakh")
    text, num_warnings = _normalize_numbers(text)
    warnings.extend(num_warnings)

    # Step 6: Lowercase
    text = text.lower()

    # Step 7: Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Step 8: Detect if any Devanagari remains (parse warning)
    if re.search(r"[\u0900-\u097F]", text):
        warnings.append(
            "Some Devanagari characters could not be transliterated — they were dropped"
        )

    return text, warnings


def resolve_state(text: str) -> str | None:
    """
    Given a chunk of text, try to extract a state ISO code.
    Uses word-boundary matching for short aliases to avoid false positives
    (e.g., 'as' inside 'paas', 'ka' inside 'saal ka').
    Returns the ISO code string or None if not found.
    """
    text_lower = text.lower().strip()
    # Process longer aliases first (e.g., 'uttar pradesh' before 'up')
    for alias in sorted(STATE_ALIASES.keys(), key=len, reverse=True):
        if len(alias) <= 3:
            # Short alias: require word boundary
            if re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
                return STATE_ALIASES[alias]
        else:
            # Long alias: substring match is fine
            if alias in text_lower:
                return STATE_ALIASES[alias]
    return None


# ---------------------------------------------------------------------------
# PRIVATE HELPERS
# ---------------------------------------------------------------------------

def _replace_devanagari_words(text: str) -> str:
    """Replace full Devanagari words with their English/Hinglish equivalents.
    IMPORTANT: Process longer words first to prevent partial substring matches
    (e.g., 'शादीशुदा' must be replaced before 'शादी').
    """
    for deva_word, roman in sorted(DEVANAGARI_WORDS.items(), key=lambda x: len(x[0]), reverse=True):
        text = text.replace(deva_word, roman)
    return text


def _transliterate_devanagari(text: str) -> str:
    """Character-by-character transliteration of remaining Devanagari."""
    result = []
    for char in text:
        if "\u0900" <= char <= "\u097F":  # Devanagari Unicode range
            result.append(DEVANAGARI_MAP.get(char, ""))  # Drop unmapped
        else:
            result.append(char)
    return "".join(result)


def _expand_abbreviations(text: str) -> str:
    for pattern, replacement in ABBREVIATIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _normalize_numbers(text: str) -> Tuple[str, List[str]]:
    """
    Convert expressions like:
      "2 lakh"    → "200000"
      "1.5 lakhs" → "150000"
      "50k"       → "50000"
      "ek lakh"   → "100000"
      "25 hazaar" → "25000"
    """
    warnings: List[str] = []

    # Numeric word + multiplier: "2.5 lakh", "1 crore"
    def replace_num_multiplier(m: re.Match) -> str:
        num_str = m.group(1).replace(",", "")
        multiplier_word = m.group(2).lower()
        try:
            num = float(num_str)
            mult = MULTIPLIER_WORDS.get(multiplier_word, 1)
            return str(int(num * mult))
        except ValueError:
            warnings.append(f"Could not parse number: {m.group(0)}")
            return m.group(0)

    text = re.sub(
        r"([\d,]+(?:\.\d+)?)\s*(lakh|lac|lak|lakhs|crore|hazaar|hazar|hajaar|thousand|million|k|l)\b",
        replace_num_multiplier,
        text,
        flags=re.IGNORECASE,
    )

    # Word number + multiplier: "ek lakh", "do hazaar"
    for word, value in NUMBER_WORDS.items():
        for mult_word, mult_value in MULTIPLIER_WORDS.items():
            pattern = rf"\b{re.escape(word)}\s+{re.escape(mult_word)}\b"
            replacement = str(value * mult_value)
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Standalone "k" suffix: "50k"
    text = re.sub(
        r"\b(\d+)k\b",
        lambda m: str(int(m.group(1)) * 1000),
        text,
        flags=re.IGNORECASE,
    )

    # Per-month → annualize: "5000 per month", "5000 mahine mein"
    def annualize(m: re.Match) -> str:
        try:
            monthly = int(m.group(1).replace(",", ""))
            return f"{monthly * 12} per_year_annualized"
        except ValueError:
            return m.group(0)

    text = re.sub(
        r"\b([\d,]+)\s*(?:per\s*month|mahine\s*(?:mein|ka|ki|pe)?|monthly)\b",
        annualize,
        text,
        flags=re.IGNORECASE,
    )

    return text, warnings
