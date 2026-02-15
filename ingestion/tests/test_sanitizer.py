"""Tests for the document sanitizer."""

from sanitizer import DocumentSanitizer


class TestIPRedaction:
    def setup_method(self):
        self.sanitizer = DocumentSanitizer()

    def test_redacts_192_168_addresses(self):
        text = "Server is at 192.168.1.10 on port 53"
        report = self.sanitizer.sanitize(text)
        assert "192.168.1.10" not in report.sanitized_text
        assert "[PRIVATE_IP_1]" in report.sanitized_text
        assert report.redaction_count == 1
        assert "ip_redacted" in report.actions

    def test_redacts_10_x_addresses(self):
        text = "Proxmox at 10.0.0.5"
        report = self.sanitizer.sanitize(text)
        assert "10.0.0.5" not in report.sanitized_text
        assert "[PRIVATE_IP_1]" in report.sanitized_text

    def test_redacts_172_16_addresses(self):
        text = "NAS is at 172.16.0.100"
        report = self.sanitizer.sanitize(text)
        assert "172.16.0.100" not in report.sanitized_text
        assert "[PRIVATE_IP_1]" in report.sanitized_text

    def test_does_not_redact_172_15(self):
        """172.15.x.x is NOT RFC 1918 — should be left alone."""
        text = "External host 172.15.0.1"
        report = self.sanitizer.sanitize(text)
        assert "172.15.0.1" in report.sanitized_text
        assert report.redaction_count == 0

    def test_does_not_redact_public_ips(self):
        text = "Cloudflare DNS is 1.1.1.1 and Google is 8.8.8.8"
        report = self.sanitizer.sanitize(text)
        assert "1.1.1.1" in report.sanitized_text
        assert "8.8.8.8" in report.sanitized_text
        assert report.redaction_count == 0

    def test_consistent_placeholders(self):
        """Same IP always gets the same placeholder within a document."""
        text = "Primary 192.168.1.10, Secondary 10.0.0.5, Primary again 192.168.1.10"
        report = self.sanitizer.sanitize(text)
        assert report.sanitized_text.count("[PRIVATE_IP_1]") == 2
        assert "[PRIVATE_IP_2]" in report.sanitized_text
        # 3 IPs found but 2 unique → 3 total redactions
        assert report.redaction_count == 3

    def test_multiple_unique_ips(self):
        text = "A=192.168.1.1, B=10.0.0.1, C=172.16.0.1"
        report = self.sanitizer.sanitize(text)
        assert "[PRIVATE_IP_1]" in report.sanitized_text
        assert "[PRIVATE_IP_2]" in report.sanitized_text
        assert "[PRIVATE_IP_3]" in report.sanitized_text

    def test_rejects_invalid_octets(self):
        """Octets > 255 are not valid IPs — should NOT be redacted."""
        text = "Not an IP: 10.300.400.500 or 192.168.999.1"
        report = self.sanitizer.sanitize(text)
        assert "10.300.400.500" in report.sanitized_text
        assert "192.168.999.1" in report.sanitized_text
        assert report.redaction_count == 0

    def test_boundary_octets(self):
        """255 is valid, 256 is not."""
        text = "Valid: 10.0.0.255 Invalid: 10.0.0.256"
        report = self.sanitizer.sanitize(text)
        assert "10.0.0.255" not in report.sanitized_text
        assert "10.0.0.256" in report.sanitized_text
        assert report.redaction_count == 1


class TestSecretRedaction:
    def setup_method(self):
        self.sanitizer = DocumentSanitizer()

    def test_redacts_password_equals(self):
        text = "password=SuperSecret123!"
        report = self.sanitizer.sanitize(text)
        assert "SuperSecret123!" not in report.sanitized_text
        assert "[REDACTED]" in report.sanitized_text
        assert "secret_redacted" in report.actions

    def test_redacts_api_key_colon(self):
        text = "api_key: sk-abc123xyz"
        report = self.sanitizer.sanitize(text)
        assert "sk-abc123xyz" not in report.sanitized_text
        assert "[REDACTED]" in report.sanitized_text

    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.dGVzdA.abc123"
        report = self.sanitizer.sanitize(text)
        assert "eyJhbGciOiJIUzI1NiJ9" not in report.sanitized_text
        assert "bearer_token_redacted" in report.actions

    def test_redacts_aws_key(self):
        text = "aws_key = AKIAIOSFODNN7EXAMPLE"
        report = self.sanitizer.sanitize(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in report.sanitized_text

    def test_redacts_double_quoted_password(self):
        text = 'password="SuperSecret123!"'
        report = self.sanitizer.sanitize(text)
        assert "SuperSecret123!" not in report.sanitized_text
        assert "[REDACTED]" in report.sanitized_text
        # Quotes should be preserved
        assert '"[REDACTED]"' in report.sanitized_text

    def test_redacts_single_quoted_password(self):
        text = "api_key='sk-abc123xyz'"
        report = self.sanitizer.sanitize(text)
        assert "sk-abc123xyz" not in report.sanitized_text
        assert "'[REDACTED]'" in report.sanitized_text

    def test_redacts_backtick_quoted_password(self):
        text = "password=`hunter2`"
        report = self.sanitizer.sanitize(text)
        assert "hunter2" not in report.sanitized_text
        assert "`[REDACTED]`" in report.sanitized_text

    def test_no_op_on_clean_text(self):
        text = "This is perfectly normal documentation with no secrets."
        report = self.sanitizer.sanitize(text)
        assert report.sanitized_text == text
        assert report.redaction_count == 0
        assert report.actions == []


class TestMixedContent:
    def test_redacts_both_ips_and_secrets(self):
        sanitizer = DocumentSanitizer()
        text = "Connect to 192.168.1.10 with password=hunter2"
        report = sanitizer.sanitize(text)
        assert "192.168.1.10" not in report.sanitized_text
        assert "hunter2" not in report.sanitized_text
        assert "ip_redacted" in report.actions
        assert "secret_redacted" in report.actions

    def test_fixture_file(self, markdown_fixture):
        sanitizer = DocumentSanitizer()
        report = sanitizer.sanitize(markdown_fixture)
        # All private IPs should be gone
        assert "192.168.1.10" not in report.sanitized_text
        assert "10.0.0.5" not in report.sanitized_text
        assert "172.16.0.100" not in report.sanitized_text
        # Public IP should remain
        assert "1.1.1.1" in report.sanitized_text
        # Password should be redacted
        assert "SuperSecret123!" not in report.sanitized_text
        # Structure preserved
        assert "# Homelab DNS Setup" in report.sanitized_text
        assert report.redaction_count > 0
