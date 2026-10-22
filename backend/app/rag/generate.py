import json
import re

from openai import OpenAI

from app.config import get_settings
from app.rag.config_store import ActiveConfig, get_active_config
from app.rag.prompts import render_system_prompt

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


def _c(cfg) -> dict:
    """Accept an ActiveConfig, a plain config dict, or None (= the active config)."""
    if cfg is None:
        return get_active_config().config
    return cfg.config if isinstance(cfg, ActiveConfig) else cfg


def _qa_system_prompt(product_display_name: str, cfg: dict) -> str:
    return render_system_prompt(cfg["system_prompt"], product_display_name, cfg["fallback_text"])


def _language_instruction(language: str, fallback_text: str) -> str:
    # The fixed deflection stays in English first so in_scope logging (which matches it) still
    # works; the translation follows on the next line for the participant.
    return (
        f"Reply in {language}. If the question is out of scope, reply with exactly this English "
        f"sentence: \"{fallback_text}\" followed on a new line by the same sentence in {language}."
    )


def is_fallback(answer_text: str, fallback_text: str, language: str | None = None) -> bool:
    """True when the answer is the fixed deflection (possibly followed by its translation)."""
    answer_text = answer_text.strip()
    return answer_text.startswith(fallback_text) if language else answer_text == fallback_text


def _build_qa_messages(
    query_text: str, chunks: list[dict], product_display_name: str, history: list[dict] | None, cfg: dict,
    language: str | None = None,
) -> list[dict]:
    excerpts = (
        "\n\n".join(f"[{c['section_label'] or 'Leaflet excerpt'}]\n{c['text']}" for c in chunks)
        if chunks
        else "(no leaflet excerpts were retrieved for this query)"
    )
    user_content = f"Leaflet excerpts:\n\n{excerpts}\n\nParticipant's newest message: {query_text}"
    if language:
        # Repeated here as well as in the system message: the main prompt is English-centric, and an
        # instruction next to the question is followed far more reliably.
        user_content += f"\n\n(Write your reply in {language}.)"

    # Prior turns go in as real user/assistant messages (not flattened into one text block) so
    # the model resolves follow-ups ("what do you mean by that") the way it was actually trained
    # to use conversation context, rather than parsing a narrated transcript out of a single turn.
    messages: list[dict] = [{"role": "system", "content": _qa_system_prompt(product_display_name, cfg)}]
    if language:
        messages.append({"role": "system", "content": _language_instruction(language, cfg["fallback_text"])})
    for turn in history or []:
        messages.append({"role": "user", "content": turn["query"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    messages.append({"role": "user", "content": user_content})
    return messages


def generate_answer(
    query_text: str, chunks: list[dict], product_display_name: str, history: list[dict] | None = None, cfg=None,
    language: str | None = None,
) -> str:
    c = _c(cfg)
    messages = _build_qa_messages(query_text, chunks, product_display_name, history, c, language)
    resp = _client().chat.completions.create(
        model=c["generation_model"],
        max_tokens=c["max_tokens"],
        temperature=c["temperature"],
        messages=messages,
    )
    text = (resp.choices[0].message.content or "").strip()
    return text or c["fallback_text"]


def generate_answer_stream(
    query_text: str, chunks: list[dict], product_display_name: str, history: list[dict] | None = None, cfg=None,
    language: str | None = None,
):
    """Same call as generate_answer, but yields text deltas as the model produces them instead of
    blocking for the complete response - lets the caller start synthesizing/speaking the first
    sentence while the model is still writing the rest, instead of the full answer's generation
    time sitting entirely in front of the first word spoken."""
    c = _c(cfg)
    messages = _build_qa_messages(query_text, chunks, product_display_name, history, c, language)
    stream = _client().chat.completions.create(
        model=c["generation_model"],
        max_tokens=c["max_tokens"],
        temperature=c["temperature"],
        messages=messages,
        stream=True,
    )
    for event in stream:
        delta = event.choices[0].delta.content if event.choices else None
        if delta:
            yield delta


_CORE_INFO_SYSTEM_PROMPT = """You extract structured OTC medicine information from leaflet excerpts for a research kiosk.

Rules:
1. Use ONLY the leaflet excerpts provided. Never use outside knowledge.
2. Respond with ONLY a JSON object with these exact keys: product_name, used_for, dose, frequency, max_dose_24h, warnings (a list of short warning strings), full_text (a natural 4-6 sentence spoken narrative covering all the above, ending with a prompt to ask a pharmacist if unsure).
3. If a field isn't present in the excerpts, set it to null (or an empty list for warnings).
4. No text outside the JSON object."""


def generate_core_info(product_display_name: str, chunks: list[dict], cfg=None, language: str | None = None) -> dict:
    c = _c(cfg)
    if not chunks:
        return {
            "product_name": product_display_name,
            "used_for": None,
            "dose": None,
            "frequency": None,
            "max_dose_24h": None,
            "warnings": [],
            "full_text": c["fallback_text"],
        }

    excerpts = "\n\n".join(f"[{c['section_label'] or 'Leaflet excerpt'}]\n{c['text']}" for c in chunks)
    user_content = f"Product: {product_display_name}\n\nLeaflet excerpts:\n\n{excerpts}"

    resp = _client().chat.completions.create(
        model=c["generation_model"],
        max_tokens=c["core_info_max_tokens"],
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _CORE_INFO_SYSTEM_PROMPT
             + (f"\n5. Write every text value in {language}; keep the JSON keys in English." if language else "")},
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
            "warnings": [], "full_text": c["fallback_text"],
        }
    data.setdefault("product_name", product_display_name)
    data.setdefault("warnings", [])
    return data
