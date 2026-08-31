import { useEffect, useRef } from "react";

/** Soft, synthesized "thinking" pulse played while waiting for the backend to answer - there was
 * previously no audio feedback during this wait at all, so a voice-only participant had no signal
 * anything was happening. Generated in the Web Audio API (no audio asset to ship/host) as a low,
 * gentle two-tone pulse, quiet enough not to compete with TTS or feel alarm-like. */
function startTone(ctx: AudioContext): () => void {
  const master = ctx.createGain();
  master.gain.value = 0.05;
  master.connect(ctx.destination);

  const PULSE_INTERVAL_S = 0.9;
  const PULSE_DURATION_S = 0.22;
  let stopped = false;
  let timer: number;

  function pulse() {
    if (stopped) return;
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(392, now); // G4
    osc.frequency.setValueAtTime(494, now + PULSE_DURATION_S * 0.55); // B4
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(1, now + PULSE_DURATION_S * 0.25);
    gain.gain.linearRampToValueAtTime(0, now + PULSE_DURATION_S);
    osc.connect(gain);
    gain.connect(master);
    osc.start(now);
    osc.stop(now + PULSE_DURATION_S);
    timer = window.setTimeout(pulse, PULSE_INTERVAL_S * 1000);
  }

  pulse();

  return () => {
    stopped = true;
    window.clearTimeout(timer);
    master.disconnect();
  };
}

/** Plays the thinking pulse for as long as `active` is true. Safe to call from multiple screens -
 * each mount owns its own AudioContext and cleans it up on unmount or when `active` goes false. */
export function useThinkingTone(active: boolean) {
  const stopRef = useRef<(() => void) | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (active) {
      const ctx = new AudioContext();
      ctxRef.current = ctx;
      stopRef.current = startTone(ctx);
    }
    return () => {
      stopRef.current?.();
      stopRef.current = null;
      ctxRef.current?.close().catch(() => {});
      ctxRef.current = null;
    };
  }, [active]);
}
