"""Admin-editable, versioned RAG configuration.

Every setting that used to be a constant or env var (top-k, memory turns, generation model,
temperature, prompt, chunking, embedding model, ...) lives in one config dict. Saving never edits a
row - it inserts a new RagConfigVersion and marks it active - so a turn's `config_version` always
identifies the exact settings (including the full prompt) that produced its answer.

Settings split into two kinds:
  * LIVE - take effect on the next request.
  * REINDEX - chunking_* and embedding_model change how leaflets are split and embedded, so they only
    take effect after an explicit re-index (see ingest.reindex_all). Until then retrieval keeps using
    the index as it was built (see VectorStore - queries are embedded with the INDEX's own model).
"""
import threading
import time
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import RagConfigVersion
from app.db.session import SessionLocal
from app.rag.prompts import DEFAULT_SYSTEM_PROMPT, REQUIRED_PLACEHOLDERS
from app.rag.scope_guard import FALLBACK_TEXT

settings = get_settings()

GENERATION_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "gpt-4.1-nano"]
EMBEDDING_MODELS = {  # name -> vector dimension
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
}
CHUNKING_STRATEGIES = {
    "by_section": "Split at the leaflet's section headers (falls back to a sliding window if none are found). Chunk size/overlap are ignored.",
    "by_section_max_size": "Split at section headers, then split any section longer than the chunk size.",
    "sliding_window": "Ignore headers; cut fixed-size overlapping windows of the whole text.",
}

# Settings that need a re-index to take effect.
REINDEX_KEYS = ("chunking_strategy", "chunk_size_chars", "chunk_overlap_chars", "embedding_model")

DEFAULT_CONFIG: dict = {
    "top_k": settings.retrieval_top_k,
    "core_info_top_k": 8,
    "history_turns": 4,
    "generation_model": settings.openai_generation_model,
    "temperature": 0.0,
    "max_tokens": 300,
    "core_info_max_tokens": 1024,
    "fallback_text": FALLBACK_TEXT,
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "chunking_strategy": "by_section",
    "chunk_size_chars": settings.chunk_size_chars,
    "chunk_overlap_chars": settings.chunk_overlap_chars,
    "embedding_model": settings.openai_embedding_model,
}

# name -> UI/validation metadata. `group` drives the sections of the admin Settings tab.
FIELDS: dict[str, dict] = {
    "top_k": {"type": "int", "min": 1, "max": 20, "group": "Retrieval",
              "help": "How many leaflet chunks are given to the model for each question."},
    "core_info_top_k": {"type": "int", "min": 1, "max": 30, "group": "Retrieval",
                        "help": "Chunks used to build the 'Tell me about this medicine' summary."},
    "history_turns": {"type": "int", "min": 0, "max": 10, "group": "Retrieval",
                      "help": "How many previous turns of the conversation the model sees (0 = none)."},
    "generation_model": {"type": "choice", "choices": GENERATION_MODELS, "group": "Generation",
                         "help": "The model that writes the answer."},
    "temperature": {"type": "float", "min": 0.0, "max": 1.0, "group": "Generation",
                    "help": "0 = most repeatable. Raise only if you accept answers varying between participants."},
    "max_tokens": {"type": "int", "min": 50, "max": 1000, "group": "Generation",
                   "help": "Upper limit on the length of an answer."},
    "core_info_max_tokens": {"type": "int", "min": 200, "max": 3000, "group": "Generation",
                             "help": "Upper limit for the 'Tell me about this medicine' summary."},
    "fallback_text": {"type": "text", "max_len": 300, "group": "Generation",
                      "help": "The exact sentence shown when a question is out of scope. A turn counts as 'deflected' when its answer equals this."},
    "system_prompt": {"type": "prompt", "max_len": 40000, "group": "Prompt",
                      "help": "The instructions that define scope and behaviour. Must contain {product_display_name} and {fallback_text}."},
    "chunking_strategy": {"type": "choice", "choices": list(CHUNKING_STRATEGIES), "group": "Chunking & embedding",
                          "reindex": True, "help": "How a leaflet is cut into retrievable chunks."},
    "chunk_size_chars": {"type": "int", "min": 200, "max": 6000, "group": "Chunking & embedding", "reindex": True,
                         "help": "Max chunk length in characters (used by 'by_section_max_size' and 'sliding_window')."},
    "chunk_overlap_chars": {"type": "int", "min": 0, "max": 2000, "group": "Chunking & embedding", "reindex": True,
                            "help": "Characters shared between neighbouring chunks (must be smaller than the chunk size)."},
    "embedding_model": {"type": "choice", "choices": list(EMBEDDING_MODELS), "group": "Chunking & embedding",
                        "reindex": True, "help": "The model that turns text into vectors for search."},
}


class ConfigError(ValueError):
    """Raised with a message safe to show the admin."""


def validate_config(cfg: dict) -> dict:
    """Return a cleaned, fully-populated config or raise ConfigError. Unknown keys are rejected so a
    typo can't silently do nothing."""
    unknown = set(cfg) - set(FIELDS)
    if unknown:
        raise ConfigError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
    out = {}
    for key, meta in FIELDS.items():
        value = cfg.get(key, DEFAULT_CONFIG[key])
        t = meta["type"]
        try:
            if t == "int":
                if isinstance(value, bool) or int(value) != float(value):
                    raise ValueError
                value = int(value)
            elif t == "float":
                value = float(value)
        except (TypeError, ValueError):
            raise ConfigError(f"'{key}' must be a number")
        if t in ("int", "float") and not (meta["min"] <= value <= meta["max"]):
            raise ConfigError(f"'{key}' must be between {meta['min']} and {meta['max']}")
        if t == "choice" and value not in meta["choices"]:
            raise ConfigError(f"'{key}' must be one of: {', '.join(meta['choices'])}")
        if t in ("text", "prompt"):
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"'{key}' cannot be empty")
            if len(value) > meta["max_len"]:
                raise ConfigError(f"'{key}' is too long (max {meta['max_len']} characters)")
            if t == "text":
                value = value.strip()
        out[key] = value
    missing = [p for p in REQUIRED_PLACEHOLDERS if p not in out["system_prompt"]]
    if missing:
        raise ConfigError(f"The system prompt must contain {' and '.join(missing)} (they are filled in per product)")
    if out["chunk_overlap_chars"] >= out["chunk_size_chars"]:
        raise ConfigError("'chunk_overlap_chars' must be smaller than 'chunk_size_chars'")
    return out


@dataclass(frozen=True)
class ActiveConfig:
    version: int
    config: dict

    def __getitem__(self, key: str):
        return self.config[key]


_cache_lock = threading.Lock()
_cache: tuple[float, ActiveConfig] | None = None
_CACHE_TTL_SECONDS = 5.0


def invalidate_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


def ensure_initial_version(db: Session) -> None:
    """Seed version 1 from the built-in defaults on a database that has none, so deploying this
    feature changes no behaviour. Idempotent."""
    if db.query(RagConfigVersion).count() > 0:
        return
    db.add(RagConfigVersion(version=1, config=validate_config({}), note="Initial version (built-in defaults)",
                            created_by="system", is_active=True))
    db.commit()


def _load_active(db: Session) -> ActiveConfig:
    row = db.query(RagConfigVersion).filter(RagConfigVersion.is_active == True).first()  # noqa: E712
    if row is None:
        ensure_initial_version(db)
        row = db.query(RagConfigVersion).filter(RagConfigVersion.is_active == True).first()  # noqa: E712
    # Re-validate so a version saved by an older build still gets any newly-added setting's default.
    return ActiveConfig(version=row.version, config=validate_config(row.config))


def get_active_config(db: Session | None = None) -> ActiveConfig:
    """The active configuration, cached ~5s so each request doesn't hit the DB. Call once per
    request and pass the result down - one request must see one consistent version."""
    global _cache
    now = time.monotonic()
    with _cache_lock:
        if _cache and now - _cache[0] < _CACHE_TTL_SECONDS:
            return _cache[1]
    own = db is None
    session = SessionLocal() if own else db
    try:
        active = _load_active(session)
    finally:
        if own:
            session.close()
    with _cache_lock:
        _cache = (now, active)
    return active


def merged(base: dict, overrides: dict | None) -> dict:
    return validate_config({**base, **(overrides or {})})


def save_version(db: Session, overrides: dict, note: str, created_by: str) -> RagConfigVersion:
    """Validate (active config + overrides) and insert it as the new active version. A no-op change
    is rejected so the history only contains real changes."""
    current = get_active_config(db)
    new_cfg = merged(current.config, overrides)
    if new_cfg == current.config:
        raise ConfigError("No changes to save")
    next_version = (db.query(func.max(RagConfigVersion.version)).scalar() or 0) + 1
    db.query(RagConfigVersion).filter(RagConfigVersion.is_active == True).update({"is_active": False})  # noqa: E712
    row = RagConfigVersion(version=next_version, config=new_cfg, note=(note or "").strip()[:500],
                           created_by=created_by, is_active=True)
    db.add(row)
    db.commit()
    invalidate_cache()
    return row


def activate_version(db: Session, version: int) -> RagConfigVersion:
    row = db.query(RagConfigVersion).filter(RagConfigVersion.version == version).first()
    if row is None:
        raise ConfigError(f"Version {version} does not exist")
    db.query(RagConfigVersion).filter(RagConfigVersion.is_active == True).update({"is_active": False})  # noqa: E712
    row.is_active = True
    db.commit()
    invalidate_cache()
    return row


def reindex_keys_changed(a: dict, b: dict) -> list[str]:
    return [k for k in REINDEX_KEYS if a.get(k) != b.get(k)]
