import { useCallback, useEffect, useRef, useState } from "react";
import { api, type InputMethod, type SessionStartResponse } from "../lib/api";
import { useSTT } from "./useSTT";
import { useTTS, stopAllSpeech } from "./useTTS";
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

  useEffect(() => {
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
      setSubmitting(true);
      try {
        const res = await api.query(session.session_id, text.trim(), method);
        setHistory((h) => [
          ...h,
          { turnNumber: res.turn_number, queryText: text.trim(), answerText: res.answer_text, inScope: res.in_scope },
        ]);
        if (mountedRef.current) tts.speak(res.answer_text);
      } catch {
        setHistory((h) => [
          ...h,
          {
            turnNumber: h.length + 1,
            queryText: text.trim(),
            answerText: "Sorry, something went wrong reaching the system. Please try again.",
            inScope: false,
          },
        ]);
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
