# frontend-vr — VR Pepper (Meta Quest 2, Unity)

A third delivery condition for the OTC medication-guidance study: a **virtual Pepper robot in a
virtual pharmacy**, running on a Meta Quest 2. It sits alongside the other two conditions in this
repo and must stay in **research parity** with them:

- `frontend-pepper/` — physical Pepper robot (Android/QiSDK), embodied condition
- `frontend-app/` — tablet web app "MedCheck" (React/Vite), non-embodied condition
- `frontend-vr/` — this project, virtual embodied condition

All three call the **same backend** (`backend/`, FastAPI + FAISS RAG over medicine leaflets). The
only thing that should differ between conditions is the delivery modality — never the AI, the
retrieval, the scope rules, or the answer content. Read `../docs/ARCHITECTURE.md` before changing
behavior, and mirror the participant flow of `frontend-app/src/screens/` and
`frontend-pepper/app/src/main/java/com/otc/pepper/`.

## Stack

- Unity **6000.3.27f1** (Unity 6.3 LTS), URP, build target **Android**
- Meta XR SDK from Meta's scoped registry (`https://npm.developer.oculus.com`):
  `com.meta.xr.sdk.core` and `com.meta.xr.sdk.interaction.ovr` at 207.0.1.
  The **Meta XR Simulator** ships inside Core and is used for testing in the editor without a headset.
- `com.unity.nuget.newtonsoft-json` for backend JSON
- Developed on an Apple Silicon Mac — Quest Link is unavailable, so test in the editor with the
  Meta XR Simulator and periodically build to the headset.

## Backend API (base URL: `https://otc-h81d.onrender.com`)

Reference client: `frontend-app/src/lib/api.ts`. Request schemas: `backend/app/schemas.py`.

| Call | Purpose |
|---|---|
| `GET /api/products` | Medicines available in the study |
| `POST /api/session/start` `{platform, product_slug, device_info:{user_agent, screen_width, screen_height}}` | Start a participant session |
| `POST /api/core-info?session_id=…` | Core product info delivered at the start |
| `POST /api/query/stream` `{session_id, query_text, input_method}` | Streaming answer as NDJSON: `{"delta": "..."}` lines, then a final `{"done": true, ...}` line |
| `POST /api/stt` (multipart field `audio`) | Speech-to-text → `{transcript}` |
| `POST /api/tts` `{text}` | Text-to-speech audio bytes |
| `POST /api/session/{id}/end` `{errors_logged}` | End the session |

`input_method` is `"voice"` or `"typed"` (`"system"` is reserved for auto-triggered core info).
Speak answers **sentence by sentence as they stream** (same as the other two clients), not after
the whole answer arrives.

The backend is on Render's free tier and sleeps when idle — expect a slow first request and
retry transient failures (as `frontend-app` does for the product list).

## Backend additions for VR (all optional / backward compatible)

- `platform = "vr_quest"` → `condition = "vr_pepper"` (`schemas.py`, `routes/sessions.py`).
- `QueryRequest.response_language` and `/api/core-info?language=` — reply language. Out-of-scope
  replies keep the English fallback first, then the translation, and `generate.is_fallback()` still
  logs them as out of scope.
- `/api/query/stream` final line has `sources` (leaflet section labels the answer used).
- `TTSRequest.slow` — slower delivery (sent via `extra_body` for the older openai SDK).

These must be deployed (push to `main` → Render) before the headset build can start sessions; until
then the Editor uses a local backend on port 8001 (`OtcSettings.useLocalBackendInEditor`).

## Runtime code (Assets/OTC/Scripts, namespace Otc.VR)

- `OtcExperience` — study flow (setup → tutorial → core info → Q&A → closing), captions, sources,
  settings, safety and pharmacist panels, product switching. `OtcSettings.studyParityMode` turns the
  VR-only extras off (English only, no spoken safety prompt, no product switching).
- `OtcApi` (backend client, NDJSON streaming), `MicRecorder` (WAV + silence auto-stop),
  `SpeechPlayer` (sentence-by-sentence TTS while the answer streams), `SafetyCheck` (red flags,
  Australian numbers).
- `PepperRig` (joints by NAOqi name/radians, self-calibrating axis mapping), `PepperBehaviour`
  (eye contact, gestures, idle motion, LED states).
- `HandInteractor` (controllers or hands: ray select, poke, grab), `Grabbable`, `ProductTray`,
  `VRButton`/`Ui` (world-space UI from quads + TextMeshPro).
- Scene wiring is done by `Assets/OTC/Editor/OtcRuntimeSetup.cs` from `PharmacySceneBuilder`.

## Quest 2 constraints

- Mobile GPU: target a steady 72 fps. Keep the Pepper model and environment low-poly, avoid
  real-time shadows and heavy post-processing.
- Participants are **seated** — no locomotion; put Pepper and UI within comfortable reach/view.
- Microphone needs the Android `RECORD_AUDIO` permission requested at runtime.
- Pepper has no mouth: show "speaking" with eye/chest light and gestures, not lip-sync.

## Working in this project

- Claude edits C# and config files; the Unity Editor must reimport to pick up changes. Scene and
  prefab setup is done in the Editor (or via Editor scripts).
- Headless commands (Unity must not have this project open at the same time):
  - Open/refresh: `"/Applications/Unity/Hub/Editor/6000.3.27f1/Unity.app/Contents/MacOS/Unity" -batchmode -quit -projectPath . -logFile -`
  - Compile errors show as `error CS` in the log.
- `Library/`, `Temp/`, `Logs/`, `UserSettings/` and generated `.csproj`/`.slnx` files are not
  committed. Binary assets (models, textures, audio) go through Git LFS (see `.gitattributes`).
- Never put API keys in this app — all AI calls go through the backend.
