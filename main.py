"""
main.py
-------
FastAPI entry point for the KALAM welfare eligibility engine.

Endpoints:
  POST /evaluate   → Full scheme evaluation + Hinglish dual output
  POST /chat       → Conversational Hinglish input → field extraction + follow-up
  POST /ask        → Structured missing-field question handler
  GET  /schemes    → List all scheme IDs and names
  GET  /health     → Health check
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ValidationError
from typing import Optional, Dict, Any, List
import traceback
from pathlib import Path

from models.user import UserProfile
from engine import run_kalam, SCHEME_REGISTRY
from engine.intent_mapper import map_to_fields, get_next_question, get_all_missing_questions, MANDATORY_FIELDS
from engine.hinglish_explainer import explain_output, build_chat_response


app = FastAPI(
    title="KALAM — Welfare Eligibility Engine",
    description=(
        "Knowledge-based Allocation and Linkage to Assistance Mechanisms. "
        "Rule-based, explainable, uncertainty-aware matching engine for Indian welfare schemes. "
        "Supports English, Hindi, and Hinglish input."
    ),
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = Path(__file__).parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


# ----------------------------------------------------------------
# GET /
# ----------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def serve_frontend():
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "KALAM Engine v1.1 running. POST to /evaluate or /chat"}


# ----------------------------------------------------------------
# GET /health
# ----------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "engine": "KALAM",
        "version": "1.1.0",
        "schemes_loaded": len(SCHEME_REGISTRY),
        "hinglish_support": True,
    }


# ----------------------------------------------------------------
# GET /schemes
# ----------------------------------------------------------------
@app.get("/schemes")
async def list_schemes():
    return {
        "total": len(SCHEME_REGISTRY),
        "schemes": [
            {
                "scheme_id": s.scheme_id,
                "scheme_name": s.scheme_name,
                "type": s.type,
                "authority": s.authority,
                "ambiguity_count": len(s.ambiguities),
            }
            for s in SCHEME_REGISTRY
        ]
    }


# ----------------------------------------------------------------
# POST /evaluate  (now with dual Hinglish output)
# ----------------------------------------------------------------
@app.post("/evaluate")
async def evaluate(user_data: Dict[str, Any]):
    """
    Full evaluation endpoint — returns BOTH structured output AND Hinglish explanation.

    Input: User profile JSON
    Output: {
        structured_output: {...},
        user_explanation_hinglish: "...",
        next_steps_hinglish: [...],
        document_checklist_hinglish: [...]
    }
    """
    try:
        user = UserProfile(**user_data)
    except ValidationError as e:
        return JSONResponse(
            status_code=422,
            content={
                "error": "INPUT_ERROR",
                "message": "Kuch fields missing ya galat hain — please dobara check karein",
                "message_hinglish": "Kuch fields missing ya galat hain. Neeche dekho kya problem hai.",
                "details": e.errors(),
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": "PARSE_ERROR",
                "message": str(e),
            }
        )

    try:
        result = run_kalam(user)
        hinglish = explain_output(result)

        # Dual output: structured + Hinglish
        return {
            "structured_output":          result.model_dump(),
            "user_explanation_hinglish":  hinglish["summary_hinglish"],
            "eligible_hinglish":          hinglish["eligible_hinglish"],
            "partial_hinglish":           hinglish["partial_hinglish"],
            "uncertain_hinglish":         hinglish["uncertain_hinglish"],
            "not_eligible_hinglish":      hinglish["not_eligible_hinglish"],
            "next_steps_hinglish":        hinglish["next_steps_hinglish"],
            "document_checklist_hinglish":hinglish["document_checklist_hinglish"],
            "caveat_hinglish":            hinglish["caveat_hinglish"],
        }

    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse(
            status_code=500,
            content={
                "error": "ENGINE_ERROR",
                "message": str(e),
                "traceback": tb,
            }
        )


# ----------------------------------------------------------------
# POST /chat  ← NEW: Conversational Hinglish input
# ----------------------------------------------------------------
class ChatRequest(BaseModel):
    """
    Conversational chat turn.
    - message: what the user typed (Hinglish / Hindi / English)
    - session_fields: accumulated fields from previous turns (pass {} to start)
    - language: 'hinglish' | 'hi' | 'en'  (default: hinglish)
    """
    message: str
    session_fields: Dict[str, Any] = {}
    language: str = "hinglish"


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Conversational Hinglish endpoint.

    Flow:
    1. Normalize + extract fields from free-text message
    2. Merge with session_fields
    3. If all mandatory fields collected → run full evaluation
    4. Else → return next follow-up question in Hinglish

    Returns:
    {
        "acknowledgment_hinglish": "Samajh gaye: ...",
        "fields_collected": {...},      ← merge of session + this turn
        "next_question_hinglish": "...", ← next thing to ask, or null
        "next_question_field": "...",
        "warnings_hinglish": [...],
        "evaluation": {                 ← present only when all fields collected
            "structured": {...},
            "user_explanation_hinglish": "...",
            "eligible_hinglish": [...],
            "partial_hinglish": [...],
            "next_steps_hinglish": [...],
            "document_checklist_hinglish": [...],
            "caveat_hinglish": "..."
        }
    }
    """
    language = request.language if request.language in ("en","hinglish","hi") else "hinglish"

    # Step 0: Determine the expected field based on what was missing before this turn
    expected_field = None
    last_q = get_next_question(request.session_fields, language=language)
    if last_q:
        expected_field = last_q[0]

    # Step 1: Extract fields from this message, optionally using the expected context
    extraction = map_to_fields(request.message, expected_field=expected_field)
    new_fields = extraction["fields"]
    warnings   = extraction["warnings"]

    # Step 2: Merge with session (new fields override session if more specific)
    merged_fields: Dict[str, Any] = {**request.session_fields, **new_fields}

    # Step 3: Check what's still missing (in the chosen language)
    next_q = get_next_question(merged_fields, language=language)

    # Step 4: If all mandatory collected, attempt evaluation
    eval_result = None
    if next_q is None:
        # All mandatory fields present — run evaluation
        profile_data = {**merged_fields}
        if "land_owned_hectares" not in profile_data:
            profile_data["land_owned_hectares"] = None
        try:
            user = UserProfile(**profile_data)
            eval_result = run_kalam(user)
        except ValidationError as ve:
            # Some field is still invalid — ask the first failing field
            failing = ve.errors()[0].get("loc", ["unknown"])[0]
            warnings.append(
                f"Field '{failing}' ki value sahi nahi hai — dobara batayein"
            )
            next_q = (failing, f"'{failing}' ke baare mein dobara batayein?")
        except Exception as e:
            warnings.append(f"Evaluation mein dikkat: {str(e)}")

    return build_chat_response(
        extracted_fields=merged_fields,
        next_question=next_q,
        warnings=warnings,
        eval_result=eval_result,
        language=language,
    )


# ----------------------------------------------------------------
# POST /parse  ← Utility: test Hinglish parsing only
# ----------------------------------------------------------------
class ParseRequest(BaseModel):
    message: str

@app.post("/parse")
async def parse_hinglish(request: ParseRequest):
    """
    Utility endpoint: parse a Hinglish sentence and return extracted fields.
    Useful for testing the intent mapper.
    """
    result = map_to_fields(request.message)
    return {
        "input":            request.message,
        "normalized_text":  result["normalized_text"],
        "extracted_fields": result["fields"],
        "warnings":         result["warnings"],
        "fields_found":     len(result["fields"]),
    }


# ----------------------------------------------------------------
# POST /ask  (legacy — kept for backwards compatibility)
# ----------------------------------------------------------------
class AskRequest(BaseModel):
    partial_profile: Dict[str, Any]

FIELD_QUESTIONS_HINGLISH = {
    "age":                 "Aapki umar kitni hai? (saal mein)",
    "gender":              "Aap male hain ya female?",
    "state":               "Aap kis state mein rehte hain? (jaise UP, Bihar, MH)",
    "area_type":           "Aap gaon mein rehte hain ya sheher mein?",
    "annual_income":       "Aapki saalana income approx kitni hai?",
    "occupation":          "Aap kya kaam karte hain? (kisan / mazdoor / sarkari / business)",
    "land_leasing_status": "Zameen khud ki hai, kiraaye pe,ya koi zameen nahi?",
    "caste_category":      "Aap SC / ST / OBC / General mein se kaun se hain?",
    "family_size":         "Aapke ghar mein kitne log hain?",
    "aadhaar_linked":      "Kya Aadhaar card hai? (haan / nahi)",
    "bank_account":        "Kya bank account hai? (haan / nahi)",
    "marital_status":      "Aapki marital status kya hai? (shaadishuda / single / vidhwa)",
}

@app.post("/ask")
async def ask_follow_up(request: AskRequest):
    profile = request.partial_profile
    missing_fields = [
        f for f in MANDATORY_FIELDS if f not in profile or profile[f] is None
    ]
    follow_up_questions = {
        f: FIELD_QUESTIONS_HINGLISH.get(f, f) for f in missing_fields
    }
    partial_result = None
    if len(missing_fields) <= 3:
        attempt = {**profile}
        if "land_owned_hectares" not in attempt:
            attempt["land_owned_hectares"] = None
        try:
            user = UserProfile(**attempt)
            result = run_kalam(user)
            hinglish = explain_output(result)
            partial_result = {
                "summary": result.summary,
                "user_explanation_hinglish": hinglish["summary_hinglish"],
            }
        except Exception:
            pass

    return {
        "missing_fields": missing_fields,
        "follow_up_questions_hinglish": follow_up_questions,
        "fields_provided": len(MANDATORY_FIELDS) - len(missing_fields),
        "total_required": len(MANDATORY_FIELDS),
        "partial_evaluation": partial_result,
    }


# ----------------------------------------------------------------
# GET /scheme/{scheme_id}
# ----------------------------------------------------------------
@app.get("/scheme/{scheme_id}")
async def get_scheme_detail(scheme_id: str):
    scheme = next((s for s in SCHEME_REGISTRY if s.scheme_id == scheme_id), None)
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme '{scheme_id}' not found")
    return scheme.model_dump()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
