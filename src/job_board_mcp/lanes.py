"""Match job titles to career lanes using keywords from config/lanes.yaml."""

from pathlib import Path

import yaml
import re


def load_lanes(path: Path) -> dict:
    """Open the yaml file and return it as a dictionary object"""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def tokenize(text: str) -> list[str]:
    """Lowercase text and split it into words of letters and digits."""
    lowercase = text.lower()

    # Using \w to match word characters instead of [a-z0-9] helps include
    # underscores and other word characters as well
    tokens = re.findall(r"\w+", lowercase) # Extract all word characters as tokens
    return tokens


def matches(title_tokens: list[str], keyword: str) -> bool:
    """True if the keyword's words appear next to each other, in order, in title_tokens."""
    if not keyword:
        return False
    
    keyword_tokens = tokenize(keyword)

    for i in range(len(title_tokens) - len(keyword_tokens) + 1):
        window = title_tokens[i : i + len(keyword_tokens)]
        if window == keyword_tokens:
            return True

    return False


def classify(title: str, lanes: dict) -> list[str]:
    """Return the lanes a title belongs to, in config order. Empty if any exclude keyword matches."""
    title_tokens = tokenize(title)

    for word in lanes["exclude"]:
        if matches(title_tokens, word):
            return []

    result = []

    # Note: using lanes.get returns a an empty dictionary if the 'lanes' key is missing.
    # Changed this to lanes["lanes"] to raise KeyError immediately if 'lanes' is missing.
    extracted_lanes = lanes["lanes"]

    for lane, keywords in extracted_lanes.items():
            if any(matches(title_tokens, keyword) for keyword in keywords):
                    result.append(lane)
                
    

    return result