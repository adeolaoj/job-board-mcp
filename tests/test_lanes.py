from pathlib import Path

import pytest

from job_board_mcp.lanes import classify, load_lanes, matches, tokenize

LANES_PATH = Path(__file__).parent.parent / "config" / "lanes.yaml"


@pytest.fixture(scope="module")
def lanes():
    return load_lanes(LANES_PATH)


def test_tokenize_lowercases_and_drops_punctuation():
    assert tokenize("Sr. Account Executive - Enterprise") == ["sr", "account", "executive", "enterprise"]


def test_tokenize_splits_on_hyphens_and_slashes():
    assert tokenize("Forward-Deployed Staff/Principal") == ["forward", "deployed", "staff", "principal"]


def test_matches_requires_adjacent_words():
    title = tokenize("Customer Success Engineer")
    assert matches(title, "customer success engineer")
    assert not matches(title, "customer engineer")


def test_matches_whole_words_only():
    assert not matches(tokenize("Upgrade Specialist"), "grad")
    assert not matches(tokenize("Staffing Coordinator"), "staff")
    assert not matches(tokenize("Solutions Engineer, International"), "intern")


# Real titles from tests/fixtures/, plus a few written to test edge cases.
@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # Greenhouse (Addepar)
        ("AddeGrad Program (2027) - Client Solutions Analyst", ["new_grad"]),
        ("Product Manager - Early Career, AI Platform", ["pm", "new_grad"]),
        ("Software Engineer - Customer Facing Applied AI", ["deployment"]),
        ("Sr. Account Executive - Enterprise", []),
        # Lever (Zoox)
        ("Technical Program Manager, PMO - Test Fleet Program (Contract)", ["pm"]),
        ("Senior Staff/Principal Software Engineer - GPU System Software, Onboard Execution", []),
        ("Administrative Business Partner, Floater", []),
        # Ashby (Deepgram)
        ("Forward-Deployed Engineer (FDE), Strategic Accounts", ["deployment"]),
        ("Senior Forward-Deployed Engineer, Federal", []),
        ("Customer Success Engineer (Scaled)", ["deployment"]),
        ("Research Staff, Voice AI Foundations", []),  # accepted miss, see decisions.md
        # Written to test edge cases
        ("Solutions Engineer, International", ["deployment"]),
        ("Software Engineer Intern (Summer 2027)", []),
        ("New Graduate Software Engineer", ["new_grad"]),
        ("Sr. Solutions Engineer", []),
        ("Head of Product Operations", []),
    ],
)
def test_classify(lanes, title, expected):
    assert classify(title, lanes) == expected