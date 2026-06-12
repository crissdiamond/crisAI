import { type UiEvent } from "@crisai/contracts";

/**
 * Maps a thrown failure to a single, human-readable sentence for the error region.
 *
 * Recognises the runtime client's `crisAI runtime request failed (NNN): {body}`
 * envelope, fetch/network TypeErrors, and authentication failures, and otherwise
 * cleans the raw message (dropping the status prefix and any JSON `detail` wrapper).
 */
export function humanizeError(reason: unknown): string {
  const raw =
    reason instanceof Error ? reason.message : typeof reason === "string" ? reason : String(reason);

  // Network / unreachable server: fetch rejects with a TypeError ("Failed to fetch").
  if (
    (reason instanceof TypeError && /fetch/i.test(raw)) ||
    /failed to fetch|networkerror|load failed/i.test(raw)
  ) {
    return "Can't reach the crisAI server. Is it running?";
  }

  // Authentication: the runtime returns 401 with {"detail":"Unauthorized"}.
  if (/\(401\)/.test(raw) || /unauthorized/i.test(raw)) {
    return "Add or check your API key to use crisAI.";
  }

  return cleanRuntimeMessage(raw);
}

/** Strips the runtime status prefix and JSON wrapper, leaving readable text. */
function cleanRuntimeMessage(raw: string): string {
  let message = raw.replace(/^crisAI runtime request failed \(\d+\):\s*/i, "").trim();
  // Unwrap a JSON error body such as {"detail":"..."} down to its message.
  if (message.startsWith("{")) {
    try {
      const parsed = JSON.parse(message) as Record<string, unknown>;
      const detail = parsed.detail ?? parsed.message ?? parsed.error;
      if (typeof detail === "string" && detail.trim()) {
        message = detail.trim();
      }
    } catch {
      // Leave the raw body in place if it is not valid JSON.
    }
  }
  return message || "Something went wrong. Please try again.";
}

/** True when the failure points at a missing or invalid API key. */
export function isAuthError(reason: unknown): boolean {
  const raw =
    reason instanceof Error ? reason.message : typeof reason === "string" ? reason : String(reason);
  return /\(401\)/.test(raw) || /unauthorized/i.test(raw);
}

export function formatRecallScore(score: number): string {
  return Number.isInteger(score) ? String(score) : score.toFixed(2);
}

export function dedupeEvents(items: UiEvent[]): UiEvent[] {
  const seen = new Set<string>();
  return items.filter((event) => {
    const key = `${event.event_type}-${event.timestamp}-${event.agent_id ?? ""}-${event.stage ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  }
  if (typeof value === "string" && value.trim()) {
    return [value];
  }
  return [];
}

/** Reads a File as a base64-encoded string for workspace uploads. */
export async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.slice(index, index + chunkSize));
  }
  return btoa(binary);
}
