import { backendFetch } from "@/lib/backend";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const body = await request.json();

  const backendResponse = await backendFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  // If streaming and backend returned 200, pipe the SSE stream through
  if (body.stream && backendResponse.ok && backendResponse.body) {
    return new Response(backendResponse.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  }

  // Non-streaming or error: return JSON
  const data = await backendResponse.json();
  return Response.json(data, { status: backendResponse.status });
}
