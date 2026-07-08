import type { DeviceInfo, Platform } from "../lib/api";

/** Breakpoints tuned for the study's three targets: mobile browser, tablet kiosk (primary),
 * desktop browser. Touch capability alone isn't reliable (many desktops have touchscreens), so
 * width is the primary signal, matching how the responsive layout itself breaks. */
export function detectPlatform(): Platform {
  const width = window.innerWidth;
  if (width < 640) return "mobile_web";
  if (width < 1280) return "tablet_web";
  return "desktop_web";
}

export function collectDeviceInfo(): DeviceInfo {
  return {
    user_agent: navigator.userAgent,
    screen_width: window.innerWidth,
    screen_height: window.innerHeight,
  };
}
