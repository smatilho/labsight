import { backendFetch } from "@/lib/backend";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const formData = await request.formData();

  const backendResponse = await backendFetch("/api/upload", {
    method: "POST",
    body: formData,
  });

  const data = await backendResponse.json();
  return Response.json(data, { status: backendResponse.status });
}
