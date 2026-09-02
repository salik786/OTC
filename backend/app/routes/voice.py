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
    """Proxies audio to OpenAI's transcription API (gpt-4o-mini-transcribe by default - faster
    than whisper-1 for short kiosk utterances). Kept server-side (not called from the browser
    directly) so the same endpoint can be reused by a future native Android client without
    duplicating STT logic or embedding API keys client-side."""
    audio_bytes = await audio.read()
    file_tuple = (audio.filename or "audio.webm", audio_bytes, audio.content_type or "audio/webm")
    transcript = _openai().audio.transcriptions.create(model=settings.openai_stt_model, file=file_tuple)
    return STTResponse(transcript=transcript.text)


@router.post("/tts")
def text_to_speech(req: TTSRequest) -> StreamingResponse:
    """Proxies text to OpenAI TTS and relays audio chunks as OpenAI sends them. Previously this
    called response.read() first, which fully buffers the entire clip in memory before this
    endpoint sends a single byte to the browser - despite the docstring already claiming to
    stream, it was fully serial (OpenAI generates the whole clip -> we finish downloading it ->
    only then does the browser start receiving anything). Genuinely relaying chunks as they
    arrive lets that download overlap with OpenAI's own generation instead of happening
    strictly after it."""
    def relay():
        with _openai().audio.speech.with_streaming_response.create(
            model=settings.openai_tts_model,
            voice=settings.openai_tts_voice,
            input=req.text,
        ) as response:
            for chunk in response.iter_bytes(chunk_size=4096):
                yield chunk

    return StreamingResponse(relay(), media_type="audio/mpeg")
