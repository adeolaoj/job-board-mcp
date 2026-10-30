""" Defined normalized job format shared by every ATS. """

from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Job:
    company: str # Name comes from companies.yaml
    title: str
    location: str
    remote: bool | None
    url: str
    poste_at: datetime # UTC
    ats: str # 'greenhouse' | 'lever' | 'ashby'
    job_id: str
    lanes: list[str] = field(default_factory=list) # Ensures every instance of Job has its own list of lanes