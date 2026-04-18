"""
engine/hinglish_explainer.py
-----------------------------
Generates simple, conversational explanations for KALAM engine output.
Supports three language modes:
  - "en"       -- English
  - "hinglish" -- Hinglish (Hindi + English mix, Roman script)
  - "hi"       -- Pure Hindi (Devanagari script)
"""

from typing import List, Dict, Any, Optional, Tuple
from models.result import (
    KALAMOutput, SchemeResult, EligibilityStatus, ConfidenceLevel,
    AmbiguityFlag, GapAnalysis, ApplicationStep
)

SCHEME_NAMES = {
    "PM_KISAN":  {"en":"PM Kisan Samman Nidhi (Rs.6,000/year for farmers)",       "hinglish":"PM Kisan Samman Nidhi (6,000 rupees saal mein kisan ko)",  "hi":"पीएम किसान सम्मान निधि (किसानों को Rs.6,000 प्रति वर्ष)"},
    "PMFBY":     {"en":"PM Fasal Bima Yojana (crop insurance)",                    "hinglish":"PM Fasal Bima Yojana (fasal ka insurance)",                 "hi":"पीएम फसल बीमा योजना (फसल का बीमा)"},
    "MGNREGA":   {"en":"MGNREGA (100 days guaranteed employment)",                 "hinglish":"MGNREGA (100 din ka guaranteed kaam)",                      "hi":"मनरेगा (100 दिन का गारंटीड रोज़गार)"},
    "PMAY":      {"en":"PM Awas Yojana (housing assistance)",                      "hinglish":"PM Awas Yojana (ghar banane mein sahayata)",                "hi":"पीएम आवास योजना (घर बनाने में सहायता)"},
    "PMJJBY":    {"en":"PM Jeevan Jyoti Bima (life insurance at Rs.436/year)",     "hinglish":"PM Jeevan Jyoti Bima (jeewan bima sirf 436 rupees mein)",   "hi":"पीएम जीवन ज्योति बीमा (सिर्फ Rs.436 में जीवन बीमा)"},
    "PMSBY":     {"en":"PM Suraksha Bima (accident insurance at Rs.20/year)",      "hinglish":"PM Suraksha Bima (accident insurance sirf 20 rupees mein)", "hi":"पीएम सुरक्षा बीमा (सिर्फ Rs.20 में दुर्घटना बीमा)"},
    "APY":       {"en":"Atal Pension Yojana (pension after age 60)",               "hinglish":"Atal Pension Yojana (60 saal ke baad pension)",             "hi":"अटल पेंशन योजना (60 वर्ष के बाद पेंशन)"},
    "PMMVY":     {"en":"PM Matru Vandana Yojana (Rs.5,000 for pregnant mothers)",  "hinglish":"PM Matru Vandana Yojana (maa ko 5,000 rupees)",             "hi":"पीएम मातृ वंदना योजना (माँ को Rs.5,000 की सहायता)"},
    "PMBJP":     {"en":"PM Jan Aushadhi (subsidised medicines)",                   "hinglish":"PM Janaushadhi (sasti dawaiyaan Janaushadhi store pe)",     "hi":"पीएम जनऔषधि (जनऔषधि स्टोर पर सस्ती दवाइयाँ)"},
    "PMMY":      {"en":"PM Mudra Yojana (small business loans)",                   "hinglish":"PM Mudra Yojana (chhota business loan)",                    "hi":"पीएम मुद्रा योजना (छोटे व्यापार के लिए ऋण)"},
    "SSY":       {"en":"Sukanya Samriddhi Yojana (savings for daughter)",          "hinglish":"Sukanya Samriddhi Yojana (beti ki padhai ke liye bachat)",  "hi":"सुकन्या समृद्धि योजना (बेटी के भविष्य के लिए बचत)"},
    "PMKVY":     {"en":"PM Kaushal Vikas Yojana (free skill training)",            "hinglish":"PM Kaushal Vikas Yojana (skill training bilkul free)",      "hi":"पीएम कौशल विकास योजना (मुफ़्त कौशल प्रशिक्षण)"},
    "PMUY":      {"en":"PM Ujjwala Yojana (free LPG gas connection)",              "hinglish":"PM Ujjwala Yojana (gas connection free mein)",              "hi":"पीएम उज्ज्वला योजना (मुफ़्त एलपीजी गैस कनेक्शन)"},
    "JJM":       {"en":"Jal Jeevan Mission (tap water at home)",                   "hinglish":"Jal Jeevan Mission (ghar pe pani ka connection)",           "hi":"जल जीवन मिशन (घर पर नल से पानी का कनेक्शन)"},
    "BBBP":      {"en":"Beti Bachao Beti Padhao (girl child welfare)",             "hinglish":"Beti Bachao Beti Padhao (beti ki suraksha aur padhai)",     "hi":"बेटी बचाओ बेटी पढ़ाओ (बेटी की सुरक्षा और शिक्षा)"},
    "PMKSY":     {"en":"PM Krishi Sinchai Yojana (irrigation for farming)",        "hinglish":"PM Krishi Sinchai Yojana (kheti ke liye paani ki suvidha)", "hi":"पीएम कृषि सिंचाई योजना (खेती के लिए सिंचाई)"},
    "PMJAY":     {"en":"Ayushman Bharat (free treatment up to Rs.5 lakh)",         "hinglish":"Ayushman Bharat (5 lakh tak ka free ilaaj)",                "hi":"आयुष्मान भारत (Rs.5 लाख तक का मुफ़्त इलाज)"},
    "PMJDY":     {"en":"PM Jan Dhan Yojana (zero-balance bank account)",           "hinglish":"PM Jan Dhan Yojana (zero balance bank account)",            "hi":"पीएम जन धन योजना (शून्य शेष बैंक खाता)"},
    "ESHRAM":    {"en":"e-Shram (unorganised worker registration + Rs.2L insurance)","hinglish":"e-Shram (asangathit mazdoor registration + 2L bima)",      "hi":"ई-श्रम (असंगठित श्रमिक पंजीकरण + Rs.2L बीमा)"},
    "PMSYM":     {"en":"PM Shram Yogi Maan-dhan (pension Rs.3,000/month after 60)",  "hinglish":"PM Shram Yogi Maan-dhan (60 ke baad 3,000 pension)",      "hi":"पीएम श्रम योगी मान-धन (60 वर्ष बाद Rs.3,000 पेंशन)"},
}

RULE_FAIL = {
    "minimum_age":            {"en":"Your age ({value}) is below the minimum {expected} years required.","hinglish":"Aapki umar {value} saal hai, minimum {expected} saal chahiye.","hi":"आपकी उम्र {value} वर्ष है, न्यूनतम {expected} वर्ष होनी चाहिए।"},
    "maximum_age":            {"en":"Your age ({value}) exceeds the maximum limit of {expected} years.","hinglish":"Aapki umar {value} saal hai, limit {expected} saal tak hai.","hi":"आपकी उम्र {value} वर्ष है, अधिकतम सीमा {expected} वर्ष है।"},
    "gender_requirement":     {"en":"This scheme is only for {expected}.","hinglish":"Yeh scheme sirf {expected} ke liye hai.","hi":"यह योजना केवल {expected} के लिए है।"},
    "area_type_requirement":  {"en":"This scheme is only for {expected} areas.","hinglish":"Yeh scheme sirf {expected} area ke logon ke liye hai.","hi":"यह योजना केवल {expected} क्षेत्र के लिए है।"},
    "occupation_eligibility": {"en":"Your occupation ({value}) is not eligible.","hinglish":"Aapka occupation ({value}) eligible nahi hai.","hi":"आपका व्यवसाय ({value}) पात्र नहीं है।"},
    "land_ownership_required":{"en":"This scheme requires land ownership.","hinglish":"Is scheme ke liye apni zameen honi chahiye.","hi":"इस योजना के लिए अपनी ज़मीन होना आवश्यक है।"},
    "tenant_farmer_excluded": {"en":"Only land-owning farmers are eligible, not tenant farmers.","hinglish":"Sirf zameen ke maalik kisan eligible hain, kiraayedaar nahi.","hi":"केवल ज़मीन के मालिक किसान पात्र हैं, किराएदार नहीं।"},
    "urban_income_category":  {"en":"Your income does not fit any urban income bracket.","hinglish":"Aapki income kisi bhi urban income category mein fit nahi hoti.","hi":"आपकी आय किसी भी शहरी आय श्रेणी में नहीं आती।"},
}

AMB_MSG = {
    "VAGUE_CRITERIA": {"en":"some rules are not clearly defined","hinglish":"Kuch rules clear nahi hain","hi":"कुछ नियम स्पष्ट नहीं हैं"},
    "PROXY_MISMATCH": {"en":"actual eligibility depends on an external database","hinglish":"Actual eligibility ek database se check hogi","hi":"वास्तविक पात्रता बाहरी डेटाबेस से जाँची जाएगी"},
    "STATE_VARIATION":{"en":"this depends on your state's specific rules","hinglish":"Yeh aapke state pe depend karta hai","hi":"यह आपके राज्य के नियमों पर निर्भर करता है"},
    "HOUSEHOLD_DATA": {"en":"more household information is needed","hinglish":"Ghar ke baare mein kuch aur info chahiye","hi":"घर के बारे में और जानकारी आवश्यक है"},
    "OPERATIONAL_GAP":{"en":"there may be practical implementation issues","hinglish":"Scheme mein practical dikkat ho sakti hai","hi":"योजना में व्यावहारिक कठिनाई हो सकती है"},
}

CONF_LABEL = {
    "HIGH":  {"en":"high confidence","hinglish":"pakki baat lag rahi hai","hi":"पूर्ण विश्वास"},
    "MEDIUM":{"en":"moderate chance","hinglish":"achha chance hai",       "hi":"अच्छी संभावना"},
    "LOW":   {"en":"uncertain",      "hinglish":"thoda uncertain hai",     "hi":"अनिश्चित"},
}

DOC_NAMES = {
    "Aadhaar Card":                {"en":"Aadhaar Card (most important)","hinglish":"Aadhaar Card (sabse zaruri)","hi":"आधार कार्ड (सबसे ज़रूरी)"},
    "Aadhaar Or Other Kyc":        {"en":"Aadhaar or any KYC document","hinglish":"Aadhaar ya koi bhi KYC document","hi":"आधार या कोई KYC दस्तावेज़"},
    "Bank Passbook":               {"en":"Bank Passbook / Cancelled Cheque","hinglish":"Bank Passbook ya Cancelled Cheque","hi":"बैंक पासबुक या रद्द चेक"},
    "Land Records":                {"en":"Land Records (Khasra/Khatoni)","hinglish":"Zameen ke kagaz (Khasra/Khatoni)","hi":"ज़मीन के कागज़ (खसरा/खतौनी)"},
    "Ration Card":                 {"en":"Ration Card or Family ID","hinglish":"Ration Card ya Family ID","hi":"राशन कार्ड या परिवार पहचान पत्र"},
    "Income Certificate":          {"en":"Income Certificate (from Tehsildar)","hinglish":"Income Certificate (Tehsildar se)","hi":"आय प्रमाण पत्र (तहसीलदार से)"},
    "Caste Certificate":           {"en":"Caste Certificate","hinglish":"Jati Praman Patra","hi":"जाति प्रमाण पत्र"},
    "Self Declaration No House":   {"en":"Self-declaration of not owning a house","hinglish":"Ghar nahi hai iski self-declaration","hi":"पक्का घर न होने का स्व-घोषणा पत्र"},
    "Mother Child Protection Card":{"en":"Mother & Child Protection Card","hinglish":"Maa-Bachcha Card (Anganwadi se)","hi":"मातृ एवं शिशु सुरक्षा कार्ड"},
    "Girl Child Birth Certificate":{"en":"Girl child birth certificate","hinglish":"Beti ka Birth Certificate","hi":"बेटी का जन्म प्रमाण पत्र"},
    "Crop Sowing Certificate":     {"en":"Crop sowing certificate","hinglish":"Fasal bawai praman patra","hi":"फसल बुआई प्रमाण पत्र"},
    "Business Proof":              {"en":"Business proof (Udyam/GST)","hinglish":"Business ka proof (Udyam ya GST)","hi":"व्यापार प्रमाण (उद्यम/GST)"},
    "Valid Prescription":          {"en":"Valid doctor prescription","hinglish":"Doctor ka prescription","hi":"डॉक्टर का पर्चा"},
    "Bpl Certificate":             {"en":"BPL Certificate / SECC listing","hinglish":"BPL Certificate ya SECC listing","hi":"BPL प्रमाण पत्र या SECC सूची"},
    "Job Card":                    {"en":"MGNREGA Job Card (Gram Panchayat)","hinglish":"MGNREGA Job Card (Gram Panchayat se)","hi":"मनरेगा जॉब कार्ड (ग्राम पंचायत से)"},
    "Identity Proof":              {"en":"Any identity proof","hinglish":"Koi bhi identity proof","hi":"कोई भी पहचान प्रमाण"},
    "Ration Card Or Family Id":    {"en":"Ration Card or Family ID","hinglish":"Ration Card ya Family ID","hi":"राशन कार्ड या परिवार पहचान पत्र"},
}

PRIORITY_LABEL = {
    "HIGH":  {"en":"🔴 Urgent","hinglish":"🔴 Urgent","hi":"🔴 अत्यावश्यक"},
    "MEDIUM":{"en":"🟡 Required","hinglish":"🟡 Jaruri","hi":"🟡 ज़रूरी"},
    "LOW":   {"en":"🟢 Optional","hinglish":"🟢 Optional","hi":"🟢 वैकल्पिक"},
}

OCC_LABELS = {
    "FARMER_OWNER":         {"en":"Land-owning farmer","hinglish":"Zameen ke maalik kisan","hi":"ज़मीन के मालिक किसान"},
    "FARMER_TENANT":        {"en":"Tenant farmer","hinglish":"Kiraayedaar kisan","hi":"किराएदार किसान"},
    "AGRICULTURAL_LABOURER":{"en":"Agricultural labourer","hinglish":"Khet mazdoor","hi":"खेत मज़दूर"},
    "UNSKILLED_LABOURER":   {"en":"Unskilled worker","hinglish":"Mazdoor","hi":"अकुशल मज़दूर"},
    "SELF_EMPLOYED":        {"en":"Self-employed/business","hinglish":"Khud ka kaam/business","hi":"स्वरोज़गार / व्यापार"},
    "SALARIED_PRIVATE":     {"en":"Private sector job","hinglish":"Private job","hi":"निजी क्षेत्र की नौकरी"},
    "SALARIED_GOVT":        {"en":"Government job","hinglish":"Sarkari naukri","hi":"सरकारी नौकरी"},
    "UNEMPLOYED":           {"en":"Unemployed","hinglish":"Berozgaar","hi":"बेरोज़गार"},
    "STUDENT":              {"en":"Student","hinglish":"Chhaatr","hi":"छात्र"},
    "OTHER":                {"en":"Other","hinglish":"Aur kaam","hi":"अन्य"},
}

AREA_LABELS  = {"RURAL":{"en":"Rural (Village)","hinglish":"Gaon (Rural)","hi":"ग्रामीण (गाँव)"},"URBAN":{"en":"Urban (City)","hinglish":"Sheher (Urban)","hi":"शहरी (नगर)"}}
GENDER_LABELS= {"MALE":{"en":"Male","hinglish":"Male","hi":"पुरुष"},"FEMALE":{"en":"Female","hinglish":"Female","hi":"महिला"},"TRANSGENDER":{"en":"Transgender","hinglish":"Transgender","hi":"ट्रांसजेंडर"}}


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def explain_output(result: KALAMOutput, language: str = "hinglish") -> Dict[str, Any]:
    lang = language if language in ("en","hinglish","hi") else "hinglish"
    eligible = result.eligible_schemes
    partial  = result.partially_eligible_schemes
    uncertain= result.uncertain_schemes
    not_elig = result.not_eligible_schemes
    return {
        # Language-correct keys
        "summary_text":           _summary(result.summary, lang),
        "eligible_text":          [_eligible(s,lang) for s in eligible],
        "partial_text":           [_partial(s,lang)  for s in partial],
        "uncertain_text":         [_uncertain(s,lang) for s in uncertain],
        "not_eligible_text":      [_not_eligible(s,lang) for s in not_elig[:5]],
        "next_steps_text":        _next_steps(result, lang),
        "document_checklist_text":_doc_list(result, lang),
        "caveat_text":            _caveat(lang),
        "language":               lang,
        # Legacy Hinglish keys (backwards compat)
        "summary_hinglish":           _summary(result.summary,"hinglish"),
        "eligible_hinglish":          [_eligible(s,"hinglish") for s in eligible],
        "partial_hinglish":           [_partial(s,"hinglish")  for s in partial],
        "uncertain_hinglish":         [_uncertain(s,"hinglish") for s in uncertain],
        "not_eligible_hinglish":      [_not_eligible(s,"hinglish") for s in not_elig[:5]],
        "next_steps_hinglish":        _next_steps(result,"hinglish"),
        "document_checklist_hinglish":_doc_list(result,"hinglish"),
        "caveat_hinglish":            _caveat("hinglish"),
        "user_explanation_hinglish":  _summary(result.summary, lang),
    }


def build_chat_response(
    extracted_fields: Dict[str, Any],
    next_question: Any,
    warnings: List[str],
    eval_result: KALAMOutput = None,
    language: str = "hinglish",
) -> Dict[str, Any]:
    lang = language if language in ("en","hinglish","hi") else "hinglish"
    response = {
        "fields_collected":       extracted_fields,
        "warnings_text":          [f"⚠ {w}" for w in warnings],
        "warnings_hinglish":      [f"⚠ {w}" for w in warnings],
        "next_question_text":     None,
        "next_question_hinglish": None,
        "evaluation":             None,
        "language":               lang,
    }
    response["acknowledgment_text"]     = _ack(extracted_fields, lang)
    response["acknowledgment_hinglish"] = _ack(extracted_fields, "hinglish")

    if next_question:
        field, question = next_question
        response["next_question_text"]     = question
        response["next_question_hinglish"] = question
        response["next_question_field"]    = field
    else:
        response["next_question_field"] = None

    if eval_result:
        exp = explain_output(eval_result, lang)
        response["evaluation"] = {
            "structured":                eval_result.model_dump(),
            "user_explanation_hinglish": exp["summary_text"],
            "eligible_hinglish":         exp["eligible_text"],
            "partial_hinglish":          exp["partial_text"],
            "uncertain_hinglish":        exp["uncertain_text"],
            "next_steps_hinglish":       exp["next_steps_text"],
            "document_checklist_hinglish":exp["document_checklist_text"],
            "caveat_hinglish":           exp["caveat_text"],
        }
    return response


# ---------------------------------------------------------------------------
# PRIVATE
# ---------------------------------------------------------------------------

def _sn(s: SchemeResult, lang: str) -> str:
    return SCHEME_NAMES.get(s.scheme_id,{}).get(lang, s.scheme_name)

def _summary(sm: Dict[str,int], lang: str) -> str:
    fe=sm.get("fully_eligible",0); pe=sm.get("partially_eligible",0)
    un=sm.get("uncertain",0);      ne=sm.get("not_eligible",0)
    parts=[]
    if lang=="hi":
        if fe: parts.append(f"{fe} योजना के लिए आप पात्र हैं")
        if pe: parts.append(f"{pe} योजना के लिए कुछ काम बाकी है")
        if un: parts.append(f"{un} योजना में अस्पष्टता है")
        if ne: parts.append(f"{ne} योजना के लिए पात्र नहीं हैं")
        return ("✅ "+"।  ".join(parts)+"।") if parts else "कोई परिणाम नहीं मिला।"
    elif lang=="en":
        if fe: parts.append(f"eligible for {fe} scheme(s)")
        if pe: parts.append(f"partially eligible for {pe} scheme(s)")
        if un: parts.append(f"{un} scheme(s) uncertain")
        if ne: parts.append(f"not eligible for {ne} scheme(s)")
        return ("✅ You are "+" and ".join(parts)+".") if parts else "No results — check your profile."
    else:
        if fe: parts.append(f"{fe} scheme ke liye eligible hain")
        if pe: parts.append(f"{pe} scheme ke liye thoda kaam baaki")
        if un: parts.append(f"{un} scheme unclear")
        if ne: parts.append(f"{ne} scheme ke liye eligible nahi")
        return ("✅ "+" ; ".join(parts)+".") if parts else "Koi result nahi — profile check karein."

def _eligible(s: SchemeResult, lang: str) -> str:
    n=_sn(s,lang); pct=int(s.confidence_score*100)
    lvl=s.confidence_level.value if hasattr(s.confidence_level,"value") else s.confidence_level
    c=CONF_LABEL.get(lvl,{}).get(lang,"")
    if lang=="hi":   return f"🟢 {n} — आप पात्र हैं ({pct}% — {c})।"
    elif lang=="en": return f"🟢 {n} — You are eligible ({pct}% — {c})."
    else:            return f"🟢 {n} — Aap eligible hain ({pct}% — {c})."

def _partial(s: SchemeResult, lang: str) -> str:
    n=_sn(s,lang); pct=int(s.confidence_score*100); miss=[]
    if s.gap_analysis:
        for mc in s.gap_analysis.missing_conditions[:2]:
            r=mc.requirement.lower()
            if "aadhaar" in r:   miss.append({"en":"link Aadhaar","hinglish":"Aadhaar link karna padega","hi":"आधार लिंक करना होगा"}.get(lang,""))
            elif "bank" in r:    miss.append({"en":"open a bank account","hinglish":"bank account banana padega","hi":"बैंक खाता खोलना होगा"}.get(lang,""))
            elif "job card" in r:miss.append({"en":"get a Job Card","hinglish":"Job Card banana padega","hi":"जॉब कार्ड बनवाना होगा"}.get(lang,""))
            elif "land" in r:    miss.append({"en":"provide land records","hinglish":"zameen ka record dikhana padega","hi":"ज़मीन के कागज़ दिखाने होंगे"}.get(lang,""))
            else: miss.append(mc.requirement)
    if lang=="hi":
        m=" और ".join(miss) if miss else "कुछ पूर्वशर्तें"
        return f"🟡 {n} — लगभग पात्र हैं ({pct}%), बस {m}।"
    elif lang=="en":
        m=" and ".join(miss) if miss else "some prerequisites"
        return f"🟡 {n} — Almost eligible ({pct}%), but need to {m}."
    else:
        m=" aur ".join(miss) if miss else "kuch prerequisites"
        return f"🟡 {n} — Almost eligible hain ({pct}%), bas {m}."

def _uncertain(s: SchemeResult, lang: str) -> str:
    n=_sn(s,lang); pct=int(s.confidence_score*100)
    if s.ambiguity_flags:
        top=max(s.ambiguity_flags,key=lambda a:a.confidence_penalty)
        r=AMB_MSG.get(top.type,{}).get(lang,"")
        if lang=="hi":   return f"🔵 {n} — निश्चित नहीं ({pct}%): {r}। कार्यालय से जाँचें।"
        elif lang=="en": return f"🔵 {n} — Not certain ({pct}%): {r}. Verify with office."
        else:            return f"🔵 {n} — Pakka nahi ({pct}%): {r}. Office se verify karein."
    if lang=="hi":   return f"🔵 {n} — पात्रता अस्पष्ट ({pct}%)। कार्यालय से पुष्टि करें।"
    elif lang=="en": return f"🔵 {n} — Eligibility unclear ({pct}%). Confirm with office."
    else:            return f"🔵 {n} — Eligibility unclear ({pct}%). Office se confirm karein."

def _not_eligible(s: SchemeResult, lang: str) -> str:
    n=_sn(s,lang)
    failed=[t for t in s.rule_trace if t.status=="failed"]
    if failed:
        tmpl=RULE_FAIL.get(failed[0].rule,{}).get(lang)
        if tmpl:
            reason=tmpl.format(value=failed[0].value_found or "?",expected=failed[0].expected or "?")
            if lang=="hi":   return f"🔴 {n} — पात्र नहीं। {reason}"
            elif lang=="en": return f"🔴 {n} — Not eligible. {reason}"
            else:            return f"🔴 {n} — Eligible nahi. {reason}"
    if lang=="hi":   return f"🔴 {n} — इस योजना के लिए पात्र नहीं।"
    elif lang=="en": return f"🔴 {n} — Not eligible for this scheme."
    else:            return f"🔴 {n} — Is scheme ke liye eligible nahi."

def _next_steps(result: KALAMOutput, lang: str) -> List[str]:
    steps=[]
    for step in result.application_sequence[:6]:
        ac=step.action; sc=step.scheme_or_document; n=step.step
        if "Aadhaar" in ac:
            s={"en":f"Step {n}: Enroll for Aadhaar at nearest Aadhaar Seva Kendra.","hinglish":f"Step {n}: Pehle Aadhaar banwayein — sabse zaruri document hai.","hi":f"चरण {n}: पहले आधार कार्ड बनवाएँ — सबसे ज़रूरी दस्तावेज़।"}
        elif "PMJDY" in sc or "zero-balance" in ac.lower():
            s={"en":f"Step {n}: Open a Jan Dhan zero-balance account at any bank.","hinglish":f"Step {n}: Kisi bhi bank mein Jan Dhan account khulwayein — bilkul free.","hi":f"चरण {n}: किसी भी बैंक में जन धन खाता खुलवाएँ — बिल्कुल मुफ़्त।"}
        elif "PM-KISAN" in sc or "PM_KISAN" in sc:
            s={"en":f"Step {n}: Apply for PM-KISAN at pm-kisan.gov.in or nearest CSC.","hinglish":f"Step {n}: PM Kisan ke liye pm-kisan.gov.in ya CSC pe apply karein.","hi":f"चरण {n}: PM किसान के लिए pm-kisan.gov.in पर या CSC पर आवेदन करें।"}
        elif "MGNREGA" in sc:
            s={"en":f"Step {n}: Get MGNREGA Job Card from Gram Panchayat.","hinglish":f"Step {n}: Gram Panchayat se Job Card banwayein.","hi":f"चरण {n}: ग्राम पंचायत से जॉब कार्ड बनवाएँ।"}
        elif "SECC" in ac:
            s={"en":f"Step {n}: Visit nearest CSC to check SECC list for Ayushman Bharat.","hinglish":f"Step {n}: CSC pe jaake SECC list mein apna naam check karein.","hi":f"चरण {n}: CSC पर जाकर SECC सूची में अपना नाम जाँचें।"}
        elif "PMUY" in sc or "Ujjwala" in sc:
            s={"en":f"Step {n}: Visit nearest LPG distributor for free gas connection.","hinglish":f"Step {n}: Free gas ke liye nearest LPG distributor pe jaayein.","hi":f"चरण {n}: मुफ़्त गैस के लिए नजदीकी LPG वितरक के पास जाएँ।"}
        else:
            s={"en":f"Step {n}: {ac} — {step.authority}","hinglish":f"Step {n}: {ac} — {step.authority}","hi":f"चरण {n}: {ac} — {step.authority}"}
        steps.append(s.get(lang,s["hinglish"]))
    if not steps:
        steps.append({"en":"Visit nearest CSC for guidance.","hinglish":"Nearest CSC pe jaayein guidance ke liye.","hi":"मार्गदर्शन के लिए अपने नजदीकी CSC पर जाएँ।"}.get(lang,""))
    return steps

def _doc_list(result: KALAMOutput, lang: str) -> List[str]:
    docs=[]
    for d in result.document_checklist:
        f=DOC_NAMES.get(d.document,{}).get(lang,d.document)
        p=PRIORITY_LABEL.get(d.priority,{}).get(lang,d.priority)
        uf=", ".join(d.required_for[:3])
        tail={"en":f"needed for {uf}","hinglish":f"{uf} ke liye","hi":f"{uf} के लिए"}.get(lang,"")
        docs.append(f"{p}: {f} — ({tail})")
    return docs

def _caveat(lang: str) -> str:
    return {
        "en":      "⚠ This engine is rule-based — please verify final decisions with your local Panchayat / Block office.",
        "hinglish":"⚠ Yeh engine rules pe based hai — final decision ke liye nagar panchayat / block office se verify karein.",
        "hi":      "⚠ यह इंजन नियम-आधारित है — अंतिम निर्णय के लिए अपने ग्राम पंचायत / ब्लॉक कार्यालय से अवश्य जाँचें।",
    }.get(lang,"")

def _ack(fields: Dict[str,Any], lang: str) -> str:
    parts=[]
    if "age" in fields:
        parts.append({"en":f"Age: {fields['age']} yrs","hinglish":f"Umar: {fields['age']} saal","hi":f"उम्र: {fields['age']} वर्ष"}.get(lang,""))
    if "gender" in fields:
        g=GENDER_LABELS.get(fields["gender"],{}).get(lang,fields["gender"])
        parts.append({"en":f"Gender: {g}","hinglish":f"Gender: {g}","hi":f"लिंग: {g}"}.get(lang,""))
    if "state" in fields:
        parts.append({"en":f"State: {fields['state']}","hinglish":f"State: {fields['state']}","hi":f"राज्य: {fields['state']}"}.get(lang,""))
    if "area_type" in fields:
        a=AREA_LABELS.get(fields["area_type"],{}).get(lang,fields["area_type"])
        parts.append({"en":f"Area: {a}","hinglish":f"Area: {a}","hi":f"क्षेत्र: {a}"}.get(lang,""))
    if "annual_income" in fields:
        inc=fields["annual_income"]
        s=f"Rs.{inc//100000}L" if inc>=100000 else f"Rs.{inc:,}"
        parts.append({"en":f"Income: ~{s}/yr","hinglish":f"Income: ~{s} saalana","hi":f"आय: ~{s} प्रतिवर्ष"}.get(lang,""))
    if "occupation" in fields:
        o=OCC_LABELS.get(fields["occupation"],{}).get(lang,fields["occupation"])
        parts.append({"en":f"Occupation: {o}","hinglish":f"Kaam: {o}","hi":f"व्यवसाय: {o}"}.get(lang,""))
    if "caste_category" in fields:
        parts.append({"en":f"Caste: {fields['caste_category']}","hinglish":f"Category: {fields['caste_category']}","hi":f"जाति वर्ग: {fields['caste_category']}"}.get(lang,""))
    if "aadhaar_linked" in fields:
        v=fields["aadhaar_linked"]
        a=("Yes ✅" if v else "No ❌") if lang=="en" else ("Hai ✅" if v else "Nahi ❌") if lang=="hinglish" else ("है ✅" if v else "नहीं ❌")
        parts.append({"en":f"Aadhaar: {a}","hinglish":f"Aadhaar: {a}","hi":f"आधार: {a}"}.get(lang,""))
    if "bank_account" in fields:
        v=fields["bank_account"]
        a=("Yes ✅" if v else "No ❌") if lang=="en" else ("Hai ✅" if v else "Nahi ❌") if lang=="hinglish" else ("है ✅" if v else "नहीं ❌")
        parts.append({"en":f"Bank: {a}","hinglish":f"Bank account: {a}","hi":f"बैंक खाता: {a}"}.get(lang,""))
    if "land_owned_hectares" in fields:
        lv = fields["land_owned_hectares"]
        if lv is not None:
            parts.append({"en":f"Land: {lv} ha","hinglish":f"Zameen: {lv} hectare","hi":f"ज़मीन: {lv} हेक्टेयर"}.get(lang,""))
    if "land_leasing_status" in fields:
        ls = fields["land_leasing_status"]
        ls_labels = {"OWNER":{"en":"Owned","hinglish":"Apni","hi":"अपनी"}, "TENANT":{"en":"Leased","hinglish":"Kiraaye pe","hi":"किराये पर"}, "NONE":{"en":"No land","hinglish":"Koi zameen nahi","hi":"कोई ज़मीन नहीं"}, "UNKNOWN":{"en":"Unknown","hinglish":"Pata nahi","hi":"पता नहीं"}}
        ll = ls_labels.get(ls,{}).get(lang,ls)
        parts.append({"en":f"Land status: {ll}","hinglish":f"Zameen: {ll}","hi":f"ज़मीन: {ll}"}.get(lang,""))
    if "family_size" in fields:
        parts.append({"en":f"Family: {fields['family_size']} members","hinglish":f"Ghar mein: {fields['family_size']} log","hi":f"परिवार: {fields['family_size']} सदस्य"}.get(lang,""))
    if "marital_status" in fields:
        ms = fields["marital_status"]
        ms_labels = {"SINGLE":{"en":"Single","hinglish":"Single","hi":"अविवाहित"}, "MARRIED":{"en":"Married","hinglish":"Shaadishuda","hi":"विवाहित"}, "WIDOWED":{"en":"Widowed","hinglish":"Vidhwa/Vidhur","hi":"विधवा/विधुर"}, "DIVORCED":{"en":"Divorced","hinglish":"Talakshuda","hi":"तलाकशुदा"}, "UNKNOWN":{"en":"Unknown","hinglish":"Pata nahi","hi":"अज्ञात"}}
        ml = ms_labels.get(ms,{}).get(lang,ms)
        parts.append({"en":f"Marital: {ml}","hinglish":f"Marital: {ml}","hi":f"वैवाहिक: {ml}"}.get(lang,""))
    parts=[p for p in parts if p]
    if not parts:
        return {"en":"Could not understand — please give more details.","hinglish":"Kuch samajh nahi aaya — thoda aur batayein?","hi":"कुछ समझ नहीं आया — थोड़ा और बताएँ?"}.get(lang,"")
    prefix={"en":"Understood: ","hinglish":"Samajh gaye: ","hi":"समझ गए: "}.get(lang,"")
    return prefix+", ".join(parts)+"."
