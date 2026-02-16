/**
 * Route handler tests.
 *
 * These test the API proxy route handlers by mocking the backend fetch
 * and verifying correct pass-through behavior.
 *
 * @jest-environment node
 */

// Mock the backend module before importing routes
jest.mock("@/lib/backend", () => ({
  backendFetch: jest.fn(),
}));

import { backendFetch } from "@/lib/backend";
import { GET as healthGet } from "@/app/api/health/route";

const mockBackendFetch = backendFetch as jest.MockedFunction<typeof backendFetch>;

describe("GET /api/health", () => {
  it("returns ok without calling backend", async () => {
    const response = await healthGet();
    const data = await response.json();
    expect(data).toEqual({ status: "ok" });
    expect(mockBackendFetch).not.toHaveBeenCalled();
  });
});

describe("POST /api/chat", () => {
  it("proxies non-streaming request", async () => {
    const { POST } = await import("@/app/api/chat/route");

    mockBackendFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ answer: "test", sources: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const request = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "hello", stream: false }),
    });

    const response = await POST(request);
    const data = await response.json();
    expect(data.answer).toBe("test");
    expect(response.status).toBe(200);
  });

  it("passes through streaming response", async () => {
    const { POST } = await import("@/app/api/chat/route");

    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"type":"token","content":"hi"}\n\n'));
        controller.close();
      },
    });

    mockBackendFetch.mockResolvedValueOnce(
      new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      })
    );

    const request = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "hello", stream: true }),
    });

    const response = await POST(request);
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("text/event-stream");
  });
});

describe("GET /api/upload/status", () => {
  it("proxies status request with file_name", async () => {
    const { GET } = await import("@/app/api/upload/status/route");

    mockBackendFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ file_name: "test.md", status: "success" }), {
        status: 200,
      })
    );

    const request = new Request("http://localhost/api/upload/status?file_name=test.md");
    const response = await GET(request);
    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data.status).toBe("success");
  });

  it("returns 400 when file_name missing", async () => {
    const { GET } = await import("@/app/api/upload/status/route");

    const request = new Request("http://localhost/api/upload/status");
    const response = await GET(request);
    expect(response.status).toBe(400);
  });
});

describe("GET /api/dashboard/overview", () => {
  it("proxies dashboard request", async () => {
    const { GET } = await import("@/app/api/dashboard/overview/route");

    mockBackendFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          service_health: [],
          uptime_summary: [],
          resource_utilization: [],
          query_activity: [],
          recent_ingestions: [],
        }),
        { status: 200 }
      )
    );

    const response = await GET();
    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.service_health).toEqual([]);
  });
});
