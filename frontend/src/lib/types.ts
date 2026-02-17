/** TypeScript interfaces matching the backend API contracts. */

// --- Chat ---

export interface ChatRequest {
  query: string;
  stream: boolean;
}

export interface ChatSource {
  index: number;
  content: string;
  similarity_score: number;
  metadata: Record<string, string | number | boolean | null>;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  model: string;
  latency_ms: number;
  retrieval_count: number;
  query_mode: "rag" | "metrics" | "hybrid";
}

/** SSE event types emitted by the streaming chat endpoint. */
export type SSEEventType = "token" | "tool_call" | "tool_result" | "sources" | "done" | "error";

export interface SSEEvent {
  type: SSEEventType;
  content?: string;
  tool?: string;
  result?: string;
  sources?: ChatSource[];
  model?: string;
  latency_ms?: number;
  query_mode?: string;
  message?: string;
  retrieval_count?: number;
}

// --- Upload ---

export interface UploadResponse {
  file_name: string;
  object_name: string;
  bucket: string;
  size_bytes: number;
  status: string;
}

export interface UploadStatusResponse {
  file_name: string;
  file_type: string | null;
  status: "processing" | "success" | "error";
  chunk_count: number | null;
  chunks_sanitized: number | null;
  total_time_ms: number | null;
  error_message: string | null;
  timestamp: string | null;
}

export interface RecentUploadsResponse {
  files: UploadStatusResponse[];
}

// --- Dashboard ---

export interface ServiceHealth {
  service_name: string;
  status: string;
  response_time_ms: number;
  checked_at: string;
}

export interface UptimeSummary {
  service_name: string;
  uptime_percent: number;
  total_checks: number;
  avg_response_ms: number;
}

export interface ResourceUtilization {
  node: string;
  cpu_percent: number;
  memory_percent: number;
  storage_percent: number;
  collected_at: string;
}

export interface QueryActivity {
  query_date: string;
  total_queries: number;
  successful: number;
  failed: number;
  avg_latency_ms: number;
  rag_queries: number;
  metrics_queries: number;
  hybrid_queries: number;
}

export interface RecentIngestion {
  file_name: string;
  file_type: string;
  status: string;
  chunk_count: number;
  total_time_ms: number;
  timestamp: string;
}

export interface DashboardOverview {
  service_health: ServiceHealth[];
  uptime_summary: UptimeSummary[];
  resource_utilization: ResourceUtilization[];
  query_activity: QueryActivity[];
  recent_ingestions: RecentIngestion[];
}
