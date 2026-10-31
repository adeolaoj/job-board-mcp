import textwrap
from pathlib import Path

import pytest

from job_board_mcp.config import Company, load_companies

REAL_CONFIG = Path(__file__).parent.parent / "config" / "companies.yaml"


def write_config(tmp_path: Path, text: str) -> Path:
    """Write YAML text to a temporary companies.yaml and return its path."""
    path = tmp_path / "companies.yaml"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


# --- Valid config ---

def test_loads_valid_companies(tmp_path):
    path = write_config(tmp_path, """
        - name: Addepar
          ats: greenhouse
          slug: addepar1
        - name: Deepgram
          ats: ashby
          slug: deepgram
    """)

    assert load_companies(path) == [
        Company(name="Addepar", ats="greenhouse", slug="addepar1"),
        Company(name="Deepgram", ats="ashby", slug="deepgram"),
    ]


def test_real_config_is_valid():
    # Catches typos in the actual config before the server hits them.
    companies = load_companies(REAL_CONFIG)
    assert len(companies) > 0


# --- Invalid config: each must raise ValueError naming the problem ---

def test_unknown_ats_names_the_company(tmp_path):
    path = write_config(tmp_path, """
        - name: Sierra
          ats: workday
          slug: sierra
    """)

    with pytest.raises(ValueError, match="Sierra"):
        load_companies(path)


def test_missing_slug_raises(tmp_path):
    """ Test that loading a company with a missing slug raises a ValueError """
    path = write_config(tmp_path, """
        - name: Sierra
          ats: greenhouse
    """)

    with pytest.raises(ValueError, match="Sierra"):
        load_companies(path)


def test_missing_name_raises(tmp_path):
    """ Test that loading a company with a missing name raises a ValueError """
    path = write_config(tmp_path, """
        - ats: greenhouse
          slug: sierra
    """)

    with pytest.raises(ValueError, match="Entry #1 has missing required fields"):
        load_companies(path)


def test_duplicate_names_raise(tmp_path):
    """ Test that loading companies with duplicate names raises a ValueError """
    path = write_config(tmp_path, """
        - name: Sierra
          ats: greenhouse
          slug: sierra
        - name: Sierra
          ats: ashby
          slug: sierra2
    """)

    with pytest.raises(ValueError, match="Entry #2 has duplicate name Sierra"):
        load_companies(path)


def test_empty_file_raises(tmp_path):
    """ Test that loading an empty config file raises a ValueError instead of a TypeError """
    path = write_config(tmp_path, "")

    with pytest.raises(ValueError, match="must be a list of company entries"):
        load_companies(path)


def test_top_level_mapping_raises(tmp_path):
    """ Test that a config whose top level is a mapping instead of a list raises a ValueError """
    path = write_config(tmp_path, """
        name: Sierra
        ats: greenhouse
        slug: sierra
    """)

    with pytest.raises(ValueError, match="must be a list of company entries"):
        load_companies(path)


def test_non_mapping_entry_raises(tmp_path):
    """ Test that an entry that isn't a mapping raises a ValueError naming its position """
    path = write_config(tmp_path, """
        - name: Addepar
          ats: greenhouse
          slug: addepar1
        - Sierra
    """)

    with pytest.raises(ValueError, match="Entry #2 must be a mapping"):
        load_companies(path)


def test_non_string_ats_raises(tmp_path):
    """ Test that a numeric ATS raises a ValueError instead of crashing on .lower() """
    path = write_config(tmp_path, """
        - name: Sierra
          ats: 123
          slug: sierra
    """)

    with pytest.raises(ValueError, match="Entry #1 has unsupported ATS for company Sierra"):
        load_companies(path)


def test_non_string_slug_raises(tmp_path):
    """ Test that a numeric slug (which YAML parses as an int) raises a ValueError """
    path = write_config(tmp_path, """
        - name: Sierra
          ats: greenhouse
          slug: 12345
    """)

    with pytest.raises(ValueError, match="Entry #1 name and slug must be strings"):
        load_companies(path)


def test_non_string_name_raises(tmp_path):
    """ Test that a numeric name raises a ValueError """
    path = write_config(tmp_path, """
        - name: 123
          ats: greenhouse
          slug: sierra
    """)

    with pytest.raises(ValueError, match="Entry #1 name and slug must be strings"):
        load_companies(path)


def test_ats_capitalization(tmp_path):
    """ Test that loading a company with a capitalization mismatch in ATS gets lowercased before validation """
    path = write_config(tmp_path, """
        - name: Sierra
          ats: Greenhouse
          slug: sierra
    """)

    assert load_companies(path) == [
        Company(name="Sierra", ats="greenhouse", slug="sierra"),
    ]