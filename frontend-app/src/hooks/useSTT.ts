import { useCallback, useRef, useState } from "react";
import { api } from "../lib/api";

type Status = "idle" | "recording" | "transcribing" | "error";

const SILENCE_RMS_THRESHOLD = 0.02;
const SILENCE_DURATION_MS = 1300;
const MIN_RECORDING_MS = 500;

/** Records audio with MediaRecorder and sends it to the backend transcription proxy - not the
 * browser's native SpeechRecognition, so behavior (and availability) is consistent across
 * Safari/Chrome and reusable by a future Android client.
 *
 * Auto-stops on sustained silence (voice activity detection via an AnalyserNode) rather than
 * requiring the participant to tap the mic a second time - matches how voice assistants actually
 * behave instead of a manual record/stop toggle. */
export function useSTT() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const silenceTimerRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const onSilenceRef = useRef<(() => void) | null>(null);
  const silenceFiredRef = useRef(false);

  const cleanupAudioAnalysis = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    if (silenceTimerRef.current !== null) window.clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
  }, []);

  /** onSilence fires once when sustained silence is detected - the caller decides what to do
   * (typically: stop recording and submit), this hook only detects it. */
  const start = useCallback(async (onSilence?: () => void) => {
    setError(null);
    silenceFiredRef.current = false;
    onSilenceRef.current = onSilence ?? null;
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
      startTimeRef.current = Date.now();
      setStatus("recording");

      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      const data = new Uint8Array(analyser.fftSize);

      const checkVolume = () => {
        analyser.getByteTimeDomainData(data);
        let sumSquares = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sumSquares += v * v;
        }
        const rms = Math.sqrt(sumSquares / data.length);
        const elapsed = Date.now() - startTimeRef.current;

        if (rms < SILENCE_RMS_THRESHOLD && elapsed > MIN_RECORDING_MS) {
          if (silenceTimerRef.current === null) {
            silenceTimerRef.current = window.setTimeout(() => {
              if (!silenceFiredRef.current) {
                silenceFiredRef.current = true;
                onSilenceRef.current?.();
              }
            }, SILENCE_DURATION_MS);
          }
        } else if (silenceTimerRef.current !== null) {
          window.clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
        rafRef.current = requestAnimationFrame(checkVolume);
      };
      rafRef.current = requestAnimationFrame(checkVolume);
    } catch {
      setStatus("error");
      setError("Microphone access was denied or is unavailable. Please type your question instead.");
    }
  }, []);

  const stop = useCallback((): Promise<string | null> => {
    return new Promise((resolve) => {
      cleanupAudioAnalysis();
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
  }, [cleanupAudioAnalysis]);

  const cancel = useCallback(() => {
    cleanupAudioAnalysis();
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setStatus("idle");
  }, [cleanupAudioAnalysis]);

  return { start, stop, cancel, status, error };
}
