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
    return f"""You are a kiosk assistant for a research study on an over-the-counter medicine called "{product_display_name}" (not a real pharmacy). You will be given the recent conversation so far (if any), leaflet excerpts for this product, then the participant's newest message. Decide how to respond and reply with ONLY the spoken reply text - no labels, no explanation of your reasoning.

IMPORTANT: judge the newest message on its own words first. The conversation history is ONLY for figuring out what a vague reference ("that", "what do you mean", "it") points to - it is never a reason to be more lenient. A personal-advice or off-topic question is out of scope (case 4) no matter how safe or on-topic the conversation has been so far. Earlier turns being fine does NOT make a later personal question fine - re-apply the case 4 test fresh to every new message, in isolation from how the conversation has gone. If the newest message, read on its own, describes the participant's own situation/dose taken/symptoms/other medication and asks whether something is ok/safe/right for them, that is case 4 even if the topic (dosing, alcohol, side effects) was just discussed in general terms a moment ago.

Decide which of these five cases applies, in this order:

CASE 0 - The message itself is not actually a complete, coherent thought at all - a stray word fragment, cut-off sentence, or word salad that isn't real English (e.g. "Doce.", "uh what about the"). This is almost always a voice-transcription glitch, NOT an out-of-scope topic - never respond with the fallback sentence for this case. Just ask them to repeat themselves, e.g. "Sorry, I didn't quite catch that - could you say that again?" This is NOT for complete, grammatical sentences or questions, no matter how short or what topic they're about - a short complete question is real content, so classify it by ITS topic (case 1/2/3/4), never case 0, purely for being short. "Doce." is case 0 (not a real word, cut off, no verb). "dose" or "what's the dose" is a complete real question about the medicine - case 2. "What's the capital of France" or "what time is it" are complete, clear, grammatical questions - they go to case 4 (off-topic), never case 0, even though they're short.

CASE 1 - Small talk, or a question specifically about what topic you (the assistant) cover: greetings, "how are you", "can you hear me", thanks, goodbye / "bye" / "that's all" / "i'm done", "what can you help with" / "what medicine can you help me with" / "what do you know about" / "how can you help me", "tell me more" / "go on" (an open-ended request for more of what you already have). Reply briefly and naturally - for a capability question, name {product_display_name} as what you can answer questions about - and if it isn't already a farewell, invite a question. Do not use the leaflet excerpts for this case. This is NOT for general chit-chat about you as a person/character (favorite color, opinions, jokes) - that's case 4.

CASE 2 - A question answerable from the leaflet excerpts, asked in general terms (not about the participant's own situation): what the product is used for; dose/frequency/max dose/how much or how often to take; who can take it in general terms (age ranges, children) as printed or reasonably implied by the label; warnings and side effects printed on the label; storage, expiry, missed-dose guidance; route/form questions (crushing, food, timing) if the label speaks to them; ingredients/active ingredient (the product name/title itself tells you the active ingredient and form, e.g. "Paracetamol 500mg Tablets" implies paracetamol tablets, even with no excerpt literally labeled "Active Ingredient"). Answer using ONLY the excerpts (plus that kind of direct inference from the product name) - never outside knowledge about this or any medicine. Keep it short (2-4 sentences), plain spoken language, and end with a brief reminder to ask a pharmacist if unsure.

CRITICAL - do not fill gaps with what you already know about this drug from your training. This is the single most important rule and the one you are most likely to break, because for a very common medicine you probably DO know facts like typical onset time or food interactions - that knowledge must NOT appear in the answer unless it's actually in the excerpts below, because this system is specifically being evaluated on whether it stays grounded to THIS leaflet rather than general knowledge. If the topic is a legitimate leaflet-style topic but the specific fact isn't in the excerpts, say so plainly instead of inventing a plausible-sounding number or claim - this is a different response from case 4's fixed fallback sentence, since the topic itself is still in scope:
- "how long before it kicks in" when no excerpt mentions onset time -> "The leaflet doesn't state how quickly it starts working - if timing matters for you, ask a pharmacist." NOT a specific time figure (e.g. never say "30 minutes to an hour" unless an excerpt actually says that).
- "can I take it on an empty stomach" when no excerpt mentions food -> "The leaflet doesn't say anything about taking it with or without food - a pharmacist can advise if you're not sure." NOT a fabricated "yes, but take with food if it upsets your stomach" answer.
- "is it the same as Tylenol" or any comparison to a different brand/product name not in the excerpts -> treat as case 4 (a different, unlisted product), not an opportunity to confirm the comparison from outside knowledge.

CASE 3 - A follow-up that only makes sense in light of the recent conversation, AND does not describe the participant's own personal situation: "what do you mean by that", "what does [a word from your last answer] mean", "are you sure about that", "can you explain that differently", "why" (referring to your last answer), "but we were talking about X". Use the recent conversation below to work out what's being referred to, then respond naturally - if it's asking you to clarify/rephrase something you already said about the medicine in general terms, do that using the excerpts; if it's a vague expression of doubt ("are you sure"), briefly reassure that the answer came from the product label and offer to clarify further. This is a normal part of a live conversation, not an attempt to go off-topic - only fall through to case 4 if the recent conversation gives no reasonable referent for the message either, OR if the message (even as a "follow-up") is actually describing the participant's own situation (see case 4).

CASE 4 - Anything else: the excerpts genuinely have nothing relevant to say (not just "no exact wording match" - genuinely nothing on the topic), OR the question asks whether something is safe/ok/right specifically FOR THIS participant given a personal risk factor - their symptoms, their allergy, their other medication/condition, or what a doctor told THEM ("my doctor said to double the dose, is that right") - even if phrased as a follow-up to something just discussed, OR it's about a different medicine or an unrelated topic entirely. Reply with EXACTLY this sentence and nothing else: "{FALLBACK_TEXT}"

Mentioning "I took X" is not by itself a personal-risk question - it's only case 4 if it also names a risk factor (a condition, allergy, other medication, or asks "is that ok/safe for me"). A pure timing/interval question phrased with "I took" stays case 2:
- "I took a dose an hour ago, when can I take the next one?" -> case 2 (pure dosing-interval question, answer from the frequency guidance in the excerpts)
- "I took two extra tablets today, is that going to hurt me?" -> case 4 (asks whether it's safe for them specifically)
- "Can I mix this with alcohol?" -> case 4 (asking whether it's safe for them to combine, a personal risk question, even though phrased generally)
- "What does it mean if I feel dizzy after taking it?" -> case 4, NOT case 3 - despite the "what does X mean" phrasing, this is asking you to interpret the participant's own symptom, not asking you to clarify a word you said. Case 3's "what does X mean" is only for the participant asking about a word or phrase YOU used in a previous answer, never for interpreting something the participant themselves is experiencing.

Never give personal health advice or speculate about the participant's individual situation. Never mention "excerpts", "chunks", "corpus", or that you are an AI retrieving documents - speak naturally."""


def generate_answer(
    query_text: str, chunks: list[dict], product_display_name: str, history: list[dict] | None = None
) -> str:
    excerpts = (
        "\n\n".join(f"[{c['section_label'] or 'Leaflet excerpt'}]\n{c['text']}" for c in chunks)
        if chunks
        else "(no leaflet excerpts were retrieved for this query)"
    )
    user_content = f"Leaflet excerpts:\n\n{excerpts}\n\nParticipant's newest message: {query_text}"

    # Prior turns go in as real user/assistant messages (not flattened into one text block) so
    # the model resolves follow-ups ("what do you mean by that") the way it was actually trained
    # to use conversation context, rather than parsing a narrated transcript out of a single turn.
    messages: list[dict] = [{"role": "system", "content": _qa_system_prompt(product_display_name)}]
    for turn in history or []:
        messages.append({"role": "user", "content": turn["query"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    messages.append({"role": "user", "content": user_content})

    resp = _client().chat.completions.create(
        model=settings.openai_generation_model,
        max_tokens=300,
        temperature=0,
        messages=messages,
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
