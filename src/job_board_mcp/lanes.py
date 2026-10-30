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
    tokens = re.findall(r"\w+", lowercase)
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

    for token in title_tokens:
        if token in lanes["exclude"]:
            return []

    result = []
    seen = set()

    extracted_lanes = lanes.get('lanes', {})

    for lane, keywords in extracted_lanes.items():
        for keyword in keywords:
            if matches(title_tokens, keyword):
                if lane not in seen:
                    seen.add(lane)
                    result.append(lane)
                
    

    return result