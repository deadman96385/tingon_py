"""Terminal formatting helpers for the tingon CLI."""

from __future__ import annotations

import json
from typing import Optional

from ..profiles import DeviceProfile


ZERO_COLD_WATER_MODE_LABELS = {0: "off", 1: "on", 3: "enhanced"}

_BOOL_KEYS = {
    "power", "drainage", "dehumidification", "defrost",
    "wind_status", "water_status", "fire_status",
    "eco_cruise", "water_pressurization", "single_cruise",
    "diandong", "zero_cold_water",
}


def _format_timer_entries(entries: list) -> str:
    if not entries:
        return "none"
    rendered = []
    for entry in entries:
        if not isinstance(entry, dict):
            rendered.append(str(entry))
            continue
        action = "On" if entry.get("switch") else "Off"
        hours = entry.get("hours", 0)
        flag = "" if entry.get("status") else " (disabled)"
        rendered.append(f"{action} in {hours}h{flag}")
    return ", ".join(rendered)


def format_status(status: dict, device_profile: Optional[DeviceProfile] = None) -> str:
    """Format a status dict for display."""
    lines = []
    for key, value in sorted(status.items()):
        if key == "timer_entries":
            value = _format_timer_entries(value if isinstance(value, list) else [])
        elif key == "zero_cold_water_mode":
            value = ZERO_COLD_WATER_MODE_LABELS.get(value, str(value))
        elif isinstance(value, bool):
            value = "ON" if value else "OFF"
        elif isinstance(value, list):
            value = json.dumps(value)
        elif key in _BOOL_KEYS:
            value = "ON" if value else "OFF"
        elif "temp" in key:
            value = f"{value} C"
        elif "hum" in key:
            value = f"{value}%"
        lines.append(f"  {key:.<30} {value}")
    return "\n".join(lines)
