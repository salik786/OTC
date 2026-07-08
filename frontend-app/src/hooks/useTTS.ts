import { useCallback, useRef, useState } from "react";
import { api } from "../lib/api";

/** Plays TTS audio from the backend proxy (not native SpeechSynthesis) so voice output stays
 * consistent across tablet/mobile/desktop and reusable by a future Android client. */
export function useTTS() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const speak = useCallback(async (text: string) => {
    setError(null);
    try {
      audioRef.current?.pause();
      const blob = await api.speak(text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      setIsSpeaking(true);
      audio.onended = () => {
        setIsSpeaking(false);
        URL.revokeObjectURL(url);
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
    audioRef.current?.pause();
    setIsSpeaking(false);
  }, []);

  return { speak, stop, isSpeaking, error };
}
