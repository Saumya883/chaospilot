import httpx
from bs4 import BeautifulSoup


def fetch_page_summary(url: str, max_chars: int = 4000) -> str:
    """Summarize the visible structure of a page: headings, fields, buttons, links."""
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"(Could not fetch page: {e})"

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    lines = []
    if soup.title and soup.title.string:
        lines.append(f"Title: {soup.title.string.strip()}")
    for h in soup.find_all(["h1", "h2", "h3"]):
        lines.append(f"Heading: {h.get_text(strip=True)}")
    for f in soup.find_all(["input", "textarea", "select"]):
        lines.append(
            f"Field: type={f.get('type', 'text')} "
            f"name={f.get('name') or f.get('id') or ''} "
            f"placeholder={f.get('placeholder', '')}"
        )
    for b in soup.find_all(["button", "a"]):
        text = b.get_text(strip=True)
        if text:
            lines.append(f"Button/Link: {text}")
    return "\n".join(lines)[:max_chars]