import io

from fastapi import APIRouter, UploadFile
from fastapi.responses import StreamingResponse
from openai import OpenAI

from app.config import get_settings
from app.schemas import STTResponse, TTSRequest

router = APIRouter(prefix="/api", tags=["voice"])
settings = get_settings()
_client: OpenAI | None = None


def _openai() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(audio: UploadFile) -> STTResponse:
    """Proxies audio to Whisper. Kept server-side (not called from the browser directly) so the
    same endpoint can be reused by a future native Android client without duplicating STT logic
    or embedding API keys client-side."""
    audio_bytes = await audio.read()
    file_tuple = (audio.filename or "audio.webm", audio_bytes, audio.content_type or "audio/webm")
    transcript = _openai().audio.transcriptions.create(model=settings.openai_stt_model, file=file_tuple)
    return STTResponse(transcript=transcript.text)


@router.post("/tts")
def text_to_speech(req: TTSRequest) -> StreamingResponse:
    """Proxies text to OpenAI TTS and streams back audio. Same rationale as /stt: keeps voice
    generation platform-agnostic and server-controlled rather than relying on inconsistent
    browser-native speech synthesis."""
    response = _openai().audio.speech.create(
        model=settings.openai_tts_model,
        voice=settings.openai_tts_voice,
        input=req.text,
    )
    audio_bytes = response.read()
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")
