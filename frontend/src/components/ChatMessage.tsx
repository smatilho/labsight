import type { ChatSource } from "@/lib/types";
import SourceCard from "./SourceCard";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  queryMode?: string;
  model?: string;
  latencyMs?: number;
  isStreaming?: boolean;
}

export default function ChatMessage({
  role,
  content,
  sources,
  queryMode,
  model,
  latencyMs,
  isStreaming,
}: ChatMessageProps) {
  const isUser = role === "user";
  const queryModeClass =
    queryMode === "rag"
      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
      : queryMode === "metrics"
        ? "bg-blue-500/20 text-blue-300 border-blue-500/30"
        : queryMode === "hybrid"
          ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
          : "bg-ops-bg text-ops-muted border-ops-border";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? "bg-ops-blue/20 border border-ops-blue/30"
            : "bg-ops-surface border border-ops-border"
        }`}
      >
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {content}
          {isStreaming && <span className="inline-block w-2 h-4 bg-ops-green animate-pulse ml-0.5" />}
        </div>

        {!isUser && !isStreaming && (queryMode || model || latencyMs) && (
          <div className="mt-2 pt-2 border-t border-ops-border/50 flex gap-2 flex-wrap">
            {queryMode && (
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded border ${queryModeClass}`}
              >
                {queryMode}
              </span>
            )}
            {model && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-ops-bg text-ops-muted border border-ops-border">
                {model}
              </span>
            )}
            {latencyMs !== undefined && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-ops-bg text-ops-muted border border-ops-border">
                {latencyMs.toFixed(0)}ms
              </span>
            )}
          </div>
        )}

        {sources && sources.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs text-ops-muted font-medium">Sources</p>
            {sources.map((source) => (
              <SourceCard key={source.index} source={source} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
