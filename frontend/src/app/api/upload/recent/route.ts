import { backendFetch } from "@/lib/backend";

export const runtime = "nodejs";

export async function GET() {
  const backendResponse = await backendFetch("/api/upload/recent");
  const data = await backendResponse.json();
  return Response.json(data, { status: backendResponse.status });
}
