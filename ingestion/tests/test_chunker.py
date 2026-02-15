"""Tests for the document chunker."""

from chunker import DocumentChunker


class TestMarkdownChunking:
    def setup_method(self):
        self.chunker = DocumentChunker(target_size=500, overlap=100)

    def test_splits_on_headers(self, markdown_fixture):
        chunks = self.chunker.chunk(markdown_fixture, "test.md")
        assert len(chunks) > 1
        # First chunk should contain the title section
        header_chunks = [c for c in chunks if "# Homelab DNS Setup" in c.text]
        assert len(header_chunks) >= 1

    def test_preserves_metadata(self, markdown_fixture):
        chunks = self.chunker.chunk(markdown_fixture, "dns-setup.md")
        for i, chunk in enumerate(chunks):
            assert chunk.metadata["filename"] == "dns-setup.md"
            assert chunk.metadata["type"] == "markdown"
            assert chunk.metadata["chunk_index"] == i

    def test_handles_no_headers(self):
        text = "Just a plain paragraph of text with no markdown headers at all."
        chunks = self.chunker.chunk(text, "plain.md")
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_txt_uses_markdown_strategy(self):
        text = "# Title\n\nBody text here."
        chunks = self.chunker.chunk(text, "notes.txt")
        assert chunks[0].metadata["type"] == "markdown"


class TestYAMLChunking:
    def setup_method(self):
        self.chunker = DocumentChunker()

    def test_chunks_by_top_level_keys(self, compose_fixture):
        chunks = self.chunker.chunk(compose_fixture, "docker-compose.yaml")
        # docker-compose has version, services, volumes as top-level keys
        assert len(chunks) >= 2
        keys = [c.metadata.get("yaml_key") for c in chunks]
        assert "services" in keys

    def test_yaml_key_metadata(self, compose_fixture):
        chunks = self.chunker.chunk(compose_fixture, "docker-compose.yaml")
        for chunk in chunks:
            assert "yaml_key" in chunk.metadata
            assert chunk.metadata["type"] == "yaml"

    def test_yml_extension_works(self):
        text = "key1:\n  nested: value\nkey2:\n  other: data\n"
        chunks = self.chunker.chunk(text, "config.yml")
        assert chunks[0].metadata["type"] == "yaml"

    def test_invalid_yaml_falls_back(self):
        text = "this: is: not: valid: yaml: {{{"
        chunks = self.chunker.chunk(text, "bad.yaml")
        assert len(chunks) >= 1
        assert chunks[0].metadata["type"] == "yaml"


class TestConfigChunking:
    def setup_method(self):
        self.chunker = DocumentChunker()

    def test_splits_on_sections(self):
        text = "[server]\nhost = 0.0.0.0\nport = 8080\n\n[database]\nurl = localhost\n"
        chunks = self.chunker.chunk(text, "app.conf")
        assert len(chunks) == 2
        assert "[server]" in chunks[0].text
        assert "[database]" in chunks[1].text

    def test_config_metadata(self):
        text = "[main]\nkey = value\n"
        chunks = self.chunker.chunk(text, "test.ini")
        assert chunks[0].metadata["type"] == "config"


class TestFallbackChunking:
    def setup_method(self):
        self.chunker = DocumentChunker(target_size=100, overlap=20)

    def test_unknown_extension_uses_fallback(self):
        text = "A" * 300
        chunks = self.chunker.chunk(text, "data.csv")
        assert len(chunks) > 1
        assert chunks[0].metadata["type"] == "fallback"

    def test_small_text_single_chunk(self):
        text = "Short text."
        chunks = self.chunker.chunk(text, "small.csv")
        assert len(chunks) == 1

    def test_empty_text_no_chunks(self):
        chunks = self.chunker.chunk("", "empty.csv")
        assert len(chunks) == 0

    def test_chunk_indices_sequential(self):
        text = "Word " * 200
        chunks = self.chunker.chunk(text, "long.csv")
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))
