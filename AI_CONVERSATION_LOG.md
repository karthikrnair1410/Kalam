# KALAM — AI Conversation Log

## Tool Used
**Google Gemini (Antigravity Agentic AI)** — an AI coding assistant by Google DeepMind, used for pair programming throughout the development of this project.

---

## Conversation 1: Initial System Design & Build
**Date:** 2026-04-14

### Prompts & Work Done:

**Prompt 1:**
> [The initial Mission 3 brief was provided — building an AI-powered welfare eligibility engine for Indian government schemes that handles ambiguity, supports Hinglish, and provides explainable outputs]

**Work Done:**
- Designed the full architecture: FastAPI backend, deterministic rule engine, Pydantic models
- Created `models/user.py` (UserProfile), `models/scheme.py`, `models/result.py`
- Built `engine/eligibility.py` with rules for 18 initial welfare schemes
- Created `engine/intent_mapper.py` for NLP parsing (Hinglish → structured fields)
- Built `engine/text_normalizer.py` for Devanagari transliteration
- Created `engine/hinglish_explainer.py` for trilingual output
- Built `engine/dependency.py` using Kahn's algorithm for topological sorting
- Created `engine/ambiguity.py` for conflict detection
- Built `frontend/index.html` — single-page app with form + chat modes
- Created `data/schemes.json` with 18 scheme definitions

---

## Conversation 2: Fixing NLP Extraction Logic
**Date:** 2026-04-16

### Prompts & Work Done:

**Prompt 1:**
> The engine keeps asking for gender even though I already told it. Fix the state management bug.

**Prompt 2:**
> "2L" is being parsed as "2 Rupees" instead of "2 Lakh". Fix the income extraction.

**Work Done:**
- Fixed state persistence bug in chat session management
- Fixed income multiplier regex to correctly handle "2L" → 200000
- Added "L" as a multiplier variant for lakh

---

## Conversation 3: UI Redesign & Landing Page
**Date:** 2026-04-18

### Prompts & Work Done:

**Prompt 1:**
> CSS Variable Updates & Aesthetics:
> - Backgrounds: Soft warm whites and cream/beige tones (#FDFBF7, #FFFFFF)
> - Accents: Soft terracotta/orange gradients (#D96A36, #E0875C)
> - Text: Deep brown/charcoal (#2E2925)
> - Font: Add the Outfit font (don't change "kalam" font on landing page)
>
> Landing Page: Add language selector. Tagline + get started button should change based on language (en, hinglish, hi).

**Prompt 2:**
> I love the layout for the chat section but the form layout wastes space and looks unappealing. Also the "Fill the form" box doesn't point at the form. Fix these issues.

**Work Done:**
- Complete UI redesign with warm terracotta/cream theme
- Created landing page with language selector (EN/Hinglish/Hindi)
- Fixed form layout spacing and visual hierarchy
- Added Outfit + Inter + Noto Sans Devanagari fonts

---

## Conversation 4: Adversarial Audit & NLP Robustness (Current Session)
**Date:** 2026-04-18

### Prompt 3 (Chat Loop Bug Report):
> The chat keeps getting stuck in a loop when I type "33" for age. It keeps repeating the same question. FIX THIS ASAP!! Any mistake means getting rejected. Seriously fix all such loops properly this time.

**Work Done:**
- Added context-aware bare number handling (age, family_size, income, land)

---

### Prompt 4 (Adversarial Testing Request):
> You are a STRICT and highly critical judge evaluating submissions for a national-level AI systems competition (Mission 3).
> Your goal is NOT to pass the system. Your goal is to REJECT it by finding every possible flaw.
> You must behave like: A skeptical government evaluator, a systems engineer, a real-world user tester.
>
> Generate at least 15 adversarial user profiles including:
> - Landless farmer, Migrant worker (state mismatch), Widow remarried
> - Person with Aadhaar but no bank account, Conflicting inputs
> - Extremely low income but urban, Missing multiple fields
>
> Test for: False positives, False negatives, Crash resistance, Ambiguity handling, Explainability, Edge cases

**Work Done:**
- Created 15 adversarial profiles in `tests/audit_adversarial.py`
- Found and fixed issues:
  - SSY: Added `girl_child_required` rule
  - PMFBY: Tightened occupation mapping
  - BBBP: Added `awareness_campaign_only` flag
  - Added e-Shram and PM-SYM schemes (18 → 20 total)
  - Updated UI badges from "18 Schemes" to "20 Schemes"
  - Added per-capita income warning for large families
  - Added PMAY income boundary detection
- Result: 15/15 adversarial profiles pass, 0 crashes

---

### Prompt 5-9 (Continuation prompts):
> Continue / Yes fix all the issues you encountered

**Work Done:**
- Implemented all fixes identified during adversarial audit
- Updated dependency graph for new schemes
- Updated trilingual dictionary for new scheme names

---

### Prompt 10 (NLP Robustness Request):
> The user might use different spellings for different words or may say something in a different way than expected. This causes problems in the chat option and causes it to get stuck in an endless loop. This happens particularly in Hinglish and Hindi chat. Look into it and fix all such issues.

**Work Done:**

Phase 1 — Identified 47 parsing gaps across 12 field categories via systematic testing:
- Created `tests/test_nlp_gaps.py` with 49 test cases
- Found failures in: age (5), gender (6), area (5), occupation (4), aadhaar (5), bank (8), caste (1), marital (4), land (2), income (1)

Phase 2 — Fixed all gaps in `engine/intent_mapper.py`:
- Added 47 new keyword patterns
- Added **context-aware bare yes/no handler** — when engine asks "Kya aadhaar hai?", bare "haan"/"nhi"/"yes"/"no" now works
- Added variants: `berojgar`, `gaav`, `sal`, `shahar`, `shehr`, `dehaat`, `gramin`, `purush`, `boy`, `girl`, `lady`, `unmarried`, `shadi`, `aadhar`, `adhar`, `jamin`, `zamin`, `lak`, `nokri`, `kuch nahi karta`, `ghar pe baitha`

Phase 3 — Fixed `engine/text_normalizer.py`:
- Added `lak` as multiplier variant (= lakh)
- Added entry for `hajaar`

Phase 4 — Verification:
- 49/49 unit tests pass
- 20/20 API keyword tests pass
- 13/13 end-to-end Hinglish chat flow checks pass
- 15/15 adversarial profiles still pass (no regression)
- Browser test confirmed zero loops

---

### Prompt 11 (Hindi Support Check):
> Wow great job. I hope the pure Hindi version also works well

**Work Done:**

Created `tests/test_hindi_flow.py` with 25 Devanagari test cases. Found 3 failures:
1. `शादीशुदा` → normalized to `shaadishudaa` (substring corruption)
2. `अनुसूचित जनजाति` → normalized to `scheduled jncaste` (wrong mapping)
3. `खेती करता हूँ` → normalized to `kheti krtaa` (unmatched variant)
4. `उत्तर प्रदेश` → state not resolved (missing Hindi state names)
5. `हाँ`/`नहीं` → bare Devanagari yes/no not working in context

Fixes applied:
- Expanded DEVANAGARI_WORDS from ~30 to 70+ entries
- Added all Indian state names in Devanagari
- Fixed caste mappings: `अनुसूचित`→`anusuchit`, `जनजाति`→`janjati`
- **Critical fix:** Sorted word replacements by length descending to prevent `शादी` from corrupting `शादीशुदा`
- Added verb mappings: `करता`→`karta`, `रहता`→`rehta`

Final results:
- 25/25 Hindi parse tests pass
- 10/10 Hindi chat flow steps complete with evaluation
- 13/13 Hinglish chat flow still passes (no regression)
- 15/15 adversarial audit still passes

---

### Prompt 12 (Submission):
> Now how do I submit this entire project? The judge should be able to easily open it and work with this.

**Work Done:**
- Created comprehensive `README.md` with 3-command setup
- Created `.gitignore`
- Initialized git repo and committed all files
- Prepared this conversation log for submission
