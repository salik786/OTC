import json
import re

from openai import OpenAI

from app.config import get_settings

settings = get_settings()
_openai_client: OpenAI | None = None

# Word-for-word fixed fallback text. Must never be paraphrased - this is a study parity
# requirement (identical wording across Pepper and tablet, every time it fires).
FALLBACK_TEXT = "That is outside what I can help with. Please speak to a pharmacist or your doctor."

# Minimum cosine similarity (normalized inner product) for a retrieved chunk to count as
# "grounded" support for the query. Below this, we deflect without even calling the generator -
# there's nothing in the corpus worth answering from.
MIN_RETRIEVAL_SCORE = 0.28

# Heuristic pre-filter: patterns strongly associated with personal health advice, individual
# drug interactions, diagnosis, or dosage-adjustment requests - all explicitly out of scope per
# the study protocol regardless of what the corpus happens to retrieve. This is a cheap, fast
# first gate; the LLM classifier below is the second, more nuanced gate.
_OUT_OF_SCOPE_PATTERNS = [
    r"\bshould i take\b", r"\bcan i take\b.*\b(with|and)\b", r"\bis it safe for me\b",
    r"\bmy (doctor|condition|prescription|medication|allergy|allergies)\b",
    r"\bi (have|am|feel|felt|am currently taking|am on)\b", r"\bi('m| am) taking\b", r"\bi took\b.*\b(before|already|earlier|this morning|today)\b",
    r"\bam i\b", r"\bwill it (hurt|harm|affect) me\b",
    r"\binteract(s|ion)? with\b", r"\bmix(ing)? with\b",
    r"\bpregnan(t|cy)\b", r"\bbreastfeed(ing)?\b",
    r"\boverdose(d)?\b.*\bme\b",
    r"\bdiagnos(e|is|ed)\b", r"\bsymptom(s)? (mean|indicate)\b",
]
_OUT_OF_SCOPE_RE = re.compile("|".join(_OUT_OF_SCOPE_PATTERNS), re.IGNORECASE)


def _client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def heuristic_out_of_scope(query_text: str) -> bool:
    return bool(_OUT_OF_SCOPE_RE.search(query_text))


def retrieval_gate_passes(chunks: list[dict]) -> bool:
    return bool(chunks) and chunks[0]["score"] >= MIN_RETRIEVAL_SCORE


_CLASSIFY_SYSTEM_PROMPT = """You are a strict scope classifier for an OTC medicine information kiosk used in a research study. This is a factual, deterministic classification task - always give the same answer to the same question.

IN SCOPE (always classify true): what the medicine is used for; standard dose/frequency/max dose; warnings printed on the approved leaflet, INCLUDING standard printed side-effect information (e.g. "may cause X in some people", "stop use if you notice Y") since these are safety warnings from the label, not personalized advice; expiry guidance; missed-dose guidance if it is on the label; standard storage instructions.

OUT OF SCOPE (always classify false): personal health advice ("should I take this given my situation"), drug-drug interactions specific to the individual, diagnosis or interpretation of the participant's own symptoms ("what does it mean that I feel X"), dosage adjustment for a specific person's condition, or anything not answerable from a standard consumer leaflet.

Classify the participant's question. Respond with ONLY a JSON object: {"in_scope": true or false}. No other text."""


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def llm_classify_in_scope(query_text: str) -> bool:
    resp = _client().chat.completions.create(
        model=settings.openai_generation_model,
        max_tokens=50,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": query_text},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    raw = _FENCE_RE.sub("", raw).strip()
    try:
        return bool(json.loads(raw)["in_scope"])
    except (json.JSONDecodeError, KeyError, TypeError):
        # Fail closed: if we can't parse the classifier's answer, treat as out of scope.
        return False


_CHECKIN_RE = re.compile(r"\b(can you hear me|are you (there|listening)|anyone (there|listening))\b", re.IGNORECASE)
# Unanchored (not whole-utterance) because these phrases never legitimately appear inside a real
# medical question, unlike "hi"/"hello" alone which must stay strictly anchored below - otherwise
# "hi, what's the max dose" would get hijacked into a pure greeting reply and the real question
# would silently go unanswered.
_HOW_ARE_YOU_RE = re.compile(r"\bhow(’|'| i)?s? (are )?you( doing| going)?\b|\bhow'?s it going\b|\bwhat'?s up\b", re.IGNORECASE)
_GREETING_RE = re.compile(r"^\s*(hi|hello|hey|good (morning|afternoon|evening))[\s,!.?]*$", re.IGNORECASE)
_FAREWELL_RE = re.compile(
    r"^\s*(bye( bye)?|goodbye|good bye|see you( later)?|that'?s all([, ]*thanks)?|i'?m done)[\s!.?]*$", re.IGNORECASE
)
_THANKS_RE = re.compile(r"^\s*(thanks?( you)?( so much)?|ok(ay)?|great|cool|alright|got it|sounds good)[\s!.?]*$", re.IGNORECASE)

_CONVERSATIONAL_REPLIES: list[tuple[re.Pattern, str]] = [
    (_CHECKIN_RE, "Yes, I can hear you. Please go ahead and ask your question about this medicine."),
    (_HOW_ARE_YOU_RE, "I'm doing well, thank you for asking! How can I help you with this medicine?"),
    (_GREETING_RE, "Hello! I'm here to help you understand this medicine. What would you like to know?"),
    (_FAREWELL_RE, "Goodbye! Take care, and don't hesitate to ask if you have more questions."),
    (_THANKS_RE, "You're welcome! Let me know if you have any other questions about this medicine."),
]


def conversational_reply(query_text: str) -> str | None:
    """Short-circuits small talk (greetings, farewells, 'can you hear me' checks) with a natural
    reply instead of running it through medical scope classification. These aren't medical
    questions at all, so the fixed pharmacist-deflection text was firing on completely benign
    utterances like "bye bye" or "can you hear me" - correct per the letter of the scope rules,
    but broken as a live voice conversation. Checked before retrieval/classification, not after,
    so it costs nothing extra and can never be overridden by a bad LLM classification."""
    text = query_text.strip()
    for pattern, reply in _CONVERSATIONAL_REPLIES:
        if pattern.search(text):
            return reply
    return None


def is_in_scope(query_text: str, chunks: list[dict]) -> bool:
    """Three gates, all must pass: retrieval found something grounded, the heuristic pattern
    filter doesn't flag it, and the LLM classifier agrees. Any single failure deflects."""
    if not retrieval_gate_passes(chunks):
        return False
    if heuristic_out_of_scope(query_text):
        return False
    return llm_classify_in_scope(query_text)
