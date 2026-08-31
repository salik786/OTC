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

- **Conversational small talk** (`backend/app/rag/scope_guard.py`) - greetings,
  farewells, "can you hear me", "how are you", thanks now get a natural reply
  instead of the medical-scope deflection firing on non-medical utterances.
- **STT model** switched from `whisper-1` to `gpt-4o-mini-transcribe` for lower
  latency (`OPENAI_STT_MODEL` env var / `backend/app/config.py`).
- **Corpus auto-seed fix** and **DATABASE_URL persistence fix** - operational,
  not participant-facing, no porting needed either way.

## Needs manual porting into `frontend-pepper` (or a deliberate decision not to)

These are `frontend-app`-only changes - Pepper's matching Activities need the
equivalent logic added by hand.

| Change | frontend-app location | frontend-pepper equivalent | Status |
|---|---|---|---|
| Merged the product-picker + Welcome screen into one screen (greeting on top, dropdown, two action buttons, small disclaimer at bottom, no "researcher setup" badge) | `screens/ResearcherSetup.tsx` (was `ResearcherSetup.tsx` + `Welcome.tsx`) | `ResearcherSetupActivity` + `WelcomeActivity` | **Not ported** - Pepper still has these as two separate screens/Activities |
| Voice+Text Chat is now hands-free: after each answer, listening auto-resumes instead of requiring another tap | `screens/VoiceTextChat.tsx` (`voiceModeActiveRef` pattern) | `ChatActivity` | **Not ported** |
| Avatar mode hands-free loop + explicit Stop control to interrupt playback | `screens/AvatarChat.tsx` | `AvatarChatActivity` | **Not ported** |
| Voice capture auto-stops on sustained silence (Web Audio API RMS detection) instead of requiring a second tap to stop recording | `hooks/useSTT.ts` | `ConversationController` / `Speech.java` | **Not ported** - needs an Android equivalent of silence detection, not a direct code port |
| End Session shows "Saving your session..." on the Closing screen, then auto-resets to the setup screen after ~4s instead of staying a dead end | `screens/Closing.tsx` + `App.tsx` (`handleResetToStart`) | `ClosingActivity` | **Not ported** |
| Back button added to every mid-flow screen (previously some screens were dead ends with no way out except reload) | `components/BackButton.tsx`, used across screens | all Activities | **Not ported** |

## Judgment call, not a straight port

- **Removed passive TTS auto-narration** from Welcome/Core-Info/Closing on the
  tablet (voice now only used for live Q&A answers) - this was motivated by
  tablet-specific feedback ("distracting" since the same text is already
  visible on screen). **Pepper doesn't have that redundancy** - speech is
  arguably Pepper's primary channel, not a duplicate of on-screen text - so
  this one probably should **not** be ported as-is. Worth a explicit decision
  with the team before touching `frontend-pepper`'s TTS calls, not a
  copy-paste.

## Not applicable to Pepper at all

- Admin panel changes (document viewer, session search/export/delete, table
  overflow fixes) - admin-only, no Pepper equivalent needed.
- Abstract orb avatar visual redesign - Pepper *is* the embodied avatar; this
  was specifically about replacing a screen-drawn robot face with something
  non-representational for the tablet's non-embodied condition. Not relevant
  to the physical robot.
