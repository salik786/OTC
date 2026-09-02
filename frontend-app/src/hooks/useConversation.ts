import { useCallback, useEffect, useRef, useState } from "react";
import { api, type InputMethod, type SessionStartResponse } from "../lib/api";
import { useSTT } from "./useSTT";
import { useTTS, stopAllSpeech } from "./useTTS";
import { useThinkingTone } from "./useThinkingTone";
import type { QATurn } from "../types";

/** Shared conversation logic (history, submitting a turn, voice capture) used by both the
 * voice+text chat screen and the avatar screen - the two interaction modes differ only in how
 * they present this same underlying state. */
export function useConversation(session: SessionStartResponse | null) {
  const [history, setHistory] = useState<QATurn[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const stt = useSTT();
  const tts = useTTS();
  const mountedRef = useRef(true);

  useThinkingTone(submitting);

  useEffect(() => {
    // Cleanup sets this false, but setup must set it back true - without this, React 18
    // StrictMode's dev-only double-invoke (mount -> cleanup -> mount again, to surface exactly
    // this kind of bug) leaves it permanently false after the very first mount, silently
    // disabling all TTS for the rest of the component's real lifetime even though it's genuinely
    // mounted. Production builds don't double-invoke, so this specific symptom wouldn't have hit
    // real participants, but the guard was still wrong on its own terms.
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // The participant may navigate away while an answer is still generating - don't let it
      // start speaking on a screen they've already left.
      stopAllSpeech();
    };
  }, []);

  const submitText = useCallback(
    async (text: string, method: InputMethod) => {
      if (!session || !text.trim()) return;
      const trimmed = text.trim();
      setSubmitting(true);

      // Placeholder turn so the participant's own question appears immediately; answerText fills
      // in progressively as the stream delivers it (a visible "typing" effect, not just a
      // side-effect of how the streaming works).
      let turnIndex = -1;
      setHistory((h) => {
        turnIndex = h.length;
        return [...h, { turnNumber: -1, queryText: trimmed, answerText: "", inScope: true }];
      });

      // Speaking starts sentence-by-sentence as the text stream delivers each one - not after
      // waiting for the whole answer to finish generating. speakStream() itself decides whether
      // this call is still current (via its own token), so it's safe to keep pushing to it even
      // if the screen has since navigated away; only skip STARTING it if already unmounted.
      const speech = mountedRef.current ? tts.speakStream() : null;
      let answerText = "";
      let unspoken = "";

      try {
        await api.queryStream(
          session.session_id,
          trimmed,
          method,
          (delta) => {
            answerText += delta;
            unspoken += delta;
            setHistory((h) => h.map((t, i) => (i === turnIndex ? { ...t, answerText } : t)));
            // Pull out every complete sentence from the unspoken buffer and hand it to TTS as
            // soon as it's found - a "sentence" here just means "ends with . ! or ?", same
            // definition speak()'s static split already used.
            const complete = unspoken.match(/[^.!?]*[.!?]+(?:\s+|$)/g);
            if (complete) {
              for (const sentence of complete) speech?.pushSentence(sentence.trim());
              unspoken = unspoken.slice(complete.join("").length);
            }
          },
          (meta) => {
            if (unspoken.trim()) speech?.pushSentence(unspoken.trim());
            speech?.end();
            setHistory((h) =>
              h.map((t, i) =>
                i === turnIndex
                  ? { turnNumber: meta.turn_number, queryText: trimmed, answerText: meta.answer_text, inScope: meta.in_scope }
                  : t
              )
            );
          }
        );
      } catch {
        speech?.end();
        setHistory((h) =>
          h.map((t, i) =>
            i === turnIndex
              ? {
                  turnNumber: t.turnNumber,
                  queryText: trimmed,
                  answerText: "Sorry, something went wrong reaching the system. Please try again.",
                  inScope: false,
                }
              : t
          )
        );
      } finally {
        setSubmitting(false);
      }
    },
    [session, tts]
  );

  const stopVoiceAndSubmit = useCallback(async () => {
    const transcript = await stt.stop();
    if (transcript && transcript.trim()) await submitText(transcript, "voice");
  }, [stt, submitText]);

  // Auto-stops itself on sustained silence (see useSTT) and submits whatever was captured -
  // no second tap needed to end the participant's turn.
  const startVoice = useCallback(() => stt.start(() => stopVoiceAndSubmit()), [stt, stopVoiceAndSubmit]);

  return {
    history,
    submitting,
    submitText,
    startVoice,
    stopVoiceAndSubmit,
    stopSpeaking: tts.stop,
    cancelVoice: stt.cancel,
    sttStatus: stt.status,
    sttError: stt.error,
    isSpeaking: tts.isSpeaking,
  };
}
