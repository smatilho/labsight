interface ToolCallIndicatorProps {
  tool: string;
}

const toolLabels: Record<string, string> = {
  query_infrastructure_metrics: "Querying BigQuery...",
  search_documents: "Searching documents...",
  bigquery_sql: "Querying BigQuery...",
  vector_retrieval: "Searching documents...",
};

export default function ToolCallIndicator({ tool }: ToolCallIndicatorProps) {
  const label = toolLabels[tool] || `Running ${tool}...`;

  return (
    <div className="flex items-center gap-2 text-xs text-ops-amber mb-2 pl-4">
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-ops-amber animate-pulse" />
      {label}
    </div>
  );
}
