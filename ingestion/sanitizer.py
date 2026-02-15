"""Data sanitizer for document ingestion.

Strips RFC 1918 private IPs, API keys, tokens, passwords, and other
secrets from document text BEFORE embedding. Redacted values get
consistent placeholders so document structure is preserved and the
same IP always maps to the same placeholder within a document.
"""

import re
from dataclasses import dataclass, field


@dataclass
class SanitizationReport:
    """Result of sanitizing a document."""

    sanitized_text: str
    redaction_count: int = 0
    actions: list[str] = field(default_factory=list)


# RFC 1918 ranges: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
# Octet matches 0-255 only (rejects 256+).
_OCTET = r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
_IP_PATTERN = re.compile(
    rf"\b("
    rf"10\.{_OCTET}\.{_OCTET}\.{_OCTET}"
    rf"|172\.(?:1[6-9]|2\d|3[01])\.{_OCTET}\.{_OCTET}"
    rf"|192\.168\.{_OCTET}\.{_OCTET}"
    rf")\b"
)

# Patterns that look like secrets: key=value, token headers, password fields.
# Each tuple is (compiled pattern, group index of the secret value, label).
_SECRET_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    # Generic key=value secrets (password=..., api_key=..., token=..., secret=...)
    # Handles bare values, quoted values ("val", 'val', `val`), and
    # "password is: value" forms.  Quotes are preserved in the output.
    (
        re.compile(
            r"(?i)((?:password|passwd|api[_-]?key|secret|token|auth[_-]?token)"
            r"(?:\s+is)?\s*[:=]\s*)"
            r"(['\"`]?)([^\s,;\"'}{`]+)(\2)"
        ),
        3,
        "secret_redacted",
    ),
    # Bearer tokens
    (
        re.compile(r"(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)", re.IGNORECASE),
        2,
        "bearer_token_redacted",
    ),
    # AWS-style keys (AKIA...)
    (
        re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        1,
        "aws_key_redacted",
    ),
]


class DocumentSanitizer:
    """Strips private IPs and secrets from text with consistent placeholders."""

    def sanitize(self, text: str) -> SanitizationReport:
        actions: list[str] = []
        redaction_count = 0

        # --- IP redaction (consistent mapping) ---
        ip_map: dict[str, str] = {}
        ip_counter = 0

        def replace_ip(match: re.Match) -> str:
            nonlocal ip_counter
            ip = match.group(0)
            if ip not in ip_map:
                ip_counter += 1
                ip_map[ip] = f"[PRIVATE_IP_{ip_counter}]"
            return ip_map[ip]

        text, ip_count = _IP_PATTERN.subn(replace_ip, text)
        if ip_count > 0:
            redaction_count += ip_count
            actions.append("ip_redacted")

        # --- Secret redaction ---
        for pattern, group_idx, label in _SECRET_PATTERNS:
            found = False

            def replace_secret(match: re.Match) -> str:
                nonlocal found
                found = True
                groups = list(match.groups())
                groups[group_idx - 1] = "[REDACTED]"
                return "".join(groups)

            text, count = pattern.subn(replace_secret, text)
            if count > 0:
                redaction_count += count
                if label not in actions:
                    actions.append(label)

        return SanitizationReport(
            sanitized_text=text,
            redaction_count=redaction_count,
            actions=actions,
        )
