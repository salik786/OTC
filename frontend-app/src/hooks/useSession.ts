import { useCallback, useState } from "react";
import { api, type SessionStartResponse } from "../lib/api";
import { collectDeviceInfo, detectPlatform } from "./usePlatformDetect";

export function useSession() {
  const [session, setSession] = useState<SessionStartResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const startSession = useCallback(async (productSlug: string) => {
    setError(null);
    try {
      const platform = detectPlatform();
      const deviceInfo = collectDeviceInfo();
      const started = await api.startSession(platform, productSlug, deviceInfo);
      setSession(started);
      return started;
    } catch {
      setError("Could not start a session. Check the connection and try again.");
      return null;
    }
  }, []);

  const endSession = useCallback(async () => {
    if (!session) return;
    try {
      await api.endSession(session.session_id);
    } catch {
      // Session end failures are non-blocking for the participant - the closing screen still
      // shows. The researcher can reconcile from server logs if needed.
    }
  }, [session]);

  return { session, error, startSession, endSession };
}
