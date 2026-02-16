"use client";

import { useState, useRef, useEffect } from "react";

interface ChatInputProps {
  onSubmit: (query: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSubmit, disabled = false }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex gap-2 items-end">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Ask about your homelab..."
        rows={1}
        className="flex-1 resize-none bg-ops-surface border border-ops-border rounded-lg px-4 py-3 text-sm
                   text-ops-text placeholder:text-ops-muted focus:outline-none focus:border-ops-blue
                   disabled:opacity-50"
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        className="px-4 py-3 bg-ops-green text-white rounded-lg text-sm font-medium
                   hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed
                   transition-colors"
      >
        Send
      </button>
    </div>
  );
}
