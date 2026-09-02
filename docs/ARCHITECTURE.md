# OTC Medication Guidance — Architecture & Project Reference

This is the technical reference for the project: what it is, how the pieces fit together, the
data model, and what's changed recently. Written so a new engineer (or a future session) can
get oriented without re-reading the whole git history.

## What this project is

A research study comparing two ways of delivering **OTC (over-the-counter) medication guidance**
to people:

- **Condition A — embodied robot:** a **Pepper** social robot giving verbal guidance
  (`frontend-pepper`, native Android/QiSDK).
- **Condition B — non-embodied tablet:** the same guidance through a tablet-based AI agent
  (`frontend-app`, React/Vite, branded "MedCheck").

Both conditions call the **same backend and the same RAG pipeline** over the same leaflet
content, so the only thing that differs between the two study arms is the delivery modality
(robot vs. screen) — not the underlying AI, the retrieval, or the answer content. This parity is
why `frontend-app` and `frontend-pepper` are deliberately kept in lockstep (see
[PEPPER_PARITY_CHANGES.md](PEPPER_PARITY_CHANGES.md) for the detailed porting log).

Team, timeline, and study design (participant counts, pilot, ethics) live in the Notion "OTC
Project" page, not here — this file is engineering-only.

## Repo layout

```
backend/            FastAPI + SQLAlchemy + FAISS — the shared brain for both conditions
frontend-app/        React/Vite — tablet/web participant app ("MedCheck"), Condition B
frontend-admin/       React — researcher/admin panel (corpus + session data), HTTP Basic Auth
frontend-pepper/      Native Android (QiSDK) — Pepper robot app, Condition A
docs/                 This file, PEPPER_PARITY_CHANGES.md, QA_TESTING_GUIDE.md (untracked)
```

## Deployment

- **Backend:** Render (`https://otc-h81d.onrender.com`), auto-deploys on push to `main`. Free
  tier — the service can spin down after inactivity, and there's a real (if short) window during
  every redeploy where requests fail; the frontend now retries transient failures (see "Recent
  engineering work" below).
- **`frontend-app` (participant tablet/web app):** Vercel, `https://otcuserpanel.vercel.app/`.
- **`frontend-admin` (researcher panel):** Vercel, `https://otc-sandy-omega.vercel.app/`.
  HTTP Basic Auth (`admin` / see team credentials doc — not repeated here).
- **`frontend-pepper`:** not auto-deployed. It's a native Android app installed on the physical
  Pepper robot (or an emulator for dev) — picking up a backend change means rebuilding
  (`./gradlew assembleDebug`) and reinstalling, it does not update itself like the web apps do.

## Backend architecture

FastAPI app (`backend/app/main.py`) with these route groups:

| Prefix | File | Purpose |
|---|---|---|
| `/api/products`, `/api/session/*` | `routes/sessions.py` | Public product list, session start/end, session export |
| `/api/query`, `/api/query/stream`, `/api/core-info` | `routes/query.py` | Ask a question (buffered or streaming), fetch core product info |
| `/api/stt`, `/api/tts` | `routes/voice.py` | Speech-to-text and text-to-speech proxy (OpenAI) |
| `/api/admin/*` | `routes/admin.py` | Corpus management (upload/ingest/delete leaflets), session data (list/export/delete), test-retrieval debug tool. Admin-auth gated. |

### RAG pipeline (`backend/app/rag/`)

**This was deliberately simplified** from an earlier 4-gate pipeline (retrieval-score threshold
→ regex heuristics → a separate LLM scope classifier → a second generation-time recheck) down to
**one unified LLM call**:

1. `retrieve()` (`vectorstore.py`) — FAISS similarity search over the product's leaflet chunks.
2. `generate_answer()` / `generate_answer_stream()` (`generate.py`) — a single `gpt-4o-mini` chat
   completion that sees the retrieved chunks *and* the last 4 conversation turns, and in one pass
   decides whether the question is answerable from the leaflet, small talk, or out of scope
   (personal medical advice, diagnosis, symptoms, anything not covered) — deflecting to
   `scope_guard.FALLBACK_TEXT` ("That is outside what I can help with. Please speak to a
   pharmacist or your doctor.") for anything out of scope. `scope_guard.py` is now just that one
   constant — the old heuristic/classifier code was deleted entirely.
3. The system prompt includes an explicit anti-hallucination rule: answer only from the provided
   leaflet excerpts, never fill gaps with plausible-sounding facts (this was added after catching
   the model fabricate an onset time and a food-interaction warning that weren't actually in the
   leaflet).
4. `ingest.py` — chunks an uploaded leaflet (PDF or plain text) by recognized section headers
   (covers both UK-leaflet wording and US/FDA wording like "description"/"supplement facts"),
   captures any preamble text before the first header as an "Overview" chunk (previously silently
   dropped), embeds with `text-embedding-3-large`, and rebuilds the FAISS index for that product.

### Streaming voice pipeline

To cut voice-mode latency, neither condition waits for a full answer before speaking anymore.
`frontend-app` and `frontend-pepper` share the streaming backend endpoint but speak the answer
through different mechanisms - the tablet fetches and plays TTS audio clips, Pepper speaks
natively through QiSDK, which never called the backend's TTS proxy in the first place:

- `POST /api/query/stream` streams the LLM's answer as NDJSON deltas (`{"delta": "..."}` lines,
  then a final `{"done": true, ...}` line with the persisted turn's metadata).
- The frontend extracts each complete sentence from the growing text as it arrives and pushes it
  to TTS immediately (`useTTS.speakStream()`), so speech starts on the first sentence while later
  sentences are still generating — instead of waiting for the whole answer.
- `POST /api/tts` genuinely streams audio bytes from OpenAI (`with_streaming_response` +
  `iter_bytes()`) rather than buffering the whole clip first, using `gpt-4o-mini-tts`
  (benchmarked ~26-30% faster than `tts-1`).
- OpenAI's automatic prompt caching is already active for the generation calls (confirmed ~94%
  cache hit rate on repeat calls in testing) — no code change needed, it kicks in automatically
  for prompts over ~1024 tokens with a stable prefix (the system prompt + leaflet chunks).

## Data model (`backend/app/db/models.py`)

SQLite via SQLAlchemy, **no Alembic / formal migrations** — schema is created with
`Base.metadata.create_all()` on startup (`db/session.py`), which only creates missing tables, not
new columns on existing ones. There have been no new-column changes so far this project; if one
is ever needed, it'll need either a manual `ALTER TABLE` or an actual migration tool added — this
doc should be updated at that point.

- **Product** — a physical OTC medicine (`slug`, `display_name`). Created via the admin panel's
  "+ Add new medicine..." upload flow, or implicitly by re-using an existing slug.
- **Document** — one uploaded leaflet for a Product. Only one `active` Document per product at a
  time; re-ingesting replaces it rather than appending (old chunks are deleted).
- **Chunk** — one retrievable unit of leaflet text, tied to a Document and (denormalized) a
  Product for fast filtering. `vector_index` matches its row position in the FAISS index, which
  is always rebuilt fully from Chunk rows on ingest.
- **SessionRecord** — one participant session: `platform` (`tablet_web` / `mobile_web` /
  `desktop_web` / `android_native` / `pepper`), `condition` (`tablet_ai` or `pepper` — derived
  from `platform`, see below), the Product being discussed, device info, start/end time, turn
  count.
- **Turn** — one Q&A exchange within a session: query text, retrieved chunk IDs, response text,
  `in_scope` flag, latency, timestamp, `input_method` (`voice`/`typed`).

**Custom `DateTime` TypeDecorator** wraps `sqlalchemy.DateTime(timezone=True)`: SQLite silently
drops tzinfo on write even with `timezone=True`, so on read it re-attaches `timezone.utc` if the
value comes back naive. Without this, every timestamp shown in the admin panel was off by the
viewer's local UTC offset, because a naive ISO string (no `Z`/offset suffix) gets parsed by
browsers as local time, not UTC. Postgres (which does preserve tzinfo) passes through unaffected.

**`condition` derivation** (`routes/sessions.py`): `"pepper" if platform == "pepper" else
"tablet_ai"`. This used to be hardcoded to `"tablet_ai"` for every platform — a real
data-integrity bug for the study, since it meant Pepper sessions were indistinguishable from
tablet sessions in the data. Fixed and verified against production.

## Admin panel — adding a new medicine

Corpus tab → product dropdown → "+ Add new medicine..." → enter display name + slug → choose a
file (PDF or plain text) → "Upload & Ingest". This creates the Product row, ingests the leaflet
into Chunks, and rebuilds that product's FAISS index — verified end-to-end: the new product shows
up in the participant app's picker immediately (no redeploy needed, it's a live DB read), and a
full session against it (in-scope question answered correctly, out-of-scope question correctly
deflected) saves to the admin panel with the right product, platform, and turn data.

## Recent engineering work (this pass)

- Simplified the RAG/scope architecture from 4 gates to 1 unified LLM call (see above).
- Fixed real ingestion bugs (dropped preamble text, US-leaflet header wording).
- Added conversation memory (last 4 turns) so follow-up questions resolve correctly.
- Fixed the `condition` hardcoding bug and the SQLite timestamp timezone bug (both real
  data-integrity issues for the study's session data).
- Full MedCheck visual rebrand ported to both `frontend-app` and `frontend-pepper` for research
  parity (see PEPPER_PARITY_CHANGES.md).
- Built the sentence-streaming generation+TTS pipeline described above to cut voice-mode latency,
  plus an animated/rotating loading-message indicator and a fix for the transcript not
  auto-scrolling while an answer streams in.
- Fixed a `mountedRef` bug (TTS silently disabled after React 18 StrictMode's dev-only
  double-invoke) and a Chrome quirk (firing `pause` immediately before `ended` on natural
  playback completion, which was cutting every spoken answer off after its first sentence).
- Added retry-with-backoff + a "Try again" control to the participant app's product-list load, so
  a transient backend hiccup (e.g. a Render redeploy window) no longer permanently strands the
  screen requiring a full page reload.
- Ported the sentence-streaming idea to `frontend-pepper`: it now also calls
  `/api/query/stream` and speaks each sentence via QiSDK `Say` as soon as it's complete (a
  `BlockingQueue` + background "speaker" thread stands in for the web's audio-clip queue, since
  `Say` generates its own audio on-robot — no fetch step needed), plus the same rotating loading
  message and a matching retry-with-backoff fix for its own product list load. The web's
  progressive on-screen "typing" effect was deliberately **not** ported — Pepper's speech is the
  primary channel and the transcript is secondary, so it still only updates once the full answer
  is known. See [PEPPER_PARITY_CHANGES.md](PEPPER_PARITY_CHANGES.md) for the full breakdown of
  what did and didn't port, plus a batch of physical-screen-only layout bugs (orb clipping,
  off-screen content, header misalignment, an invisible dropdown arrow) found and fixed once real
  Pepper screenshots were available — none of these were visible on the dev emulator, which is
  noticeably larger than the physical screen.

## Verification caveat

The Pepper voice-streaming port above was verified end-to-end on the `Pepper_1.9_API_29` emulator
against the production backend (correct answers, no crashes), and the layout bugs were verified by
resizing that same emulator down to 800x480. Neither the emulator's QiSDK speech output nor its
exact screen dimensions are guaranteed to match the physical robot — a pass on the actual hardware
is still needed before relying on either for the study.
