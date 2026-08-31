# Pepper Parity Tracker

`frontend-pepper` is a separate native Android codebase, not a build target of
`frontend-app`. Backend changes apply to both automatically (same API). Frontend/UX
changes in `frontend-app` do **not** carry over automatically and need to be
manually ported into the matching `frontend-pepper` Activity - this file tracks
what's changed and whether it needs porting.

Update this file whenever a `frontend-app` change affects participant-facing
behavior, so nothing gets forgotten when Pepper work resumes.

---

## Already shared automatically (backend changes - nothing to port)

These live in `backend/`, so both `frontend-app` and `frontend-pepper` get them
for free the moment they call the same API:

- **Scope enforcement rewrite** (`backend/app/rag/generate.py`,
  `backend/app/rag/scope_guard.py`) - collapsed from a 4-gate pipeline (retrieval
  threshold, regex heuristics, a blind LLM classifier, a second generation-time
  check) into one unified LLM call that sees the actual retrieved leaflet
  excerpts and decides in a single pass whether a question is small talk,
  answerable, or out of scope. Fixed a long tail of false deflections
  ("what medicine can you help me with", "can children take this", "how you can
  help me", etc.) that affect both conditions identically since they hit the
  same endpoint.
- **Conversation memory** - the backend now pulls the last 4 turns from its own
  Turn table and includes them as real message history in the generation call,
  so follow-ups like "what do you mean by that" resolve correctly. This is
  entirely server-side (Pepper's `ApiClient.query()` still just sends
  `session_id` + `query_text` + `input_method`, unchanged) - no client work
  needed on either side.
- **Unintelligible-input handling** - a garbled/cut-off transcription (e.g. a
  clipped voice fragment) now gets "Sorry, I didn't quite catch that - could you
  say that again?" instead of the fixed pharmacist-deflection text, which was
  misleading for a transcription glitch. Directly benefits Pepper's Android
  `SpeechRecognizer` output too.
- **Ingestion fixes** (`backend/app/rag/ingest.py`) - structural chunking no
  longer silently drops leaflet text that appears before the first recognized
  section header, and the recognized-header list now covers US/FDA-style
  wording ("description", "supplement facts", "other ingredients") in addition
  to the original UK-leaflet wording.
- **Public product list** (`GET /api/products`, no auth) - added so a medicine
  uploaded via the admin panel appears in the participant-facing picker
  immediately, without a code change on either frontend. `frontend-pepper`'s
  `ResearcherSetupActivity` now calls this (see below - this one needed a small
  client change, since it replaced a hardcoded product list).
- **Conversational small talk**, **STT model** (`gpt-4o-mini-transcribe`),
  **corpus auto-seed fix**, **DATABASE_URL persistence fix** - unchanged from
  before, still automatic.

## Ported into `frontend-pepper` this pass

All of the previously-tracked "Not ported" items are now done, verified with a
successful `./gradlew assembleDebug` (a pre-existing JDK 21 / R8 dexer
incompatibility on this machine was blocking builds independent of any of this
work - see "Build environment note" below - fixed via a user-level Gradle
config, not by touching the committed build).

| Change | frontend-app location | frontend-pepper equivalent | Status |
|---|---|---|---|
| Merged the product-picker + Welcome screen into one screen | `screens/ResearcherSetup.tsx` | `ResearcherSetupActivity` (absorbed `WelcomeActivity`, which is deleted) | **Ported** - product list now fetched live from `/api/products` (was hardcoded to paracetamol/multivitamin) via new `ApiClient.listProducts()`/`ApiClient.Product`. The on-robot greeting speech is preserved (fires once when this screen gains focus), since Pepper's speech is its primary channel unlike the tablet, which dropped passive narration as redundant with on-screen text - see "Judgment call" below, now resolved. |
| Voice+Text Chat hands-free (auto-resume listening after each answer) | `screens/VoiceTextChat.tsx` (`voiceModeActiveRef`) | `ChatActivity` | **Ported** - `voiceModeActive` boolean set true on mic tap, false on typing/end-session/destroy; `ConversationController.Listener.onSpeakingStateChanged(false)` triggers `startListening()` again when active. |
| Avatar mode hands-free loop + explicit Stop control | `screens/AvatarChat.tsx` | `AvatarChatActivity` | **Ported** - same `voiceModeActive` pattern, plus a new Stop button (visible only while `speaking`, swapped with the mic button) that calls `conversation.stopSpeaking()` and opts out of the loop. |
| Voice capture auto-stop on sustained silence | `hooks/useSTT.ts` (Web Audio RMS) | `ConversationController` / `Speech.java` | **Not applicable, already satisfied** - Android's `SpeechRecognizer` (used by both `ChatActivity` and `AvatarChatActivity`) has its own OS-level end-of-speech detection; there was never a "second tap to stop" behavior on Pepper needing a port. |
| Closing screen auto-reset instead of a dead end | `screens/Closing.tsx` + `App.tsx` (`handleResetToStart`) | `ClosingActivity` | **Ported** - `Handler.postDelayed(4000ms)` navigates to `ResearcherSetupActivity` with `FLAG_ACTIVITY_NEW_TASK \| FLAG_ACTIVITY_CLEAR_TASK`, clearing the whole back stack so there's no way back into the ended session. `onBackPressed()` still swallows back presses during the ~4s window (unchanged). Note: unlike the web version, Pepper's session-end API call already happens in `ChatActivity`/`AvatarChatActivity.endSession()` before navigating here, so there's no "Saving..." state to show - this screen only ever displays the final "session has ended" state. |
| Back button on every mid-flow screen | `components/BackButton.tsx` | all Activities | **Ported** - was already on `ChatActivity`/`AvatarChatActivity`/`ModeSelectActivity` (the tracker was stale on this point); added to `CoreInfoActivity` (previously missing). All four now use a shared `UiKit.topNav()` helper (back button + centered compact brand header in one flex row) instead of a standalone back button, matching a bug fix made on the tablet side: centering a header within the full screen width mathematically overlaps a corner back button once the wordmark is wide enough relative to screen width - a real flex row avoids this by construction. `ResearcherSetupActivity` (launcher) and `ClosingActivity` (deliberate dead end) still have none, matching the tablet. |
| AvatarChat transcript missing deflected-answer styling that ChatActivity has | *(found during this pass, not previously tracked)* | `AvatarChatActivity.addTranscriptTurn()` | **Fixed** - now applies the same warning-tinted background/text color as `ChatActivity` when `turn.inScope` is false, instead of rendering identically to an in-scope answer. |

## MedCheck visual rebrand - ported

The tablet's full visual rebrand (mint/teal gradient background, heart+cross
logo mark, gradient pill buttons, rounded gradient cards, icon-labeled info
rows) is now ported into `UiKit.java` and every Activity:

- `UiKit.screenBackground()` - mint gradient, applied as every screen's root background.
- `UiKit.brandHeader(ctx, compact, light)` - heart+cross mark (drawn as a vector
  path, no bitmap asset) + "MedCheck" wordmark + tagline, matching
  `frontend-app`'s `AppHeader` component. `light=true` for `ClosingActivity`'s
  solid dark-teal background.
- `UiKit.topNav()` - back button + compact header in a real flex row (see above).
- `UiKit.primaryButton()` / `circleGradientBg()` - teal gradient fills (Android's
  `GradientDrawable` supports this natively) instead of flat color, matching
  the web app's gradient buttons.
- `UiKit.card()` - rounded gradient card (white to mint) with elevation,
  replacing the flat white rounded rect.
- `UiKit.iconBadge()` - small colored pill icon badge, used on the setup
  screen's "Medicine on the counter" label and the disclaimer footer.
- `CoreInfoActivity` rebuilt with icon-labeled rows (target/dose/clock/warning
  icons in colored badges) instead of plain label/value text pairs, plus a
  pill-capsule product avatar and an "always read the label" footer note -
  matching the tablet's `CoreInfo.tsx` redesign.
- New vector drawables: `ic_heart_cross`, `ic_capsule`, `ic_clock`, `ic_dose`,
  `ic_target`, `ic_warning`, `ic_info`, `ic_question`, `ic_sparkle`, `ic_stop`.

No emoji were introduced (the codebase already avoided them - Pepper's
Android 6.0 image predates color emoji font support for several codepoints,
which is why `UiKit.icon()`/vector drawables were already the established
pattern here, unlike the tablet where this had to be fixed as part of the
same rebrand).

## Judgment call - resolved

- **Passive TTS auto-narration removed on tablet, kept on Pepper.** The
  merged `ResearcherSetupActivity` still speaks its greeting via QiSDK `Say`
  once on focus-gain, same as the old standalone `WelcomeActivity` did -
  deliberately NOT matching the tablet's removal of passive narration, since
  Pepper's speech is its primary channel rather than a redundant duplicate of
  on-screen text (which was the tablet's specific reason for dropping it).

## Not applicable to Pepper at all

- Admin panel changes (document viewer, session search/export/delete, table
  overflow fixes) - admin-only, no Pepper equivalent needed.
- Abstract orb avatar visual redesign - Pepper *is* the embodied avatar; this
  was specifically about replacing a screen-drawn robot face with something
  non-representational for the tablet's non-embodied condition. Not relevant
  to the physical robot.

## Build environment note

`./gradlew assembleDebug` was crashing with a dexer (R8) internal
`NullPointerException` on this machine - reproduced on the *unmodified*
pre-existing code via `git stash`, so it's a toolchain issue, not something
introduced by this pass. Root cause: the system default JDK is 21, and this
project's AGP/R8 version has a known incompatibility running under JDK 21.
Fixed by pointing Gradle at JDK 17 via `~/.gradle/gradle.properties`
(`org.gradle.java.home=...`) - a per-user, non-committed file, so this doesn't
affect other machines or get checked into the repo. `compileDebugJavaWithJavac`
alone (no dexing) was unaffected by this and used throughout this pass to
verify each change compiles before running the full `assembleDebug`.
