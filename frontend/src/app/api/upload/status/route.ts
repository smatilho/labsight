import { backendFetch } from "@/lib/backend";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const fileName = searchParams.get("file_name");

  if (!fileName) {
    return Response.json({ detail: "file_name parameter is required." }, { status: 400 });
  }

  const backendResponse = await backendFetch(
    `/api/upload/status?file_name=${encodeURIComponent(fileName)}`
  );

  const data = await backendResponse.json();
  return Response.json(data, { status: backendResponse.status });
}
