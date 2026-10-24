import re
from typing import Literal
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

LOCAL_HOSTS = {"localhost", "127.0.0.1"}
SENSITIVE_PARAMS = {"password", "pass", "pwd", "token", "apikey", "api_key", "secret", "email", "session"}

SECRET_PATTERNS = {
    "Google-style API key": r"AIza[0-9A-Za-z_\-]{35}",
    "AWS access key": r"AKIA[0-9A-Z]{16}",
    "OpenAI-style key": r"sk-[A-Za-z0-9]{20,}",
    "Private key header": r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
}

ERROR_PATTERNS = {
    "Stack trace": r"Traceback \(most recent call last\)|Exception in thread|\bat [\w.$]+\([\w.]+:\d+\)",
    "SQL error text": r"SQLSTATE|SQL syntax|ORA-\d{5}|psycopg2|mysql_",
    "Server file path": r"/var/www/|/home/\w+/|[A-Z]:\\\\(?:Users|inetpub)",
}


class Finding(BaseModel):
    title: str
    severity: Literal["low", "medium", "high", "critical"]
    evidence: str
    why_it_matters: str


def check_url_for_sensitive_params(url: str) -> list[Finding]:
    keys = {k.lower() for k in parse_qs(urlparse(url).query)}
    hits = sorted(keys & SENSITIVE_PARAMS)
    if not hits:
        return []
    return [Finding(
        title="Sensitive data in the URL",
        severity="medium",
        evidence=f"Query parameters in URL: {', '.join(hits)}",
        why_it_matters="URLs end up in browser history, server logs and referrer headers.",
    )]


def scan_text_for_leaks(text: str) -> list[Finding]:
    """Use on page text observed during a scenario (for example after fuzzed input)."""
    findings = []
    for label, pattern in ERROR_PATTERNS.items():
        m = re.search(pattern, text)
        if m:
            findings.append(Finding(
                title=f"Error page exposes internals: {label}",
                severity="high" if label != "Server file path" else "medium",
                evidence=f'Observed text: "{m.group(0)[:80]}"',
                why_it_matters="Detailed errors reveal how the server is built and help attackers.",
            ))
    return findings


def passive_scan(url: str) -> list[Finding]:
    """Read-only checks on a single page load. No exploitation."""
    findings = check_url_for_sensitive_params(url)
    resp = httpx.get(url, timeout=10, follow_redirects=True)
    parsed = urlparse(str(resp.url))
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    if (
        soup.find("input", attrs={"type": "password"})
        and parsed.scheme == "http"
        and parsed.hostname not in LOCAL_HOSTS
    ):
        findings.append(Finding(
            title="Login page not served over HTTPS",
            severity="high",
            evidence=f"Password field found on {parsed.scheme}://{parsed.hostname}",
            why_it_matters="Passwords sent over plain HTTP can be read in transit.",
        ))

    for label, pattern in SECRET_PATTERNS.items():
        m = re.search(pattern, html)
        if m:
            findings.append(Finding(
                title=f"Secret-looking string in page source: {label}",
                severity="critical",
                evidence=f"Found a value starting with '{m.group(0)[:4]}...' (redacted)",
                why_it_matters="Anyone who views the page source can copy this value.",
            ))

    if parsed.scheme == "https":
        wanted = ["strict-transport-security", "content-security-policy", "x-content-type-options"]
        present = {k.lower() for k in resp.headers}
        missing = [h for h in wanted if h not in present]
        if missing:
            findings.append(Finding(
                title="Standard security headers missing",
                severity="low",
                evidence="Missing: " + ", ".join(missing),
                why_it_matters="These headers add basic protection against common browser attacks.",
            ))
    return findings