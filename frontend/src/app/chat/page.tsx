"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import ChatMessage from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import ToolCallIndicator from "@/components/ToolCallIndicator";
import type { ChatSource, SSEEvent } from "@/lib/types";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  queryMode?: string;
  model?: string;
  latencyMs?: number;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeTool]);

  const handleSubmit = useCallback(async (query: string) => {
    const userMessage: Message = { role: "user", content: query };
    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);
    setActiveTool(null);

    // Add empty assistant message to fill in
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, stream: true }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: "Request failed" }));
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            role: "assistant",
            content: err.error?.message || err.detail || "An error occurred.",
          };
          return updated;
        });
        setIsStreaming(false);
        return;
      }

      const reader = resp.body?.getReader();
      if (!reader) {
        setIsStreaming(false);
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const json = line.slice(6).trim();
          if (!json) continue;

          let event: SSEEvent;
          try {
            event = JSON.parse(json);
          } catch {
            continue;
          }

          if (event.type === "token" && event.content) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, content: last.content + event.content };
              return updated;
            });
          } else if (event.type === "tool_call") {
            setActiveTool(event.tool || null);
          } else if (event.type === "tool_result") {
            setActiveTool(null);
          } else if (event.type === "sources" && Array.isArray(event.sources)) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = {
                ...last,
                sources: event.sources,
              };
              return updated;
            });
          } else if (event.type === "done") {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = {
                ...last,
                queryMode: event.query_mode,
                model: event.model,
                latencyMs: event.latency_ms,
              };
              return updated;
            });
          } else if (event.type === "error") {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = {
                ...last,
                content: last.content || event.message || "An error occurred.",
              };
              return updated;
            });
          }
        }
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: "Failed to connect to the backend.",
        };
        return updated;
      });
    } finally {
      setIsStreaming(false);
      setActiveTool(null);
    }
  }, []);

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      <div className="flex-1 overflow-y-auto p-4 max-w-4xl mx-auto w-full">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-ops-muted">
            <div className="text-center">
              <p className="text-lg mb-2">labsight</p>
              <p className="text-sm">Ask about your homelab docs or infrastructure metrics.</p>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            <ChatMessage
              role={msg.role}
              content={msg.content}
              sources={msg.sources}
              queryMode={msg.queryMode}
              model={msg.model}
              latencyMs={msg.latencyMs}
              isStreaming={isStreaming && i === messages.length - 1 && msg.role === "assistant"}
            />
          </div>
        ))}

        {activeTool && <ToolCallIndicator tool={activeTool} />}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-ops-border p-4 max-w-4xl mx-auto w-full">
        <ChatInput onSubmit={handleSubmit} disabled={isStreaming} />
      </div>
    </div>
  );
}
