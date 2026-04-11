"""Status data model for intimate devices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IntimateStatus:
    """In-memory snapshot of an intimate device's control state.

    The intimate protocol does not expose a status-query endpoint like the
    appliance family does, so callers track state locally as commands are
    issued and notifications are received.
    """

    play: bool = False
    mode: int = 0
    motor1: int = 0
    motor2: int = 0
    position: str = "all"
    n2_mode: int = 0
    custom_mode: Optional[int] = None
    range_start: int = 0
    range_end: int = 92
    custom_slots: dict[int, list[dict[str, int]]] = field(
        default_factory=lambda: {32: [], 33: [], 34: []}
    )
