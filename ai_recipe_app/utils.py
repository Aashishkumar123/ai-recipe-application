import re
import html as html_lib


def html_to_text(raw: str) -> str:
    """Convert rendered bot HTML to clean structured text for LLM history.

    Strips JavaScript-injected UI sections (YouTube videos, unit toggles)
    and converts semantic HTML (headings, lists, paragraphs) to plain text
    so the model receives a readable recipe rather than tag soup.
    """
    # ── Remove JS-injected UI blocks ──────────────────────────────────────
    # YouTube section is always appended last — truncate from there
    text = re.sub(
        r'<div[^>]*class="[^"]*recipe-videos[^"]*".*',
        '', raw, flags=re.DOTALL | re.IGNORECASE,
    )
    # Unit-toggle widget
    text = re.sub(
        r'<div[^>]*class="[^"]*unit-toggle[^"]*"[^>]*>.*?</div>',
        '', text, flags=re.DOTALL | re.IGNORECASE,
    )

    # ── Headings ──────────────────────────────────────────────────────────
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n# \1\n',   text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n',  text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', text, flags=re.DOTALL | re.IGNORECASE)

    # ── Ordered lists (preserve step numbers) ────────────────────────────
    def _numbered(m):
        idx = 0
        def _li(li_m):
            nonlocal idx
            idx += 1
            return f'\n{idx}. {li_m.group(1)}'
        return re.sub(r'<li[^>]*>(.*?)</li>', _li, m.group(0), flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<ol[^>]*>.*?</ol>', _numbered, text, flags=re.DOTALL | re.IGNORECASE)

    # ── Unordered list items ──────────────────────────────────────────────
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', text, flags=re.DOTALL | re.IGNORECASE)

    # ── Paragraphs and line breaks ────────────────────────────────────────
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', text, flags=re.DOTALL | re.IGNORECASE)

    # ── Strip remaining tags ──────────────────────────────────────────────
    text = re.sub(r'<[^>]+>', '', text)

    # ── Decode entities and normalise whitespace ──────────────────────────
    text = html_lib.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
