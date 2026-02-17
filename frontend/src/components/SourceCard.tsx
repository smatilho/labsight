"use client";

import { useState } from "react";
import type { ChatSource } from "@/lib/types";

interface SourceCardProps {
  source: ChatSource;
}

export default function SourceCard({ source }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false);
  const rawLabel =
    source.metadata.source || source.metadata.filename || "unknown source";
  const label =
    typeof rawLabel === "string"
      ? rawLabel.split("/").pop() || rawLabel
      : "unknown source";

  return (
    <div className="border border-ops-border/50 rounded bg-ops-bg p-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left text-xs"
      >
        <span className="text-ops-muted">#{source.index}</span>
        <span className="text-ops-green font-mono">
          {(source.similarity_score * 100).toFixed(0)}%
        </span>
        <span className="text-ops-muted truncate flex-1">
          {label}
        </span>
        <span className="text-ops-muted">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <p className="mt-2 text-xs text-ops-muted leading-relaxed whitespace-pre-wrap">
          {source.content}
        </p>
      )}
    </div>
  );
}
