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
        extra = {}
        instructions = []
        if req.voice:
            # Assistant voices (VR client): a warm, calm pharmacist delivery. Clients that don't pick a
            # voice (tablet, Pepper) keep the default delivery unchanged.
            instructions.append("Speak in a warm, calm, friendly and reassuring tone, like a caring "
                                "pharmacist talking to a customer. Natural pace, gentle and professional.")
        if req.slow:
            instructions.append("Speak slowly and clearly, with short pauses between sentences.")
        if instructions:
            # gpt-4o-mini-tts ignores `speed` but follows delivery instructions (sent via extra_body so it
            # also works with openai SDKs older than the `instructions` kwarg); tts-1 models take `speed`.
            if settings.openai_tts_model.startswith("gpt-4o"):
                extra = {"extra_body": {"instructions": " ".join(instructions)}}
            elif req.slow:
                extra = {"speed": 0.85}
        with _openai().audio.speech.with_streaming_response.create(
            model=settings.openai_tts_model,
            voice=req.voice or settings.openai_tts_voice,
            input=req.text,
            **extra,
        ) as response:
            for chunk in response.iter_bytes(chunk_size=4096):
                yield chunk

    return StreamingResponse(relay(), media_type="audio/mpeg")
