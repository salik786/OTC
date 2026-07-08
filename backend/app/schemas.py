from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["tablet_web", "mobile_web", "desktop_web", "android_native", "pepper"]
InputMethod = Literal["voice", "typed", "system"]  # "system" = auto-triggered core-info delivery, not participant input


class DeviceInfo(BaseModel):
    user_agent: str
    screen_width: int
    screen_height: int


class SessionStartRequest(BaseModel):
    platform: Platform
    product_slug: str
    device_info: DeviceInfo
    participant_id: str | None = None  # if omitted, backend assigns a non-PII id


class SessionStartResponse(BaseModel):
    session_id: str
    participant_id: str
    platform: Platform
    condition: str
    product_slug: str
    product_display_name: str
    start_time: datetime


class SessionEndRequest(BaseModel):
    errors_logged: int = 0


class SessionEndResponse(BaseModel):
    session_id: str
    end_time: datetime
    total_turns: int


class QueryRequest(BaseModel):
    session_id: str
    query_text: str
    input_method: InputMethod


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    section_label: str | None = None
    score: float


class QueryResponse(BaseModel):
    answer_text: str
    in_scope: bool
    retrieved_chunks: list[RetrievedChunk]
    latency_ms: float
    turn_number: int


class CoreInfoResponse(BaseModel):
    """Structured payload for screen 3 (core info delivery). Populated from RAG, never hardcoded
    client-side. Fields are None if the leaflet didn't yield that field."""

    product_name: str
    used_for: str | None
    dose: str | None
    frequency: str | None
    max_dose_24h: str | None
    warnings: list[str]
    full_text: str  # the spoken/read narrative, same generation path as /api/query
    latency_ms: float


class TTSRequest(BaseModel):
    text: str


class STTResponse(BaseModel):
    transcript: str


# ---- Admin schemas ----


class ProductOut(BaseModel):
    id: str
    slug: str
    display_name: str


class DocumentOut(BaseModel):
    id: str
    product_id: str
    product_slug: str
    filename: str
    uploaded_at: datetime
    chunk_count: int
    active: bool


class TestRetrievalRequest(BaseModel):
    query: str
    product_slug: str
    top_k: int = 5


class TestRetrievalResponse(BaseModel):
    retrieved_chunks: list[RetrievedChunk]
    latency_ms: float


class SessionSummaryOut(BaseModel):
    session_id: str
    participant_id: str
    platform: Platform
    condition: str
    product_slug: str
    start_time: datetime
    end_time: datetime | None
    total_turns: int
    errors_logged: int
