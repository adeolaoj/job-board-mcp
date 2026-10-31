"""Convert job description HTML into readable plain text."""

import re
from html.parser import HTMLParser

BLOCK_TAGS = {"p", "div", "ul", "ol", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()  # convert_charrefs=True by default, so entities come decoded in handle_data
        self._text = []
        self._bullet_pending = False

    def handle_starttag(self, tag, attrs):   # called for <p>, <li>, <strong>, ...
        if tag in BLOCK_TAGS:
            self._text.append("\n")
        if tag == "li":
            # Defer the "- " until the item's first real text, so <li><p>Text</p></li>
            # becomes "- Text" instead of a lone "- " line followed by "Text".
            self._bullet_pending = True

    def handle_endtag(self, tag):            # called for </p>, </li>, ...
        if tag in BLOCK_TAGS:
            self._text.append("\n")
        if tag == "li":
            # An item with no text (empty, or only an <img>) must not bullet the next text.
            self._bullet_pending = False

    def handle_data(self, data):             # called with the text between tags
        if self._bullet_pending and data.strip():
            self._text.append("- ")
            self._bullet_pending = False
        # Newlines in the HTML source are just whitespace; only tags create line breaks.
        # \s also matches \xa0, so &nbsp; becomes a normal space.
        self._text.append(re.sub(r"\s+", " ", data))

    def get_text(self):
        lines = "".join(self._text).split("\n")
        lines = (line.strip() for line in lines)
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    """Return readable text: block tags become line breaks, <li> becomes "- ", entities decoded."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()  # flushes text still buffered after the last tag, so it isn't lost
    return parser.get_text()
