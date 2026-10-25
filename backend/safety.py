"""Safety rules: ChaosPilot only tests sites you own or have written permission to test.

A host is allowed if (a) it is in ALLOWED_HOSTS (.env, for local development), or
(b) its owner proved control by publishing our token at /.well-known/chaospilot.txt.
"""
import hashlib
import ipaddress
import os
import socket
import time
from typing import Optional
from urllib.parse import urlparse

import httpx

VERIFY_PATH = "/chaospilot-verify.txt"
VERIFIED_TTL_SECONDS = 24 * 60 * 60
_verified: dict[str, float] = {}  # host -> time verified


def _allowed_hosts() -> set[str]:
    raw = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


ALLOWED_HOSTS = _allowed_hosts()  # kept for older imports; host_allowed() reads .env fresh


def _hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def host_allowed(url: str) -> bool:
    host = _hostname(url)
    if not host:
        return False
    if host in _allowed_hosts():
        return True
    verified_at = _verified.get(host)
    return bool(verified_at and time.time() - verified_at < VERIFIED_TTL_SECONDS)


def verification_token(host: str) -> str:
    secret = os.getenv("CHAOSPILOT_VERIFY_SECRET", "chaospilot-dev")
    return "chaospilot-verify-" + hashlib.sha256(f"{secret}:{host.lower()}".encode()).hexdigest()[:24]


def _is_public_host(host: str) -> bool:
    """Refuse private, loopback and link-local addresses so /verify cannot probe internal networks."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def verify_ownership(url: str) -> tuple[bool, str]:
    """Look for our token at /.well-known/chaospilot.txt on the site. Returns (verified, message)."""
    parsed = urlparse(url)
    host = _hostname(url)
    if parsed.scheme not in ("http", "https") or not host:
        return False, "Enter a full URL starting with http:// or https://"
    if host in _allowed_hosts():
        return True, "This host is already allowed in ALLOWED_HOSTS."
    if not _is_public_host(host):
        return False, "That host does not resolve to a public address, so it cannot be verified."

    file_url = f"https://{host}{VERIFY_PATH}"
    token = verification_token(host)
    try:
        resp = httpx.get(file_url, timeout=8, follow_redirects=False)
    except httpx.HTTPError as e:
        return False, f"Could not fetch {file_url}: {e.__class__.__name__}"
    if resp.status_code != 200:
        return False, f"{file_url} returned HTTP {resp.status_code}. Publish the token file there."
    if token not in resp.text:
        return False, f"{file_url} was found but does not contain the expected token."
    _verified[host] = time.time()
    return True, "Ownership verified. This host is allowed for the next 24 hours."


def blocked_reason(scenario, base_url: str) -> Optional[str]:
    """Return why a scenario must not run, or None if it is fine."""
    if not host_allowed(base_url):
        return (
            f"Site not allowed: {base_url}. ChaosPilot only tests sites you own or have written "
            "permission to test. Verify ownership with /verify, or add the host to ALLOWED_HOSTS "
            "in .env for local development."
        )
    for step in scenario.steps:
        if step.action == "navigate" and step.value:
            parsed = urlparse(step.value)
            if parsed.scheme not in ("", "http", "https"):
                return f"Blocked navigation to a non-web address: {step.value}"
            if parsed.hostname and not host_allowed(step.value):
                return f"Blocked navigation to a site that is not allowed: {step.value}"
    return None