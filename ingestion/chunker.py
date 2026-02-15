"""File-type-aware document chunking for the ingestion pipeline.

Different file types need different chunking strategies:
- Markdown/prose: semantic chunking by headers, with overlap so context
  isn't lost at chunk boundaries
- YAML/docker-compose: chunk by top-level key so service definitions
  stay intact
- Config files (INI-style): chunk by [section] to keep related settings
  grouped
- Fallback: sliding window with overlap for anything else

Target chunk size is ~500 chars (Vertex AI text-embedding-004 works well
with chunks in the 200-600 char range). Overlap is 100 chars for prose.
"""

import re
from dataclasses import dataclass, field
from pathlib import PurePath

import yaml


@dataclass
class Chunk:
    """A single chunk of a document with metadata."""

    text: str
    metadata: dict[str, str | int] = field(default_factory=dict)


# File extension → strategy name
_EXTENSION_MAP: dict[str, str] = {
    ".md": "markdown",
    ".txt": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".conf": "config",
    ".ini": "config",
    ".cfg": "config",
}

# Header pattern for markdown splitting
_MD_HEADER = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# INI-style section header
_INI_SECTION = re.compile(r"^\[([^\]]+)\]", re.MULTILINE)


class DocumentChunker:
    """Chunks documents using file-type-aware strategies."""

    def __init__(self, target_size: int = 500, overlap: int = 100) -> None:
        self.target_size = target_size
        self.overlap = overlap

    def chunk(self, text: str, filename: str) -> list[Chunk]:
        ext = PurePath(filename).suffix.lower()
        strategy = _EXTENSION_MAP.get(ext, "fallback")

        if strategy == "markdown":
            chunks = self._chunk_markdown(text)
        elif strategy == "yaml":
            chunks = self._chunk_yaml(text)
        elif strategy == "config":
            chunks = self._chunk_config(text)
        else:
            chunks = self._chunk_sliding_window(text)

        # Attach metadata to every chunk
        for i, chunk in enumerate(chunks):
            chunk.metadata["filename"] = filename
            chunk.metadata["type"] = strategy
            chunk.metadata["chunk_index"] = i

        # Filter out empty chunks
        return [c for c in chunks if c.text.strip()]

    def _chunk_markdown(self, text: str) -> list[Chunk]:
        """Split markdown on headers, then break large sections with overlap."""
        sections: list[str] = []
        header_positions = [m.start() for m in _MD_HEADER.finditer(text)]

        if not header_positions:
            return self._chunk_sliding_window(text)

        # Add text before first header if any
        if header_positions[0] > 0:
            preamble = text[: header_positions[0]].strip()
            if preamble:
                sections.append(preamble)

        for i, pos in enumerate(header_positions):
            end = header_positions[i + 1] if i + 1 < len(header_positions) else len(text)
            sections.append(text[pos:end].strip())

        # Break oversized sections with overlap
        chunks: list[Chunk] = []
        for section in sections:
            if len(section) <= self.target_size * 1.5:
                chunks.append(Chunk(text=section))
            else:
                chunks.extend(self._chunk_sliding_window(section))

        return chunks

    def _chunk_yaml(self, text: str) -> list[Chunk]:
        """Chunk YAML by top-level keys, keeping each key's block intact."""
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            return self._chunk_sliding_window(text)

        if not isinstance(data, dict):
            return self._chunk_sliding_window(text)

        chunks: list[Chunk] = []
        for key, value in data.items():
            block = yaml.dump({key: value}, default_flow_style=False, sort_keys=False)
            chunk = Chunk(text=block.strip())
            chunk.metadata["yaml_key"] = str(key)
            chunks.append(chunk)

        return chunks

    def _chunk_config(self, text: str) -> list[Chunk]:
        """Split INI-style config files on [section] headers."""
        section_starts = [m.start() for m in _INI_SECTION.finditer(text)]

        if not section_starts:
            return self._chunk_sliding_window(text)

        sections: list[str] = []

        # Text before first section
        if section_starts[0] > 0:
            preamble = text[: section_starts[0]].strip()
            if preamble:
                sections.append(preamble)

        for i, pos in enumerate(section_starts):
            end = section_starts[i + 1] if i + 1 < len(section_starts) else len(text)
            sections.append(text[pos:end].strip())

        return [Chunk(text=s) for s in sections]

    def _chunk_sliding_window(self, text: str) -> list[Chunk]:
        """Fallback: sliding window with overlap."""
        if len(text) <= self.target_size * 1.5:
            return [Chunk(text=text.strip())]

        chunks: list[Chunk] = []
        start = 0
        while start < len(text):
            end = start + self.target_size

            # Try to break at a paragraph or sentence boundary
            if end < len(text):
                # Look for paragraph break
                newline_pos = text.rfind("\n\n", start, end)
                if newline_pos > start + self.target_size // 2:
                    end = newline_pos
                else:
                    # Look for sentence break
                    period_pos = text.rfind(". ", start, end)
                    if period_pos > start + self.target_size // 2:
                        end = period_pos + 1

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(text=chunk_text))

            start = end - self.overlap if end < len(text) else end

        return chunks
