from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdFactory(Protocol):
    def new_id(self, namespace: str) -> str: ...


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


@dataclass
class SequenceIdFactory:
    prefix: str = "id"
    _counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def new_id(self, namespace: str) -> str:
        self._counters[namespace] += 1
        return f"{self.prefix}-{namespace}-{self._counters[namespace]:04d}"
