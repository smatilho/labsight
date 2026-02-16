"use client";

import { useState, useRef, useCallback } from "react";

const ALLOWED_EXTENSIONS = new Set([
  "md", "yaml", "yml", "json", "txt", "conf", "cfg", "ini",
  "toml", "dockerfile", "sh", "xml", "csv", "properties",
]);
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

interface DropZoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function DropZone({ onFileSelected, disabled = false }: DropZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndSelect = useCallback(
    (file: File) => {
      setError(null);

      const ext = file.name.split(".").pop()?.toLowerCase() || "";
      if (!ALLOWED_EXTENSIONS.has(ext)) {
        setError(`File type '.${ext}' is not supported.`);
        return;
      }

      if (file.size > MAX_SIZE) {
        setError("File exceeds maximum size of 10 MB.");
        return;
      }

      onFileSelected(file);
    },
    [onFileSelected]
  );

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;

    const file = e.dataTransfer.files[0];
    if (file) validateAndSelect(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) validateAndSelect(file);
    // Reset so the same file can be re-selected
    e.target.value = "";
  };

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${dragOver ? "border-ops-green bg-ops-green/5" : "border-ops-border hover:border-ops-muted"}
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <p className="text-ops-muted text-sm">
          Drop a file here or <span className="text-ops-green">click to browse</span>
        </p>
        <p className="text-ops-muted/60 text-xs mt-2">
          Supports: .md, .yaml, .json, .txt, .conf, .sh, and more (max 10 MB)
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        onChange={handleChange}
        className="hidden"
      />

      {error && (
        <p className="mt-2 text-xs text-ops-red">{error}</p>
      )}
    </div>
  );
}
