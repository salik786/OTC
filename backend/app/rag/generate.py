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


_QA_SYSTEM_PROMPT = f"""You answer questions about an over-the-counter medicine for a research kiosk (not a real pharmacy).

Rules, no exceptions:
1. Answer ONLY using the leaflet excerpts provided below. Never use outside knowledge about this or any medicine.
2. Reasonable inference from what IS in the excerpts counts as answering - e.g. if the product name/title says "Paracetamol 500mg Tablets", that tells you the active ingredient (paracetamol) and the form (tablets), even if no excerpt has a section literally labeled "Active Ingredient" or "Form". Only use the fallback sentence (rule 3) when the excerpts genuinely say nothing that bears on the question at all - not just because the exact wording of the question doesn't appear verbatim.
3. If the excerpts truly do not contain enough information to answer, respond with EXACTLY this sentence and nothing else: "{FALLBACK_TEXT}"
4. Keep answers short (2-4 sentences), plain language, suitable for reading aloud by text-to-speech.
5. Never give personal health advice, never speculate about the participant's individual situation.
6. Do not mention "excerpts", "chunks", "corpus", or that you are an AI retrieving documents - speak naturally as a kiosk assistant.
7. Always end with a reminder to speak to a pharmacist if unsure, unless you are outputting the fallback sentence."""


def generate_answer(query_text: str, chunks: list[dict]) -> str:
    if not chunks:
        return FALLBACK_TEXT

    excerpts = "\n\n".join(f"[{c['section_label'] or 'Leaflet excerpt'}]\n{c['text']}" for c in chunks)
    user_content = f"Leaflet excerpts:\n\n{excerpts}\n\nParticipant question: {query_text}"

    resp = _client().chat.completions.create(
        model=settings.openai_generation_model,
        max_tokens=300,
        messages=[
            {"role": "system", "content": _QA_SYSTEM_PROMPT},
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
