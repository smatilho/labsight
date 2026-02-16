"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import DropZone from "@/components/DropZone";
import FileStatus from "@/components/FileStatus";
import StatusBadge from "@/components/StatusBadge";
import type { UploadResponse, UploadStatusResponse } from "@/lib/types";

export default function UploadPage() {
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [fileStatus, setFileStatus] = useState<UploadStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentFiles, setRecentFiles] = useState<UploadStatusResponse[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch recent uploads on mount
  useEffect(() => {
    fetch("/api/upload/recent")
      .then((r) => r.json())
      .then((data) => setRecentFiles(data.files || []))
      .catch(() => {});
  }, []);

  // Type guard for status polling payloads
  function isValidStatusPayload(data: unknown): data is UploadStatusResponse {
    return (
      typeof data === "object" &&
      data !== null &&
      "status" in data &&
      typeof (data as Record<string, unknown>).status === "string" &&
      "file_name" in data &&
      typeof (data as Record<string, unknown>).file_name === "string"
    );
  }

  // Poll for ingestion status after upload
  const startPolling = useCallback((objectName: string) => {
    let attempts = 0;
    const maxAttempts = 20; // 60s at 3s interval

    pollRef.current = setInterval(async () => {
      attempts++;
      try {
        const resp = await fetch(
          `/api/upload/status?file_name=${encodeURIComponent(objectName)}`
        );

        if (!resp.ok) {
          // Non-2xx — stop polling and surface the error
          if (pollRef.current) clearInterval(pollRef.current);
          const body = await resp.text();
          let detail = `Status check failed (HTTP ${resp.status}).`;
          try {
            const parsed = JSON.parse(body);
            if (typeof parsed?.detail === "string") detail = parsed.detail;
          } catch { /* ignore parse errors */ }
          setError(detail);
          return;
        }

        const data: unknown = await resp.json();

        if (!isValidStatusPayload(data)) {
          // Malformed payload — stop polling
          if (pollRef.current) clearInterval(pollRef.current);
          setError("Received an unexpected response while checking status.");
          return;
        }

        setFileStatus(data);

        if (data.status !== "processing" || attempts >= maxAttempts) {
          if (pollRef.current) clearInterval(pollRef.current);
          // Refresh recent list
          fetch("/api/upload/recent")
            .then((r) => r.json())
            .then((d) => setRecentFiles(d.files || []))
            .catch(() => {});
        }
      } catch {
        if (attempts >= maxAttempts && pollRef.current) {
          clearInterval(pollRef.current);
        }
      }
    }, 3000);
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleFileSelected = async (file: File) => {
    setUploading(true);
    setError(null);
    setUploadResult(null);
    setFileStatus(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const resp = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      const data = await resp.json();

      if (!resp.ok) {
        setError(data.detail || "Upload failed.");
        return;
      }

      setUploadResult(data);
      setFileStatus({ file_name: data.object_name, status: "processing" } as UploadStatusResponse);
      startPolling(data.object_name);
    } catch {
      setError("Failed to upload file.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-xl font-bold mb-6">Upload Documents</h1>

      <DropZone onFileSelected={handleFileSelected} disabled={uploading} />

      {uploading && (
        <div className="flex items-center gap-2 mt-4 text-sm text-ops-amber">
          <span className="inline-block w-2 h-2 rounded-full bg-ops-amber animate-pulse" />
          Uploading...
        </div>
      )}

      {error && <FileStatus fileName="" status={null} error={error} />}

      {uploadResult && fileStatus && (
        <FileStatus fileName={uploadResult.file_name} status={fileStatus} />
      )}

      {/* Recent ingestions */}
      {recentFiles.length > 0 && (
        <div className="mt-8">
          <h2 className="text-sm font-medium text-ops-muted mb-3 uppercase tracking-wider">
            Recent Ingestions
          </h2>
          <div className="bg-ops-surface border border-ops-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ops-border">
                  <th className="px-3 py-2 text-left text-xs text-ops-muted font-medium">File</th>
                  <th className="px-3 py-2 text-left text-xs text-ops-muted font-medium">Status</th>
                  <th className="px-3 py-2 text-left text-xs text-ops-muted font-medium">Chunks</th>
                  <th className="px-3 py-2 text-left text-xs text-ops-muted font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {recentFiles.map((f, i) => (
                  <tr key={i} className="border-b border-ops-border/50">
                    <td className="px-3 py-2 font-mono text-xs truncate max-w-[200px]">
                      {f.file_name}
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={f.status} />
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{f.chunk_count ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {f.total_time_ms ? `${f.total_time_ms.toFixed(0)}ms` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
