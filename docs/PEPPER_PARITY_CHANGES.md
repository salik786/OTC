# Pepper Parity Tracker

`frontend-pepper` is a separate native Android codebase, not a build target of
`frontend-app`. Backend changes apply to both automatically (same API). Frontend/UX
changes in `frontend-app` do **not** carry over automatically and need to be
manually ported into the matching `frontend-pepper` Activity - this file tracks
what's changed and whether it needs porting.

Update this file whenever a `frontend-app` change affects participant-facing
behavior, so nothing gets forgotten when Pepper work resumes.

---

## Physical-screen layout bugs (found via real Pepper screenshots, not the dev emulator)

The dev emulator (`Pepper_1.9_API_29`) used throughout this project's testing is 1280x800 -
noticeably larger/wider than the physical Pepper's actual screen. Four real layout bugs were
invisible on the emulator and only showed up on the physical screen; reproduced locally by
resizing the emulator down to 800x480 (`adb shell wm size 800x480`) rather than needing the robot
itself. All four fixed in `UiKit.java`, `AvatarChatActivity.java`, `ModeSelectActivity.java`,
`ResearcherSetupActivity.java`:

1. **The orb (`UiKit.orb()`) rendered with flat-cut left/right edges instead of a full circle.**
   Root cause: the orb's outer wrapper only *requests* a 220dp minimum size, but a caller's
   `addView(orbView, someLayoutParams)` always overrides that - on a screen where the available
   width came out narrower than 220dp, the inner circle got hard-clipped to the wrapper's smaller
   actual bounds. Fixed with `outer.setClipChildren(false)` so the circle always renders at its
   full round size even if that means slightly overflowing tight bounds, instead of being clipped.
   (A first attempt fixed this by making the inner circle `MATCH_PARENT` instead - that broke
   differently, and worse, once combined with fix #2 below: a `ScrollView` always measures its
   immediate child with an unspecified height, and that ambiguity cascaded down through
   `MATCH_PARENT` and collapsed the circle to almost nothing. Reverted to a fixed-size inner
   circle, which measures correctly regardless of the surrounding container.)
2. **On `AvatarChatActivity`, the orb and everything below the back/MedCheck row could render
   entirely off-screen with no way to reach it.** Root cause: the section holding the orb, status
   text, mic dock, and end-session button was a plain (non-scrolling) `LinearLayout` sized to its
   own content - on a screen shorter than the emulator, its total content height could exceed
   what's actually available, and unlike a `ScrollView`, a plain `LinearLayout` doesn't clip and
   hide gracefully, it just extends past the screen edge with nothing to scroll. Fixed by wrapping
   that whole section in its own `ScrollView`.
3. **"MedCheck" in the top bar didn't line up with content below it that's centered across the
   full screen width** (the orb, on `AvatarChatActivity`). Root cause: `UiKit.topNav()`'s header
   only centers in the space to the *right* of the back button, by design (to guarantee it can
   never overlap the back button on a narrow screen) - but that means its centering axis is offset
   from anything below it that centers across the *full* row width. Fixed by adding an invisible,
   same-size mirror of the back button on the right side of the row, so the header now centers
   across the true full width while keeping the original "never overlaps the back button"
   guarantee (if anything, its available space is now smaller, so it's safer, not less safe).
4. **The medicine-picker `Spinner` on the launcher screen didn't look like a dropdown at all** -
   just a plain rounded box with no arrow/caret. Root cause: `spinner.setBackground(...)` replaces
   the platform's entire default background, which is also where the built-in dropdown-arrow
   indicator lives. Fixed by overlaying a plain "▾" glyph (not a vector icon or emoji - a basic
   Unicode geometric character, safe on Pepper's Android 6.0 build) on the right side, non-
   clickable so touches still pass through to the Spinner underneath.
5. **`ModeSelectActivity`'s two mode cards had the same "could render off-screen with no way to
   reach it" problem as #2** - its root was also a plain, non-scrolling `LinearLayout`. Fixed the
   same way, wrapping it in a `ScrollView` (matching the pattern already used on
   `ResearcherSetupActivity`).

Not yet chased down: a reported "Chat UI is not properly visible" issue on `ChatActivity`
specifically - re-tested at the same 800x480 resolution used to reproduce the above and the screen
looked correctly laid out (header, empty-state text, input bar, mic/Ask buttons, end-session link
all visible and reachable). Needs an actual screenshot of the specific problem to chase further;
may simply have been a consequence of one of the above bugs rather than a separate one.

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

## Voice latency work - ported (speech half only)

Ported the sentence-level streaming idea from `frontend-app`'s voice latency work (see
`docs/ARCHITECTURE.md`), adapted to how Pepper actually speaks:

| Change | frontend-app location | frontend-pepper equivalent | Status |
|---|---|---|---|
| Stream the answer from the backend instead of waiting for the whole thing | `lib/api.ts` `queryStream()`, backend `/api/query/stream` | `ApiClient.queryStream()` (new) | **Ported** - reads the same NDJSON response with `BufferedReader`/`charStream()` instead of `fetch()` + `ReadableStream`. |
| Speak each sentence as soon as it's complete, not the whole answer at once | `hooks/useTTS.ts` `speakStream()` (fetches+plays each sentence's TTS clip) | `ConversationController.submit()` + a per-submit sentence `BlockingQueue` consumed by a background "speaker" thread that runs one QiSDK `Say` per sentence, in order | **Ported**, adapted - no audio-fetch step needed since `Say` generates its own audio on-robot; a `speechToken` counter (same role as the web's) lets a new `submit()` or `stopSpeaking()` supersede an in-flight stream/speaker cleanly. |
| Animated, rotating "Thinking..." message | `hooks/useLoadingMessage.ts` | `LoadingMessageCycler` (new) | **Ported** - same 4 messages, same 1.5s interval. Wired into both `ChatActivity` and `AvatarChatActivity`; in `AvatarChatActivity` it's stopped as soon as `onSpeakingStateChanged(true)` fires, since speech can now start mid-generation and "Speaking..." should take over at that point (matches `updateStatus()`'s existing priority order). |
| Product-list load retries with backoff + a "try again" control instead of stranding the screen | `screens/ResearcherSetup.tsx` | `ResearcherSetupActivity.loadProductsAttempt()` | **Ported** - two retries with backoff, then `loadErrorTv` becomes tap-to-retry. |

**Not ported - deliberate judgment call:** the web's progressive on-screen "typing" effect (the
transcript bubble filling in as the answer streams) was **not** ported. `addTurnBubbles()` /
`addTranscriptTurn()` still add the Q+A pair to the transcript only once the full answer is known,
same as before this pass. Reasoning: Pepper's speech is the primary channel and the on-screen
transcript is secondary (same reasoning as the existing "Passive TTS auto-narration" judgment call
above) - the actual latency win participants experience is Pepper starting to *talk* sooner, which
is what got ported; a live-typing transcript would need each `ChatActivity`/`AvatarChatActivity`
turn-bubble to become a mutable, in-place-updated view instead of an append-once one, which was
judged not worth the added complexity for a secondary display.

Also not applicable: the backend's genuinely-streaming `/api/tts` and the switch to
`gpt-4o-mini-tts` - Pepper never called `/api/tts` in the first place (see `ConversationController`
header comment), so neither change affects it.

`./gradlew assembleDebug` succeeds (JDK 17 workaround still required - see below). Verified on the
`Pepper_1.9_API_29` emulator against the production backend: submitted a typed question in both
`ChatActivity` and `AvatarChatActivity`, confirmed the new `/api/query/stream` round trip
completes cleanly with the correct, leaflet-accurate answer, the loading indicator shows while
waiting, and the UI resets correctly afterward (input cleared, buttons re-enabled, status back to
idle) - no crashes or exceptions in either path. This emulator has no paired robot, so
`qiContext` never becomes non-null and QiSDK `Say` never actually fires - the sentence-queue /
`speechToken` / speaking-state logic that depends on that (the actual "does Pepper start talking
sooner" behavior) could only be verified by code review here, not on-device playback. That needs
confirming on the physical robot or a QiSDK-robot-simulator-capable emulator before relying on it
for the study.

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
