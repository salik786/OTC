import json
import re

from openai import OpenAI

from app.config import get_settings
from app.rag.scope_guard import FALLBACK_TEXT

settings = get_settings()
_openai_client: OpenAI | None = None


def _client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fences(raw: str) -> str:
    """The model sometimes wraps JSON in markdown fences despite instructions not to."""
    return _FENCE_RE.sub("", raw).strip()


def _qa_system_prompt(product_display_name: str) -> str:
    return f"""You are a kiosk assistant for a research study on an over-the-counter medicine called "{product_display_name}" (not a real pharmacy). You will be given leaflet excerpts for this product below, then a participant's message. Decide how to respond and reply with ONLY the spoken reply text - no labels, no explanation of your reasoning.

Decide which of these three cases applies, in this order:

CASE 1 - Small talk, or a question specifically about what topic you (the assistant) cover: greetings, "how are you", "can you hear me", thanks, goodbye / "bye" / "that's all" / "i'm done", "what can you help with" / "what medicine can you help me with" / "what do you know about" / "how can you help me", "tell me more" / "go on" (an open-ended request for more of what you already have). Reply briefly and naturally - for a capability question, name {product_display_name} as what you can answer questions about - and if it isn't already a farewell, invite a question. Do not use the leaflet excerpts for this case. This is NOT for general chit-chat about you as a person/character (favorite color, opinions, jokes) - that's case 3.

CASE 2 - A question answerable from the leaflet excerpts: what the product is used for; dose/frequency/max dose/how much or how often to take; who can take it in general terms (age ranges, children) as printed or reasonably implied by the label; warnings and side effects printed on the label; storage, expiry, missed-dose guidance; route/form questions (crushing, food, timing) if the label speaks to them; ingredients/active ingredient (the product name/title itself tells you the active ingredient and form, e.g. "Paracetamol 500mg Tablets" implies paracetamol tablets, even with no excerpt literally labeled "Active Ingredient"). Answer using ONLY the excerpts (plus that kind of direct inference from the product name) - never outside knowledge about this or any medicine. Keep it short (2-4 sentences), plain spoken language, and end with a brief reminder to ask a pharmacist if unsure.

CASE 3 - Anything else: the excerpts genuinely have nothing relevant to say (not just "no exact wording match" - genuinely nothing on the topic), OR the question needs to know something personal about this specific participant (their other medications, medical history, symptoms, "should I take this given my situation"), OR it's about a different medicine or an unrelated topic entirely. Reply with EXACTLY this sentence and nothing else: "{FALLBACK_TEXT}"

Never give personal health advice or speculate about the participant's individual situation. Never mention "excerpts", "chunks", "corpus", or that you are an AI retrieving documents - speak naturally."""


def generate_answer(query_text: str, chunks: list[dict], product_display_name: str) -> str:
    excerpts = (
        "\n\n".join(f"[{c['section_label'] or 'Leaflet excerpt'}]\n{c['text']}" for c in chunks)
        if chunks
        else "(no leaflet excerpts were retrieved for this query)"
    )
    user_content = f"Leaflet excerpts:\n\n{excerpts}\n\nParticipant message: {query_text}"

    resp = _client().chat.completions.create(
        model=settings.openai_generation_model,
        max_tokens=300,
        temperature=0,
        messages=[
            {"role": "system", "content": _qa_system_prompt(product_display_name)},
            {"role": "user", "content": user_content},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    return text or FALLBACK_TEXT


_CORE_INFO_SYSTEM_PROMPT = """You extract structured OTC medicine information from leaflet excerpts for a research kiosk.

Rules:
1. Use ONLY the leaflet excerpts provided. Never use outside knowledge.
2. Respond with ONLY a JSON object with these exact keys: product_name, used_for, dose, frequency, max_dose_24h, warnings (a list of short warning strings), full_text (a natural 4-6 sentence spoken narrative covering all the above, ending with a prompt to ask a pharmacist if unsure).
3. If a field isn't present in the excerpts, set it to null (or an empty list for warnings).
4. No text outside the JSON object."""


def generate_core_info(product_display_name: str, chunks: list[dict]) -> dict:
    if not chunks:
        return {
            "product_name": product_display_name,
            "used_for": None,
            "dose": None,
            "frequency": None,
            "max_dose_24h": None,
            "warnings": [],
            "full_text": FALLBACK_TEXT,
        }

    excerpts = "\n\n".join(f"[{c['section_label'] or 'Leaflet excerpt'}]\n{c['text']}" for c in chunks)
    user_content = f"Product: {product_display_name}\n\nLeaflet excerpts:\n\n{excerpts}"

    resp = _client().chat.completions.create(
        model=settings.openai_generation_model,
        max_tokens=1024,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _CORE_INFO_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        data = {
            "product_name": product_display_name,
            "used_for": None, "dose": None, "frequency": None, "max_dose_24h": None,
            "warnings": [], "full_text": FALLBACK_TEXT,
        }
    data.setdefault("product_name", product_display_name)
    data.setdefault("warnings", [])
    return data
