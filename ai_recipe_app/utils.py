import re
import html as html_lib


def html_to_text(raw: str) -> str:
    """Strip HTML tags and decode entities for LLM context."""
    text = re.sub(r"<[^>]+>", " ", raw)
    return html_lib.unescape(text).strip()
