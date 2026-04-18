from engine.intent_mapper import map_to_fields
from engine.hinglish_explainer import build_chat_response

msg1 = "Main 25 saal ka hu aur koi job nhi krta. Sc category se belong krta hu aur Gujarat me rehta hu. No land."
r1 = map_to_fields(msg1)
print(f"Extracted dict: {r1['fields']}")

chat_resp = build_chat_response(
    extracted_fields=r1["fields"],
    next_question=("gender", "Aap male hain ya female?"),
    warnings=r1["warnings"]
)

print(f"ACK: {chat_resp['acknowledgment_hinglish']}")
