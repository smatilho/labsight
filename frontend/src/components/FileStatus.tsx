import type { UploadStatusResponse } from "@/lib/types";
import StatusBadge from "./StatusBadge";

interface FileStatusProps {
  fileName: string;
  status: UploadStatusResponse | null;
  error?: string | null;
}

export default function FileStatus({ fileName, status, error }: FileStatusProps) {
  if (error) {
    return (
      <div className="bg-ops-surface border border-ops-red/30 rounded-lg p-4 mt-4">
        <p className="text-sm text-ops-red">{error}</p>
      </div>
    );
  }

  if (!status) return null;

  return (
    <div className="bg-ops-surface border border-ops-border rounded-lg p-4 mt-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-mono text-ops-text truncate">{fileName}</span>
        <StatusBadge status={status.status} />
      </div>

      {status.status === "processing" && (
        <div className="flex items-center gap-2 text-xs text-ops-amber">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-ops-amber animate-pulse" />
          Processing... Ingestion pipeline is running.
        </div>
      )}

      {status.status === "success" && (
        <div className="grid grid-cols-3 gap-3 mt-2">
          <div>
            <p className="text-[10px] uppercase text-ops-muted">Chunks</p>
            <p className="text-sm font-mono text-ops-green">{status.chunk_count}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase text-ops-muted">Sanitized</p>
            <p className="text-sm font-mono text-ops-amber">{status.chunks_sanitized ?? 0}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase text-ops-muted">Time</p>
            <p className="text-sm font-mono">{status.total_time_ms?.toFixed(0)}ms</p>
          </div>
        </div>
      )}

      {status.status === "error" && status.error_message && (
        <p className="text-xs text-ops-red mt-1">{status.error_message}</p>
      )}
    </div>
  );
}
