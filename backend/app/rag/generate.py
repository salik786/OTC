import json
import re

from anthropic import Anthropic

from app.config import get_settings
from app.rag.scope_guard import FALLBACK_TEXT

settings = get_settings()
_anthropic_client: Anthropic | None = None


def _client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fences(raw: str) -> str:
    """Claude sometimes wraps JSON in markdown fences despite instructions not to."""
    return _FENCE_RE.sub("", raw).strip()


_QA_SYSTEM_PROMPT = f"""You answer questions about an over-the-counter medicine for a research kiosk (not a real pharmacy).

Rules, no exceptions:
1. Answer ONLY using the leaflet excerpts provided below. Never use outside knowledge about this or any medicine.
2. If the excerpts do not contain enough information to answer, respond with EXACTLY this sentence and nothing else: "{FALLBACK_TEXT}"
3. Keep answers short (2-4 sentences), plain language, suitable for reading aloud by text-to-speech.
4. Never give personal health advice, never speculate about the participant's individual situation.
5. Do not mention "excerpts", "chunks", "corpus", or that you are an AI retrieving documents - speak naturally as a kiosk assistant.
6. Always end with a reminder to speak to a pharmacist if unsure, unless you are outputting the fallback sentence."""


def generate_answer(query_text: str, chunks: list[dict]) -> str:
    if not chunks:
        return FALLBACK_TEXT

    excerpts = "\n\n".join(f"[{c['section_label'] or 'Leaflet excerpt'}]\n{c['text']}" for c in chunks)
    user_content = f"Leaflet excerpts:\n\n{excerpts}\n\nParticipant question: {query_text}"

    resp = _client().messages.create(
        model=settings.anthropic_model,
        max_tokens=300,
        system=_QA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text").strip()
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

    resp = _client().messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=_CORE_INFO_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text").strip()
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
