import { useCallback, useRef, useState } from "react";
import { api } from "../lib/api";

type Status = "idle" | "recording" | "transcribing" | "error";

/** Records audio with MediaRecorder and sends it to the backend Whisper proxy - not the browser's
 * native SpeechRecognition, so behavior (and availability) is consistent across Safari/Chrome and
 * reusable by a future Android client. */
export function useSTT() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.start();
      recorderRef.current = recorder;
      setStatus("recording");
    } catch {
      setStatus("error");
      setError("Microphone access was denied or is unavailable. Please type your question instead.");
    }
  }, []);

  const stop = useCallback((): Promise<string | null> => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        resolve(null);
        return;
      }
      recorder.onstop = async () => {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        setStatus("transcribing");
        try {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          const transcript = await api.stt(blob);
          setStatus("idle");
          resolve(transcript);
        } catch {
          setStatus("error");
          setError("Couldn't understand that. Please try again or type your question.");
          resolve(null);
        }
      };
      recorder.stop();
    });
  }, []);

  const cancel = useCallback(() => {
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setStatus("idle");
  }, []);

  return { start, stop, cancel, status, error };
}
