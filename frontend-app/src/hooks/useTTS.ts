import { useCallback, useState } from "react";
import { api } from "../lib/api";

/** Module-level (not per-hook) singleton - every screen's useTTS() call controls the SAME audio
 * element, so starting new speech anywhere always stops whatever was previously playing,
 * regardless of which component/screen originally started it. Without this, navigating away from
 * a screen mid-speech left its audio playing forever in the background (confirmed bug: multiple
 * overlapping voices, audio that never stopped on screen change). */
let sharedAudio: HTMLAudioElement | null = null;
let sharedUrl: string | null = null;

export function stopAllSpeech() {
  if (sharedAudio) {
    sharedAudio.pause();
    sharedAudio.onended = null;
    sharedAudio.onerror = null;
  }
  if (sharedUrl) {
    URL.revokeObjectURL(sharedUrl);
    sharedUrl = null;
  }
  sharedAudio = null;
}

/** Plays TTS audio from the backend proxy (not native SpeechSynthesis) so voice output stays
 * consistent across tablet/mobile/desktop and reusable by a future Android client. */
export function useTTS() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const speak = useCallback(async (text: string) => {
    setError(null);
    stopAllSpeech();
    try {
      const blob = await api.speak(text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      sharedAudio = audio;
      sharedUrl = url;
      setIsSpeaking(true);
      audio.onended = () => {
        setIsSpeaking(false);
        if (sharedAudio === audio) stopAllSpeech();
      };
      audio.onerror = () => {
        setIsSpeaking(false);
        setError("Playback failed.");
      };
      await audio.play();
    } catch {
      setIsSpeaking(false);
      setError("Could not play audio.");
    }
  }, []);

  const stop = useCallback(() => {
    stopAllSpeech();
    setIsSpeaking(false);
  }, []);

  return { speak, stop, isSpeaking, error };
}
