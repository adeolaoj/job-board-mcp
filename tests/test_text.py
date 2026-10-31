import html
import json
from pathlib import Path

from job_board_mcp.text import html_to_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_plain_text_is_unchanged():
    assert html_to_text("Hello world") == "Hello world"


def test_empty_input():
    assert html_to_text("") == ""


def test_inline_tags_do_not_break_lines():
    assert html_to_text('<p>Hello <strong>bold</strong> <a href="x">link</a></p>') == "Hello bold link"


def test_paragraphs_go_on_separate_lines():
    assert html_to_text("<p>One</p><p>Two</p>") == "One\nTwo"


def test_br_breaks_lines():
    assert html_to_text("One<br>Two<br/>Three") == "One\nTwo\nThree"


def test_list_items_become_bullets():
    assert html_to_text("<ul><li>First</li><li>Second</li></ul>") == "- First\n- Second"


def test_headings_go_on_their_own_line():
    html_in = "<h1><strong>Company Overview</strong></h1><p>We build things.</p>"
    assert html_to_text(html_in) == "Company Overview\nWe build things."


def test_entities_are_decoded():
    # &nbsp; becomes a normal space, not the invisible \xa0 character.
    assert html_to_text("<p>R&amp;D&nbsp;team&rsquo;s</p>") == "R&D team\u2019s"


def test_whitespace_is_collapsed():
    assert html_to_text("<p>  lots   of\n   space  </p>") == "lots of space"


def test_blank_lines_are_removed():
    # Lever and Greenhouse use <div>&nbsp;</div> as spacers.
    html_in = "<p>One</p><div>&nbsp;</div><div>&nbsp;</div><p>Two</p>"
    assert html_to_text(html_in) == "One\nTwo"


# --- Real fixture content ---

def test_lever_list_content():
    job = json.loads((FIXTURES / "lever_job_detail.json").read_text(encoding="utf-8"))
    text = html_to_text(job["lists"][0]["content"])

    assert "<li>" not in text
    assert all(line.startswith("- ") for line in text.splitlines())


def test_greenhouse_double_escaped_content():
    # Greenhouse content is escaped HTML: unescape once to get real tags,
    # and html_to_text decodes the second layer (&amp;amp; -> &amp; -> &).
    job = json.loads((FIXTURES / "greenhouse_job_detail.json").read_text(encoding="utf-8"))
    text = html_to_text(html.unescape(job["content"]))

    assert "<" not in text
    assert "&amp;" not in text
    assert "R&D" in text
    assert "- Provide hands-on support" in text