"""Load and validate config/companies.yaml."""

from dataclasses import dataclass
from pathlib import Path

import yaml

SUPPORTED_ATS = {"greenhouse", "lever", "ashby"}


@dataclass(frozen=True)
class Company:
    name: str
    ats: str
    slug: str


def load_companies(path: Path) -> list[Company]:
    """Load companies from YAML. Raises ValueError naming the bad entry if any is invalid."""
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(f"{path.name} must be a list of company entries, got {type(data).__name__}")

    companies = []
    seen = set()
    for index, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry #{index} must be a mapping with name, ats, and slug: {entry!r}")

        name = entry.get("name")
        ats = entry.get("ats")
        slug = entry.get("slug")

        if not name or not ats or not slug:
            raise ValueError(f"Entry #{index} has missing required fields: {entry}")

        if not isinstance(name, str) or not isinstance(slug, str):
            raise ValueError(f"Entry #{index} name and slug must be strings: {entry}")

        if not isinstance(ats, str) or ats.lower() not in SUPPORTED_ATS:
            raise ValueError(f"Entry #{index} has unsupported ATS for company {name}: {ats!r}")
        ats = ats.lower()

        if name in seen:
            raise ValueError(f"Entry #{index} has duplicate name {name}: {entry}")

        seen.add(name)
        companies.append(Company(name=name, ats=ats, slug=slug))

    return companies