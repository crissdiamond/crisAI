import { CrisaiRuntimeClient } from "@crisai/contracts";

export const apiKeyStorageKey = "crisai_api_key";

export const configuredApiKey =
  import.meta.env.VITE_CRISAI_API_KEY ?? import.meta.env.VITE_CRISAI_API_TOKEN ?? "";

/** The single shared runtime client used across the web app. */
export const runtime = new CrisaiRuntimeClient({
  baseUrl: import.meta.env.VITE_CRISAI_RUNTIME_URL ?? "http://127.0.0.1:8000",
  apiToken: configuredApiKey || localStorage.getItem(apiKeyStorageKey) || undefined
});
