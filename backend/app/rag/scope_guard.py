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
MIN_RETRIEVAL_SCORE = 0.25

# Heuristic pre-filter: patterns strongly associated with personal health advice, individual
# drug interactions, diagnosis, or dosage-adjustment requests - all explicitly out of scope per
# the study protocol regardless of what the corpus happens to retrieve. This is a cheap, fast
# first gate; the LLM classifier below is the second, more nuanced gate.
_OUT_OF_SCOPE_PATTERNS = [
    r"\bshould i take\b.*\b(mine|my own|given|since i|while i|with my)\b",
    r"\bcan i take\b.*\b(with|and)\b.*\b(my|another|other|alcohol|ibuprofen|aspirin|medication|medicine|drug|prescription)\b",
    r"\bis it safe for me\b",
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

The test is simple: could this question be answered directly from a standard printed medicine leaflet, without knowing anything about the specific individual asking? If yes, it's in scope, even if it's phrased with "I"/"me"/"my" or sounds conversational. Only classify false when answering it truly requires knowing something about THIS particular person - their other medications, their medical history, their body, their symptoms.

IN SCOPE (classify true) - all standard leaflet content, including generic questions about who can take it or how:
- what the medicine is used for
- dose, frequency, max dose, "how much should I take", "how often can I take it"
- who can take it in general terms: "can children take this", "what age is this suitable for" (leaflets always state an age range - this is standard label content, NOT personal advice, even though it sounds like it's asking about a specific child)
- route/form questions: "is it ok to crush the tablet", "what form does this come in", "can I take it with food" (food/water/general timing, NOT a question about another named medication)
- how quickly it works, how long you can take it for
- printed warnings and standard side effects (e.g. "may cause X in some people", "stop use if you notice Y")
- storage, expiry, and missed-dose guidance if covered by the leaflet
- general alcohol guidance if it's standard label text (e.g. "what does the label say about alcohol")

OUT OF SCOPE (classify false) - only when it requires knowing about the specific individual:
- "should I take this GIVEN my [condition/other medication/situation]" - i.e. the question names a specific personal circumstance
- interactions with a NAMED other medication the person says they are taking ("can I take this with ibuprofen I already took")
- diagnosis or interpretation of the participant's own symptoms ("what does it mean that I feel X")
- dosage adjustment for a specific person's condition ("I have kidney disease, can I take this")
- anything genuinely not answerable from a standard consumer leaflet (unrelated topics, other unlisted medicines)

Examples:
- "can children take this" -> true (generic leaflet age guidance)
- "I have a 5 year old with a fever, what dose does she need" -> false (personalized to a specific child)
- "can I take it with food" -> true (generic timing/food guidance)
- "can I take it with my blood pressure medication" -> false (named personal medication)
- "how much should I take" -> true (standard dosage question)
- "should I take more since one didn't work for me" -> false (personal circumstance)
- "I took a dose an hour ago, when can I take the next one?" -> true (this is just the standard dosing-interval question, phrased with "I took" - it names no personal risk factor, condition, or other medication, so it's answerable purely from the label's frequency guidance)

Classify the participant's question. Respond with ONLY a JSON object: {"in_scope": true or false}. No other text."""


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def llm_classify_in_scope(query_text: str) -> bool:
    resp = _client().chat.completions.create(
        model=settings.openai_generation_model,
        max_tokens=50,
        temperature=0,
        seed=0,
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
_GREETING_RE = re.compile(r"^\s*(hi|hello|hey|hiya)( there| guys)?[\s,!.?]*$|^\s*good (morning|afternoon|evening)[\s,!.?]*$", re.IGNORECASE)
_FAREWELL_RE = re.compile(
    r"^\s*(bye( bye)?|goodbye|good bye|see you( later)?|that'?s all([, ]*thanks)?|i'?m done)[\s!.?]*$", re.IGNORECASE
)
_THANKS_RE = re.compile(r"^\s*(thanks?( you)?( so much)?|ok(ay)?|great|cool|alright|got it|sounds good)[\s!.?]*$", re.IGNORECASE)
# Meta-questions about the system's own capability/scope ("what medicine can you help me with",
# "what can you help with", "what kind of medicine do you know about") are questions ABOUT the
# assistant, not medical questions - retrieval will never find a grounded chunk for them (there's
# no leaflet section titled "what am I"), so they were falling through the retrieval gate and
# triggering the fixed pharmacist-deflection text. That's wrong: this is a legitimate, answerable
# capability question, and it should be answered by naming the actual product in the session.
_CAPABILITY_RE = re.compile(
    r"\bwhat (kind of |type of )?(medicine|medication|drug|product)s? (can|could|do) you (help( me)?( with)?|know( about)?|answer)\b"
    r"|\bwhat (kind of |type of )?(medicine|medication|drug|product)s? you can (help|answer)\b"
    r"|\bwhat can you help (me )?with\b"
    r"|\bwhat (do you|can you) know\b"
    r"|\bwhat (are you|is this) (for|able to (do|help with))\b",
    re.IGNORECASE,
)

_CONVERSATIONAL_REPLIES: list[tuple[re.Pattern, str]] = [
    (_CHECKIN_RE, "Yes, I can hear you. Please go ahead and ask your question about this medicine."),
    (_HOW_ARE_YOU_RE, "I'm doing well, thank you for asking! How can I help you with this medicine?"),
    (_GREETING_RE, "Hello! I'm here to help you understand this medicine. What would you like to know?"),
    (_FAREWELL_RE, "Goodbye! Take care, and don't hesitate to ask if you have more questions."),
    (_THANKS_RE, "You're welcome! Let me know if you have any other questions about this medicine."),
]


def conversational_reply(query_text: str, product_display_name: str | None = None) -> str | None:
    """Short-circuits small talk (greetings, farewells, 'can you hear me' checks) and capability
    meta-questions with a natural reply instead of running it through medical scope classification.
    These aren't medical questions at all, so the fixed pharmacist-deflection text was firing on
    completely benign utterances like "bye bye" or "what medicine can you help me with" - correct
    per the letter of the scope rules, but broken as a live conversation. Checked before
    retrieval/classification, not after, so it costs nothing extra and can never be overridden by
    a bad LLM classification or an empty retrieval result."""
    text = query_text.strip()
    if _CAPABILITY_RE.search(text):
        product = product_display_name or "this medicine"
        return (
            f"I can help you with questions about {product} - what it's used for, how to take it, "
            "dosage, and warnings from the packaging. What would you like to know?"
        )
    for pattern, reply in _CONVERSATIONAL_REPLIES:
        if pattern.search(text):
            return reply
    return None


_LEADING_GREETING_RE = re.compile(r"^\s*(hi|hello|hey|hiya)[\s,!.]*", re.IGNORECASE)


def is_in_scope(query_text: str, chunks: list[dict]) -> bool:
    """Three gates, all must pass: retrieval found something grounded, the heuristic pattern
    filter doesn't flag it, and the LLM classifier agrees. Any single failure deflects.

    A leading "hi"/"hey" is stripped before classification only - a greeting tacked onto a real
    question ("hi, how much can I take") was measurably flipping the classifier between runs on
    the identical input, because the greeting made the utterance read as ambiguous small-talk to
    the model. The greeting carries no scope-relevant meaning, so removing it removes the
    ambiguity without changing what's actually being asked."""
    if not retrieval_gate_passes(chunks):
        return False
    if heuristic_out_of_scope(query_text):
        return False
    classify_text = _LEADING_GREETING_RE.sub("", query_text).strip() or query_text
    return llm_classify_in_scope(classify_text)
