# KALAM — Welfare Eligibility Engine

> **"Sabse zarooratmand logon ke liye intelligence"**
> *AI for the people who need it most*

KALAM is a deterministic, rule-based welfare eligibility engine that evaluates Indian citizens against **20 government welfare schemes** in real-time. It supports **trilingual** input (English, Hinglish, Hindi/Devanagari) and provides fully **explainable** results with document checklists and next steps.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **20 Welfare Schemes** | PM-KISAN, PMAY, MGNREGA, PM-SYM, e-Shram, SSY, and more |
| **Trilingual Chat** | Converse in English, Hinglish, or pure Hindi (Devanagari) |
| **Robust NLP** | Handles 100+ spelling variations, shorthand, and colloquialisms |
| **Context-Aware** | Bare "haan"/"nahi" responses work for yes/no questions |
| **100% Explainable** | Every eligibility decision includes a rule trace |
| **Dual Interface** | Form-based input OR conversational chat |
| **Ambiguity Detection** | Flags contradictory/uncertain inputs instead of guessing |
| **Dependency Graph** | Topologically-sorted scheme application sequence |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (tested on 3.10, 3.11, 3.12)
- **pip** (Python package manager)

### Setup (3 commands)

```bash
# 1. Clone the repository
git clone https://github.com/karthikrnair1410/Kalam.git
cd Kalam

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Open in Browser

Navigate to **http://localhost:8000** — that's it! No build step, no database, no external APIs.

---

## 🏗️ Architecture

```
kalam/
├── main.py                    # FastAPI entry point (5 endpoints)
├── requirements.txt           # Python dependencies
├── frontend/
│   └── index.html             # Single-page app (HTML + CSS + JS)
├── engine/
│   ├── __init__.py            # Engine orchestrator (run_kalam)
│   ├── eligibility.py         # 20 scheme rule evaluators
│   ├── intent_mapper.py       # NLP: text → structured fields
│   ├── text_normalizer.py     # Devanagari transliteration + normalization
│   ├── hinglish_explainer.py  # Trilingual output generator
│   ├── dependency.py          # Scheme dependency graph (Kahn's algorithm)
│   ├── ambiguity.py           # Conflict/uncertainty detector
│   ├── scoring.py             # Benefit scoring & ranking
│   └── gap_analysis.py        # Missing-data recommendations
├── models/
│   ├── user.py                # UserProfile (Pydantic model)
│   ├── scheme.py              # Scheme registry model
│   └── result.py              # EligibilityResult model
├── data/
│   └── schemes.json           # 20 scheme definitions with rules
└── tests/
    ├── audit_adversarial.py   # 15 adversarial edge-case profiles
    ├── test_chat_flow.py      # End-to-end Hinglish chat test
    ├── test_hindi_flow.py     # End-to-end Hindi (Devanagari) chat test
    ├── test_nlp_gaps.py       # 49 NLP robustness test cases
    └── test_api_keywords.py   # 20 keyword API tests
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the frontend |
| `POST` | `/evaluate` | Full evaluation from structured profile |
| `POST` | `/chat` | Conversational input → field extraction + follow-up |
| `POST` | `/parse` | Test NLP parsing (debug utility) |
| `GET` | `/health` | Health check |
| `GET` | `/schemes` | List all 20 scheme IDs and names |

### Example: Chat API

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "mai berojgar hu, gaav mein rehta hu, 28 sal ka hu",
    "session_fields": {},
    "language": "hinglish"
  }'
```

---

## 🧪 Running Tests

```bash
# NLP robustness tests (49 test cases)
python tests/test_nlp_gaps.py

# Adversarial audit (15 edge-case profiles)
python tests/audit_adversarial.py

# End-to-end Hinglish chat flow
python tests/test_chat_flow.py

# End-to-end Hindi (Devanagari) chat flow
python -X utf8 tests/test_hindi_flow.py
```

**Note:** The chat flow tests (`test_chat_flow.py`, `test_hindi_flow.py`) require the server to be running on port 8000.

---

## 🎯 Design Decisions

1. **Deterministic over Probabilistic** — No LLM/ML models. Every decision is a traceable rule with explicit thresholds, ensuring 100% explainability for government auditors.

2. **Regex-based NLP with Normalization Pipeline** — A two-stage approach:
   - Stage 1: `text_normalizer.py` converts Devanagari → transliterated text, expands number words, resolves state names
   - Stage 2: `intent_mapper.py` extracts structured fields via pattern matching with 100+ regex patterns

3. **Context-Aware Parsing** — When the engine asks a specific question (e.g., "Do you have Aadhaar?"), bare responses like "haan" or "nhi" are mapped to the correct field using `expected_field` context.

4. **Ambiguity as a Feature** — Instead of silently guessing when inputs conflict (e.g., high income + BPL claim), the engine explicitly flags ambiguities with `RuleTrace` records.

---

## 📋 Supported Schemes (20)

PM-KISAN, PM Awas Yojana (PMAY), MGNREGA, PM Ujjwala Yojana, Ayushman Bharat (PMJAY), PM Fasal Bima Yojana, PM Jan Dhan Yojana, Sukanya Samriddhi Yojana, PM Mudra Yojana, Atal Pension Yojana, Stand-Up India, PM Kaushal Vikas Yojana, Beti Bachao Beti Padhao, National Social Assistance Programme, PM Jeevan Jyoti Bima, PM Suraksha Bima, PM Janaushadhi Yojana, Jal Jeevan Mission, e-Shram, PM-SYM

---

## 🤖 AI Tools Used

This project was built using **Google Gemini (Antigravity)**, an agentic AI coding assistant by Google DeepMind. A complete log of all prompts and AI interactions across 4 development sessions is available in [`AI_CONVERSATION_LOG.md`](AI_CONVERSATION_LOG.md).

---

## 📄 License

This project was built for the CBC Recruitment Missions assessment.
