import os
from typing import Optional
from urllib.parse import urlparse

from schemas import Scenario

ALLOWED_HOSTS = {
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
}


def host_allowed(url: str) -> bool:
    return (urlparse(url).hostname or "") in ALLOWED_HOSTS


def blocked_reason(scenario: Scenario, base_url: str) -> Optional[str]:
    """Return why a scenario must not run, or None if it is safe."""
    if not host_allowed(base_url):
        return (f"Host not in ALLOWED_HOSTS: {base_url}. ChaosPilot only tests sites you own or have written permission to test. Add the host to ALLOWED_HOSTS in .env only if that applies.")
    for step in scenario.steps:
        if step.action == "navigate" and step.value:
            parsed = urlparse(step.value)
            if parsed.scheme not in ("", "http", "https") or (
                parsed.hostname and parsed.hostname not in ALLOWED_HOSTS
            ):
                return f"Scenario navigates outside allowed hosts: {step.value}"
    return None