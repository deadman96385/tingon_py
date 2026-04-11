"""Device profile metadata, enums, and lookup helpers.

This module is lightweight and importable without BLE or UI dependencies.
It is the shared foundation used by CLI argument parsing, webapp request
validation, scan result classification, and controller selection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Optional

from .exceptions import TingonProtocolError


class DeviceType(IntEnum):
    FJB = 0           # Dehumidifier (1st gen)
    GS = 1            # Water Heater
    RJ = 2            # Water Heater
    FJB_SECOND = 3    # Dehumidifier (2nd gen)


class ProtocolFamily(str, Enum):
    APPLIANCE = "appliance"
    INTIMATE = "intimate"


class DeviceProfile(str, Enum):
    FJB = "fjb"
    GS = "gs"
    RJ = "rj"
    FJB2 = "fjb2"
    M1 = "m1"
    A1 = "a1"
    N1 = "n1"
    M2 = "m2"
    N2 = "n2"

    @classmethod
    def parse(cls, raw: str | None, *, fuzzy: bool = False) -> Optional["DeviceProfile"]:
        if raw is None:
            return None
        key = raw.strip().lower().replace("-", "_").replace(" ", "_")
        marketed_names = {
            "tingon_m1": cls.M1,
            "tingon_a1": cls.A1,
            "tingon_n1": cls.N1,
            "tingon_m2": cls.M2,
            "tingon_n2": cls.N2,
        }
        if key in marketed_names:
            return marketed_names[key]
        try:
            return cls(key)
        except ValueError:
            if fuzzy:
                return cls._infer_from_name(raw)
            raise TingonProtocolError(f"Unknown profile '{raw}'") from None

    @classmethod
    def _infer_from_name(cls, name: str) -> Optional["DeviceProfile"]:
        lowered = name.lower()
        code_matches: list[tuple[int, DeviceProfile]] = []
        for profile, info in PROFILE_INFO.items():
            for code in info.code_hints:
                if re.search(rf"(?<![a-z0-9]){re.escape(code)}(?![a-z0-9])", lowered):
                    code_matches.append((len(code), profile))
        if code_matches:
            code_matches.sort(key=lambda item: item[0], reverse=True)
            return code_matches[0][1]
        for profile, info in PROFILE_INFO.items():
            for hint in info.name_hints:
                if hint in lowered:
                    return profile
        return None


@dataclass(frozen=True)
class ProfileInfo:
    profile: DeviceProfile
    family: ProtocolFamily
    display_name: str
    category: str
    appliance_type: Optional[DeviceType] = None
    intimate_type: Optional[int] = None
    capabilities: frozenset[str] = frozenset()
    name_hints: tuple[str, ...] = ()
    code_hints: tuple[str, ...] = ()


# Capability identifiers
CAP_POWER = "power"
CAP_STATUS = "status"
CAP_HUMIDITY = "humidity"
CAP_DRAINAGE = "drainage"
CAP_DEHUM = "dehumidification"
CAP_WATER_TEMP = "water_temperature"
CAP_BATHROOM_MODE = "bathroom_mode"
CAP_PROVISION = "provision"
CAP_PLAY = "play"
CAP_PRESET_MODE = "preset_mode"
CAP_MOTOR1 = "motor1"
CAP_MOTOR2 = "motor2"
CAP_POSITION = "position"
CAP_CUSTOM = "custom"
CAP_CUSTOM_RANGE = "custom_range"
CAP_N2_MODE = "n2_mode"


PROFILE_INFO: dict[DeviceProfile, ProfileInfo] = {
    DeviceProfile.FJB: ProfileInfo(
        DeviceProfile.FJB, ProtocolFamily.APPLIANCE, "FJB", "Dehumidifier",
        appliance_type=DeviceType.FJB,
        capabilities=frozenset({CAP_POWER, CAP_STATUS, CAP_HUMIDITY, CAP_DRAINAGE, CAP_DEHUM, CAP_PROVISION}),
        name_hints=("xpower",),
        code_hints=("fjb",),
    ),
    DeviceProfile.GS: ProfileInfo(
        DeviceProfile.GS, ProtocolFamily.APPLIANCE, "GS", "Water Heater",
        appliance_type=DeviceType.GS,
        capabilities=frozenset({CAP_POWER, CAP_STATUS, CAP_WATER_TEMP, CAP_BATHROOM_MODE, CAP_PROVISION}),
        name_hints=("wanhe", "anward"),
        code_hints=("gs",),
    ),
    DeviceProfile.RJ: ProfileInfo(
        DeviceProfile.RJ, ProtocolFamily.APPLIANCE, "RJ", "Water Heater",
        appliance_type=DeviceType.RJ,
        capabilities=frozenset({CAP_POWER, CAP_STATUS, CAP_WATER_TEMP, CAP_BATHROOM_MODE, CAP_PROVISION}),
        name_hints=("wanhe", "anward"),
        code_hints=("rj",),
    ),
    DeviceProfile.FJB2: ProfileInfo(
        DeviceProfile.FJB2, ProtocolFamily.APPLIANCE, "FJB2", "Dehumidifier",
        appliance_type=DeviceType.FJB_SECOND,
        capabilities=frozenset({CAP_POWER, CAP_STATUS, CAP_HUMIDITY, CAP_DRAINAGE, CAP_DEHUM, CAP_PROVISION}),
        name_hints=("xpower",),
        code_hints=("fjb2",),
    ),
    DeviceProfile.M1: ProfileInfo(
        DeviceProfile.M1, ProtocolFamily.INTIMATE, "TINGON M1", "Intimate Device",
        intimate_type=0,
        capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_MOTOR2, CAP_CUSTOM}),
        name_hints=("tingon m1", "masturbator", "masturbators"),
        code_hints=("m1",),
    ),
    DeviceProfile.A1: ProfileInfo(
        DeviceProfile.A1, ProtocolFamily.INTIMATE, "TINGON A1", "Intimate Device",
        intimate_type=1,
        capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_CUSTOM}),
        name_hints=("tingon a1", "anal"),
        code_hints=("a1",),
    ),
    DeviceProfile.N1: ProfileInfo(
        DeviceProfile.N1, ProtocolFamily.INTIMATE, "TINGON N1", "Intimate Device",
        intimate_type=2,
        capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_CUSTOM}),
        name_hints=("tingon n1", "nipple", "clamp"),
        code_hints=("n1",),
    ),
    DeviceProfile.M2: ProfileInfo(
        DeviceProfile.M2, ProtocolFamily.INTIMATE, "TINGON M2", "Intimate Device",
        intimate_type=3,
        capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_POSITION, CAP_CUSTOM, CAP_CUSTOM_RANGE}),
        name_hints=("tingon m2",),
        code_hints=("m2",),
    ),
    DeviceProfile.N2: ProfileInfo(
        DeviceProfile.N2, ProtocolFamily.INTIMATE, "TINGON N2", "Intimate Device",
        intimate_type=4,
        capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_MOTOR2, CAP_CUSTOM, CAP_N2_MODE}),
        name_hints=("tingon n2",),
        code_hints=("n2",),
    ),
}


APPLIANCE_TYPE_TO_PROFILE: dict[DeviceType, DeviceProfile] = {
    DeviceType.FJB: DeviceProfile.FJB,
    DeviceType.GS: DeviceProfile.GS,
    DeviceType.RJ: DeviceProfile.RJ,
    DeviceType.FJB_SECOND: DeviceProfile.FJB2,
}


def profile_info(profile: DeviceProfile) -> ProfileInfo:
    return PROFILE_INFO[profile]


INTIMATE_MODE_COUNTS: dict[DeviceProfile, int] = {
    DeviceProfile.A1: 12,
    DeviceProfile.N1: 12,
    DeviceProfile.N2: 12,
    DeviceProfile.M1: 10,
    DeviceProfile.M2: 12,
}

INTIMATE_CUSTOM_STEP_LIMITS: dict[DeviceProfile, int] = {
    DeviceProfile.A1: 4,
    DeviceProfile.N1: 4,
    DeviceProfile.M1: 4,
    DeviceProfile.N2: 6,
    DeviceProfile.M2: 6,
}

INTIMATE_PLAYBACK_BEHAVIORS: tuple[str, ...] = ("loop", "random", "sequence")

INTIMATE_MODE_LABELS: dict[DeviceProfile, list[str]] = {
    DeviceProfile.A1: [
        "Full-Body Tingling",
        "Into the Groove",
        "Step by Step",
        "Jumping with Joy",
        "Rolling Waves",
        "Measured Pulses",
        "Unexpected Surprise",
        "All-Over Sweep",
        "Body and Soul",
        "Surging Tide",
        "Teasing Edge",
        "Hard to Let Go",
    ],
    DeviceProfile.N1: [
        "Gentle Ripples",
        "Tongue Swirl",
        "Rushing Pleasure",
        "Endless Tide",
        "Deep Tingling",
        "Climax Incoming",
        "Deep Echo",
        "Climactic Rush",
        "Tidal Kiss",
        "Rise and Fall",
        "Heartstrings",
        "Roaring Surge",
    ],
    DeviceProfile.N2: [
        "Gentle Ripples",
        "Tongue Swirl",
        "Rushing Pleasure",
        "Endless Tide",
        "Deep Tingling",
        "Climax Incoming",
        "Deep Echo",
        "Climactic Rush",
        "Tidal Kiss",
        "Rise and Fall",
        "Heartstrings",
        "Roaring Surge",
    ],
    DeviceProfile.M2: [
        "Gentle Ripples",
        "Tongue Swirl",
        "Rushing Pleasure",
        "Endless Tide",
        "Deep Tingling",
        "Climax Incoming",
        "Deep Echo",
        "Climactic Rush",
        "Tidal Kiss",
        "Rise and Fall",
        "Heartstrings",
        "Roaring Surge",
    ],
    DeviceProfile.M1: [
        "Unceasing",
        "Deep Undercurrent",
        "Burst Sprint",
        "Endless Tide",
        "Pleasure Sprint",
        "Wave Push",
        "Closing In",
        "Explosive Peak",
        "Roaring Surge",
        "Wild Stimulation",
    ],
}


def intimate_mode_count(profile: DeviceProfile) -> int:
    return INTIMATE_MODE_COUNTS.get(profile, 0)


def intimate_mode_labels(profile: DeviceProfile) -> list[str]:
    return list(INTIMATE_MODE_LABELS.get(profile, ()))


def intimate_custom_step_limit(profile: DeviceProfile) -> int:
    return INTIMATE_CUSTOM_STEP_LIMITS.get(profile, 0)
