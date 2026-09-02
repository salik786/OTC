import { useCallback, useState } from "react";
import { api } from "../lib/api";

/** Module-level (not per-hook) singleton - every screen's useTTS() call controls the SAME audio
 * element, so starting new speech anywhere always stops whatever was previously playing,
 * regardless of which component/screen originally started it. Without this, navigating away from
 * a screen mid-speech left its audio playing forever in the background (confirmed bug: multiple
 * overlapping voices, audio that never stopped on screen change). */
let sharedAudio: HTMLAudioElement | null = null;
let sharedUrl: string | null = null;
// Bumped on every stopAllSpeech() call so any in-flight segment (see speak()) whose TTS fetch
// resolves AFTER the participant already hit Stop can tell it's stale and must not start
// playback - without this, hitting Stop while a fetch was in flight did nothing, and speech
// would still start moments later as if Stop had been ignored.
let speechToken = 0;

export function stopAllSpeech() {
  speechToken++;
  if (sharedAudio) {
    sharedAudio.pause();
    sharedAudio.onended = null;
    sharedAudio.onerror = null;
    sharedAudio.onpause = null;
  }
  if (sharedUrl) {
    URL.revokeObjectURL(sharedUrl);
    sharedUrl = null;
  }
  sharedAudio = null;
}

/** Splits an answer into a short first segment (one sentence) and the remainder, so the first
 * segment can start playing as soon as its own (much shorter) TTS clip is ready instead of
 * waiting for the whole answer's audio to generate - the biggest lever on "time until the voice
 * starts talking" without a full incremental-playback rearchitecture. Single-sentence answers
 * aren't split - there'd be nothing left for a second segment to buy. */
function splitIntoSegments(text: string): string[] {
  const sentences = text.match(/[^.!?]+[.!?]+(?:\s+|$)/g);
  if (!sentences || sentences.length <= 1) return [text];
  const first = sentences[0].trim();
  const rest = sentences.slice(1).join("").trim();
  return rest ? [first, rest] : [first];
}

type PlayOutcome = "ended" | "error" | "stopped";

/** Plays one segment's audio blob, resolving once - on natural completion, on a playback error,
 * or when stopAllSpeech() pauses it out from under us (an external pause never fires 'ended', so
 * without listening for 'pause' too, awaiting this would hang forever and block the segment
 * queue in speak() from ever reaching its next stop-check).
 *
 * Takes the token that was active when this segment started so its onpause handler can tell a
 * REAL external stop apart from a browser firing 'pause' as part of natural end-of-playback -
 * Chrome does this immediately before 'ended', and treating that as "the user hit Stop" silently
 * cut every answer off after its first segment (confirmed bug: only the first sentence of any
 * multi-sentence answer was ever spoken). stopAllSpeech() always bumps speechToken before calling
 * .pause(), so a pause with the token unchanged is that natural-completion artifact, not a stop -
 * ignore it and let the 'ended' event (which follows immediately after) resolve instead. */
function playBlob(blob: Blob, myToken: number): Promise<PlayOutcome> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    sharedAudio = audio;
    sharedUrl = url;
    let settled = false;
    const finish = (outcome: PlayOutcome) => {
      if (settled) return;
      settled = true;
      URL.revokeObjectURL(url);
      if (sharedAudio === audio) {
        sharedAudio = null;
        sharedUrl = null;
      }
      resolve(outcome);
    };
    audio.onended = () => finish("ended");
    audio.onerror = () => finish("error");
    audio.onpause = () => {
      if (myToken !== speechToken) finish("stopped");
    };
    audio.play().catch(() => finish("error"));
  });
}

export interface StreamSpeechController {
  /** Enqueue one more sentence to speak, as soon as its text is known - fetches its TTS clip
   * immediately rather than waiting for previously-queued sentences to finish playing first. */
  pushSentence: (text: string) => void;
  /** Call once no more sentences are coming (the answer's text stream has ended). Playback of
   * whatever is already queued continues; this just lets the player loop know it can stop
   * waiting for more and finish once the queue drains. */
  end: () => void;
}

/** Plays TTS audio from the backend proxy (not native SpeechSynthesis) so voice output stays
 * consistent across tablet/mobile/desktop and reusable by a future Android client. */
export function useTTS() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Streaming counterpart to speak(): instead of splitting one already-known full answer into
   * two segments, sentences are pushed in as the caller discovers them (e.g. from a token stream
   * from the backend) and each one's TTS fetch starts the moment it's pushed - not once the
   * previous sentence's audio finishes playing. This is what actually lets the very first
   * sentence start playing while the model is still generating the rest of the answer, instead
   * of speak()'s static 2-way split which still waits for the WHOLE answer's text before
   * splitting anything. */
  const speakStream = useCallback((): StreamSpeechController => {
    setError(null);
    stopAllSpeech();
    setIsSpeaking(true);
    const myToken = speechToken;

    const fetches: Promise<Blob | null>[] = [];
    let ended = false;
    let notify: (() => void) | null = null;
    const wake = () => {
      notify?.();
      notify = null;
    };

    (async () => {
      let i = 0;
      let playedAny = false;
      while (true) {
        if (myToken !== speechToken) return; // stopped/superseded
        if (i >= fetches.length) {
          if (ended) break;
          await new Promise<void>((resolve) => {
            notify = resolve;
          });
          continue;
        }
        const blob = await fetches[i];
        i++;
        if (myToken !== speechToken) return;
        if (!blob) continue; // skip a failed segment rather than aborting the rest of the answer
        const outcome = await playBlob(blob, myToken);
        playedAny = true;
        if (outcome === "stopped" || myToken !== speechToken) return;
        if (outcome === "error") {
          setError("Playback failed.");
          return;
        }
      }
      if (myToken === speechToken) {
        setIsSpeaking(false);
        if (!playedAny) setError("Could not play audio.");
      }
    })();

    return {
      pushSentence: (text: string) => {
        if (myToken !== speechToken || ended) return;
        fetches.push(api.speak(text).catch(() => null));
        wake();
      },
      end: () => {
        ended = true;
        wake();
      },
    };
  }, []);

  const speak = useCallback(async (text: string) => {
    setError(null);
    stopAllSpeech();
    // Set true here, not once the first segment's audio is actually playing - the TTS request
    // (generation + download) can take a couple of seconds, and leaving isSpeaking false for
    // that whole window made the status text fall back to "Tap the microphone..." right after
    // the answer appeared, then jump to "Speaking..." with no visible transition once audio
    // actually started. That silent gap read as a stall/glitch. Covering the full prepare+play
    // window keeps the status continuous instead.
    setIsSpeaking(true);
    const myToken = speechToken;

    const segments = splitIntoSegments(text);
    // Fire every segment's TTS request now, in parallel - not one-at-a-time as each previous
    // segment finishes playing. By the time segment 1 finishes speaking, segment 2's audio has
    // been generating in the background for that whole duration and is usually already
    // downloaded, so playback continues with no audible gap. Total speech duration is unchanged;
    // only the wait before the FIRST sound is heard gets shorter, since that's now bounded by one
    // sentence's generation time instead of the whole answer's.
    const fetches = segments.map((segment) => api.speak(segment).catch(() => null));

    let playedAny = false;
    for (let i = 0; i < segments.length; i++) {
      if (myToken !== speechToken) return; // stopped/superseded before this segment's turn
      const blob = await fetches[i];
      if (myToken !== speechToken) return; // stopped/superseded while this segment was fetching
      if (!blob) continue; // skip a failed segment rather than aborting the rest of the answer
      const outcome = await playBlob(blob, myToken);
      playedAny = true;
      if (outcome === "stopped" || myToken !== speechToken) return; // don't continue to the next segment
      if (outcome === "error") {
        setError("Playback failed.");
        return;
      }
    }

    if (myToken === speechToken) {
      setIsSpeaking(false);
      if (!playedAny) setError("Could not play audio.");
    }
  }, []);

  const stop = useCallback(() => {
    stopAllSpeech();
    setIsSpeaking(false);
  }, []);

  return { speak, speakStream, stop, isSpeaking, error };
}
