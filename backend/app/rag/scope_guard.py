import json
import re

from anthropic import Anthropic

from app.config import get_settings

settings = get_settings()
_anthropic_client: Anthropic | None = None

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


def _client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


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
    resp = _client().messages.create(
        model=settings.anthropic_model,
        max_tokens=50,
        system=_CLASSIFY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": query_text}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text").strip()
    raw = _FENCE_RE.sub("", raw).strip()
    try:
        return bool(json.loads(raw)["in_scope"])
    except (json.JSONDecodeError, KeyError, TypeError):
        # Fail closed: if we can't parse the classifier's answer, treat as out of scope.
        return False


def is_in_scope(query_text: str, chunks: list[dict]) -> bool:
    """Three gates, all must pass: retrieval found something grounded, the heuristic pattern
    filter doesn't flag it, and the LLM classifier agrees. Any single failure deflects."""
    if not retrieval_gate_passes(chunks):
        return False
    if heuristic_out_of_scope(query_text):
        return False
    return llm_classify_in_scope(query_text)
