"""Terminal formatting helpers for the tingon CLI."""

from __future__ import annotations

import json
from typing import Optional

from ..profiles import DeviceProfile


def format_status(status: dict, device_profile: Optional[DeviceProfile] = None) -> str:
    """Format a status dict for display."""
    lines = []
    for key, value in sorted(status.items()):
        if isinstance(value, bool):
            value = "ON" if value else "OFF"
        elif isinstance(value, list):
            value = json.dumps(value)
        elif key in (
            "power", "drainage", "dehumidification", "defrost",
            "wind_status", "water_status", "fire_status",
            "eco_cruise", "water_pressurization", "single_cruise",
            "diandong", "zero_cold_water",
        ):
            value = "ON" if value else "OFF"
        elif "temp" in key:
            value = f"{value} C"
        elif "hum" in key:
            value = f"{value}%"
        lines.append(f"  {key:.<30} {value}")
    return "\n".join(lines)
