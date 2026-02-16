/**
 * Server-side fetch wrapper for proxying requests to the RAG backend.
 *
 * Supports two auth modes (set via BACKEND_AUTH_MODE env var):
 * - "id_token" (default): Uses google-auth-library to obtain an ID token
 *   for direct Cloud Run invocation. Skipped for localhost URLs.
 * - "api_key": Sends an API key in the x-api-key header for API Gateway.
 *   The key is read from BACKEND_API_KEY env var (populated from Secret Manager).
 */

import { GoogleAuth } from "google-auth-library";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";
const AUTH_MODE = process.env.BACKEND_AUTH_MODE || "id_token";
const API_KEY = process.env.BACKEND_API_KEY || "";

let auth: GoogleAuth | null = null;

function getAuth(): GoogleAuth {
  if (!auth) {
    auth = new GoogleAuth();
  }
  return auth;
}

function isLocalhost(): boolean {
  return (
    BACKEND_URL.startsWith("http://localhost") ||
    BACKEND_URL.startsWith("http://127.0.0.1")
  );
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  // Skip auth for local development
  if (isLocalhost()) {
    return {};
  }

  if (AUTH_MODE === "api_key") {
    if (!API_KEY) {
      console.error("BACKEND_AUTH_MODE is api_key but BACKEND_API_KEY is not set");
      return {};
    }
    return { "x-api-key": API_KEY };
  }

  // Default: id_token mode
  try {
    const client = await getAuth().getIdTokenClient(BACKEND_URL);
    const headers = await client.getRequestHeaders();
    return headers as Record<string, string>;
  } catch (err) {
    console.error("Failed to get ID token:", err);
    return {};
  }
}

/**
 * Proxy a request to the backend with auth headers.
 * Returns the raw Response for streaming or JSON handling.
 */
export async function backendFetch(
  path: string,
  init?: RequestInit
): Promise<Response> {
  const authHeaders = await getAuthHeaders();
  const url = `${BACKEND_URL}${path}`;

  return fetch(url, {
    ...init,
    headers: {
      ...authHeaders,
      ...init?.headers,
    },
  });
}
