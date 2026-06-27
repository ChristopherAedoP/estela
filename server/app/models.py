from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str


@dataclass
class TranscriptLine:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None


@dataclass
class ActaResult:
    title: str
    duration: str
    speakers: int
    lines: list = field(default_factory=list)
    markdown: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
