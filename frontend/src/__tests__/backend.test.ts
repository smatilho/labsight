/**
 * Tests for the backend fetch wrapper auth mode switching.
 *
 * @jest-environment node
 */

// We need to test the actual backend.ts module with different env vars.
// Since Node caches modules, we use jest.isolateModules for each test.

const mockGetRequestHeaders = jest.fn().mockResolvedValue({
  Authorization: "Bearer mock-id-token",
});
const mockGetIdTokenClient = jest.fn().mockResolvedValue({
  getRequestHeaders: mockGetRequestHeaders,
});

jest.mock("google-auth-library", () => ({
  GoogleAuth: jest.fn().mockImplementation(() => ({
    getIdTokenClient: mockGetIdTokenClient,
  })),
}));

// Save and restore env between tests
const originalEnv = { ...process.env };

afterEach(() => {
  process.env = { ...originalEnv };
  jest.resetModules();
  mockGetIdTokenClient.mockClear();
  mockGetRequestHeaders.mockClear();
});

describe("backend auth modes", () => {
  it("uses id_token mode by default on non-localhost URL", async () => {
    process.env.BACKEND_URL = "https://rag-service.run.app";
    process.env.BACKEND_AUTH_MODE = "id_token";
    delete process.env.BACKEND_API_KEY;

    const fetchSpy = jest.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );

    const { backendFetch } = await import("@/lib/backend");
    await backendFetch("/api/health");

    expect(mockGetIdTokenClient).toHaveBeenCalledWith("https://rag-service.run.app");
    expect(fetchSpy).toHaveBeenCalledWith(
      "https://rag-service.run.app/api/health",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer mock-id-token",
        }),
      })
    );

    fetchSpy.mockRestore();
  });

  it("uses api_key mode when BACKEND_AUTH_MODE=api_key", async () => {
    process.env.BACKEND_URL = "https://gateway.apigateway.run.app";
    process.env.BACKEND_AUTH_MODE = "api_key";
    process.env.BACKEND_API_KEY = "test-api-key-123";

    const fetchSpy = jest.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );

    const { backendFetch } = await import("@/lib/backend");
    await backendFetch("/api/health");

    // Should NOT use GoogleAuth
    expect(mockGetIdTokenClient).not.toHaveBeenCalled();

    // Should send x-api-key header
    expect(fetchSpy).toHaveBeenCalledWith(
      "https://gateway.apigateway.run.app/api/health",
      expect.objectContaining({
        headers: expect.objectContaining({
          "x-api-key": "test-api-key-123",
        }),
      })
    );

    fetchSpy.mockRestore();
  });

  it("skips all auth for localhost URLs regardless of mode", async () => {
    process.env.BACKEND_URL = "http://localhost:8080";
    process.env.BACKEND_AUTH_MODE = "api_key";
    process.env.BACKEND_API_KEY = "should-not-be-sent";

    const fetchSpy = jest.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );

    const { backendFetch } = await import("@/lib/backend");
    await backendFetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "test" }),
    });

    expect(mockGetIdTokenClient).not.toHaveBeenCalled();

    // Headers should NOT include x-api-key or Authorization
    const calledHeaders = (fetchSpy.mock.calls[0][1] as RequestInit).headers as Record<string, string>;
    expect(calledHeaders).not.toHaveProperty("x-api-key");
    expect(calledHeaders).not.toHaveProperty("Authorization");
    expect(calledHeaders["Content-Type"]).toBe("application/json");

    fetchSpy.mockRestore();
  });

  it("logs error when api_key mode but BACKEND_API_KEY not set", async () => {
    process.env.BACKEND_URL = "https://gateway.run.app";
    process.env.BACKEND_AUTH_MODE = "api_key";
    delete process.env.BACKEND_API_KEY;

    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    const fetchSpy = jest.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );

    const { backendFetch } = await import("@/lib/backend");
    await backendFetch("/api/health");

    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining("BACKEND_API_KEY is not set")
    );

    // Should still make the request (graceful degradation), just without auth
    expect(fetchSpy).toHaveBeenCalled();

    consoleSpy.mockRestore();
    fetchSpy.mockRestore();
  });
});
