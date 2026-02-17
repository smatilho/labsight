import "@testing-library/jest-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import ChatMessage from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import DataTable from "@/components/DataTable";
import DropZone from "@/components/DropZone";
import FileStatus from "@/components/FileStatus";
import ToolCallIndicator from "@/components/ToolCallIndicator";
import SourceCard from "@/components/SourceCard";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Services" value="5/5" />);
    expect(screen.getByText("Services")).toBeInTheDocument();
    expect(screen.getByText("5/5")).toBeInTheDocument();
  });

  it("renders subtext when provided", () => {
    render(<MetricCard label="Test" value={42} subtext="7-day average" />);
    expect(screen.getByText("7-day average")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("renders the status text", () => {
    render(<StatusBadge status="up" />);
    expect(screen.getByText("up")).toBeInTheDocument();
  });

  it("renders error status", () => {
    render(<StatusBadge status="error" />);
    expect(screen.getByText("error")).toBeInTheDocument();
  });
});

describe("ChatMessage", () => {
  it("renders user message", () => {
    render(<ChatMessage role="user" content="Hello" />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("renders assistant message with metadata", () => {
    render(
      <ChatMessage
        role="assistant"
        content="Here is the answer"
        queryMode="rag"
        model="gemini"
        latencyMs={1500}
      />
    );
    expect(screen.getByText("Here is the answer")).toBeInTheDocument();
    expect(screen.getByText("rag")).toBeInTheDocument();
    expect(screen.getByText("gemini")).toBeInTheDocument();
    expect(screen.getByText("1500ms")).toBeInTheDocument();
  });
});

describe("ChatInput", () => {
  it("calls onSubmit with trimmed value", () => {
    const onSubmit = jest.fn();
    render(<ChatInput onSubmit={onSubmit} />);

    const textarea = screen.getByPlaceholderText("Ask about your homelab...");
    fireEvent.change(textarea, { target: { value: "  test query  " } });
    fireEvent.click(screen.getByText("Send"));

    expect(onSubmit).toHaveBeenCalledWith("test query");
  });

  it("does not submit empty input", () => {
    const onSubmit = jest.fn();
    render(<ChatInput onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText("Send"));
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("DataTable", () => {
  it("renders column headers and rows", () => {
    render(
      <DataTable
        columns={["Name", "Value"]}
        rows={[{ Name: "test", Value: "42" }]}
      />
    );
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("test")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders empty message when no rows", () => {
    render(<DataTable columns={["A"]} rows={[]} emptyMessage="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
});

describe("DropZone", () => {
  it("renders drop zone text", () => {
    render(<DropZone onFileSelected={jest.fn()} />);
    expect(screen.getByText(/Drop a file here/)).toBeInTheDocument();
  });

  it("shows error for invalid extension", () => {
    const onFileSelected = jest.fn();
    render(<DropZone onFileSelected={onFileSelected} />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["content"], "test.exe", { type: "application/octet-stream" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(screen.getByText(/\.exe.*not supported/)).toBeInTheDocument();
    expect(onFileSelected).not.toHaveBeenCalled();
  });
});

describe("FileStatus", () => {
  it("renders error state", () => {
    render(<FileStatus fileName="test.md" status={null} error="Upload failed" />);
    expect(screen.getByText("Upload failed")).toBeInTheDocument();
  });

  it("renders processing state", () => {
    render(
      <FileStatus
        fileName="test.md"
        status={{ file_name: "test.md", status: "processing", file_type: null, chunk_count: null, chunks_sanitized: null, total_time_ms: null, error_message: null, timestamp: null }}
      />
    );
    expect(screen.getByText(/Processing/)).toBeInTheDocument();
  });

  it("renders success state with metrics", () => {
    render(
      <FileStatus
        fileName="test.md"
        status={{ file_name: "test.md", status: "success", file_type: "md", chunk_count: 5, chunks_sanitized: 2, total_time_ms: 800, error_message: null, timestamp: null }}
      />
    );
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("800ms")).toBeInTheDocument();
  });
});

describe("ToolCallIndicator", () => {
  it("shows BigQuery label", () => {
    render(<ToolCallIndicator tool="bigquery_sql" />);
    expect(screen.getByText("Querying BigQuery...")).toBeInTheDocument();
  });

  it("shows generic label for unknown tool", () => {
    render(<ToolCallIndicator tool="custom_tool" />);
    expect(screen.getByText("Running custom_tool...")).toBeInTheDocument();
  });
});

describe("SourceCard", () => {
  it("falls back to filename when source is missing", () => {
    render(
      <SourceCard
        source={{
          index: 1,
          similarity_score: 0.62,
          content: "content",
          metadata: { filename: "uploads/2026/02/16/guide.md" },
        }}
      />
    );

    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("guide.md")).toBeInTheDocument();
  });

  it("uses 1-based source index from backend as-is", () => {
    render(
      <SourceCard
        source={{
          index: 3,
          similarity_score: 0.5,
          content: "content",
          metadata: { source: "docs.md" },
        }}
      />
    );

    expect(screen.getByText("#3")).toBeInTheDocument();
    expect(screen.queryByText("#4")).not.toBeInTheDocument();
  });
});
