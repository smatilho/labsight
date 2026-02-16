/**
 * Server-side fetch wrapper for proxying requests to the RAG backend.
 *
 * When running on Cloud Run, uses google-auth-library to obtain an ID token
 * for the backend URL. When running locally (http://localhost), skips auth.
 */

import { GoogleAuth } from "google-auth-library";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

let auth: GoogleAuth | null = null;

function getAuth(): GoogleAuth {
  if (!auth) {
    auth = new GoogleAuth();
  }
  return auth;
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  // Skip auth for local development
  if (BACKEND_URL.startsWith("http://localhost") || BACKEND_URL.startsWith("http://127.0.0.1")) {
    return {};
  }

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
