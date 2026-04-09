"""
TINGON IoT BLE Device Controller

Controls TINGON dehumidifiers and water heaters via Bluetooth Low Energy.
Protocol reverse-engineered from TINGON Android app v1.1.38.

Requirements: pip install bleak
"""

import argparse
import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from random import randint
from typing import Optional

try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    BleakClient = None
    BleakScanner = None
    BLEDevice = object
    AdvertisementData = object

# ---------------------------------------------------------------------------
# UUIDs
# ---------------------------------------------------------------------------

UUID_BASE = "0000{}-0000-1000-8000-00805f9b34fb"

# Command/Control service (ee)
SVC_CMD = UUID_BASE.format("ee01")
CHR_CMD_WRITE = UUID_BASE.format("ee02")
CHR_CMD_NOTIFY = UUID_BASE.format("ee04")

# Query/Status service (cc)
SVC_QUERY = UUID_BASE.format("cc01")
CHR_QUERY_WRITE = UUID_BASE.format("cc02")
CHR_QUERY_NOTIFY = UUID_BASE.format("cc03")

# WiFi Provisioning service (ff)
SVC_PROV = UUID_BASE.format("ff01")
CHR_PROV_WRITE = UUID_BASE.format("ff03")
CHR_PROV_NOTIFY = UUID_BASE.format("ff02")

# Notification descriptor
CCCD_UUID = UUID_BASE.format("2902")

# ---------------------------------------------------------------------------
# Device types & product keys
# ---------------------------------------------------------------------------

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
            raise ValueError(f"Unknown profile '{raw}'") from None

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

PROFILE_INFO = {
    DeviceProfile.FJB: ProfileInfo(DeviceProfile.FJB, ProtocolFamily.APPLIANCE, "FJB", "Dehumidifier",
                                   appliance_type=DeviceType.FJB,
                                   capabilities=frozenset({CAP_POWER, CAP_STATUS, CAP_HUMIDITY, CAP_DRAINAGE, CAP_DEHUM, CAP_PROVISION}),
                                   name_hints=("xpower",),
                                   code_hints=("fjb",)),
    DeviceProfile.GS: ProfileInfo(DeviceProfile.GS, ProtocolFamily.APPLIANCE, "GS", "Water Heater",
                                  appliance_type=DeviceType.GS,
                                  capabilities=frozenset({CAP_POWER, CAP_STATUS, CAP_WATER_TEMP, CAP_BATHROOM_MODE, CAP_PROVISION}),
                                  name_hints=("wanhe", "anward",),
                                  code_hints=("gs",)),
    DeviceProfile.RJ: ProfileInfo(DeviceProfile.RJ, ProtocolFamily.APPLIANCE, "RJ", "Water Heater",
                                  appliance_type=DeviceType.RJ,
                                  capabilities=frozenset({CAP_POWER, CAP_STATUS, CAP_WATER_TEMP, CAP_BATHROOM_MODE, CAP_PROVISION}),
                                  name_hints=("wanhe", "anward",),
                                  code_hints=("rj",)),
    DeviceProfile.FJB2: ProfileInfo(DeviceProfile.FJB2, ProtocolFamily.APPLIANCE, "FJB2", "Dehumidifier",
                                    appliance_type=DeviceType.FJB_SECOND,
                                    capabilities=frozenset({CAP_POWER, CAP_STATUS, CAP_HUMIDITY, CAP_DRAINAGE, CAP_DEHUM, CAP_PROVISION}),
                                    name_hints=("xpower",),
                                    code_hints=("fjb2",)),
    DeviceProfile.M1: ProfileInfo(DeviceProfile.M1, ProtocolFamily.INTIMATE, "TINGON M1", "Intimate Device",
                                            intimate_type=0,
                                            capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_MOTOR2, CAP_CUSTOM}),
                                            name_hints=("tingon m1", "masturbator", "masturbators"),
                                            code_hints=("m1",)),
    DeviceProfile.A1: ProfileInfo(DeviceProfile.A1, ProtocolFamily.INTIMATE, "TINGON A1", "Intimate Device",
                                    intimate_type=1,
                                    capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_CUSTOM}),
                                    name_hints=("tingon a1", "anal"),
                                    code_hints=("a1",)),
    DeviceProfile.N1: ProfileInfo(DeviceProfile.N1, ProtocolFamily.INTIMATE, "TINGON N1", "Intimate Device",
                                             intimate_type=2,
                                             capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_CUSTOM}),
                                             name_hints=("tingon n1", "nipple", "clamp"),
                                             code_hints=("n1",)),
    DeviceProfile.M2: ProfileInfo(DeviceProfile.M2, ProtocolFamily.INTIMATE, "TINGON M2", "Intimate Device",
                                  intimate_type=3,
                                  capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_POSITION, CAP_CUSTOM, CAP_CUSTOM_RANGE}),
                                  name_hints=("tingon m2",),
                                  code_hints=("m2",)),
    DeviceProfile.N2: ProfileInfo(DeviceProfile.N2, ProtocolFamily.INTIMATE, "TINGON N2", "Intimate Device",
                                  intimate_type=4,
                                  capabilities=frozenset({CAP_PLAY, CAP_PRESET_MODE, CAP_MOTOR1, CAP_MOTOR2, CAP_CUSTOM, CAP_N2_MODE}),
                                  name_hints=("tingon n2",),
                                  code_hints=("n2",)),
}

APPLIANCE_TYPE_TO_PROFILE = {
    DeviceType.FJB: DeviceProfile.FJB,
    DeviceType.GS: DeviceProfile.GS,
    DeviceType.RJ: DeviceProfile.RJ,
    DeviceType.FJB_SECOND: DeviceProfile.FJB2,
}


def profile_info(profile: DeviceProfile) -> ProfileInfo:
    return PROFILE_INFO[profile]


INTIMATE_MODE_COUNTS = {
    DeviceProfile.A1: 12,
    DeviceProfile.N1: 12,
    DeviceProfile.N2: 12,
    DeviceProfile.M1: 10,
    DeviceProfile.M2: 12,
}

INTIMATE_CUSTOM_STEP_LIMITS = {
    DeviceProfile.A1: 4,
    DeviceProfile.N1: 4,
    DeviceProfile.M1: 4,
    DeviceProfile.N2: 6,
    DeviceProfile.M2: 6,
}

INTIMATE_PLAYBACK_BEHAVIORS = ("loop", "random", "sequence")

INTIMATE_MODE_LABELS = {
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

PRODUCT_KEYS = {
    DeviceType.FJB: "0003dbf0bd39ff10",
    DeviceType.GS: "00023f7390c6c770",
    DeviceType.FJB_SECOND: "000521df79128cd1",
}

PRODUCT_IDS = {
    DeviceType.FJB: "0003",
    DeviceType.GS: "0002",
    DeviceType.RJ: "0004",
    DeviceType.FJB_SECOND: "0005",
}

DEHUMIDIFIER_TYPES = {DeviceType.FJB, DeviceType.FJB_SECOND}
WATER_HEATER_TYPES = {DeviceType.GS, DeviceType.RJ}

# ---------------------------------------------------------------------------
# Spec ID definitions
# ---------------------------------------------------------------------------

@dataclass
class SpecDef:
    name: str
    data_type: str   # "01"=bool, "02"=int, "04"=status, "05"=error, "00"=raw
    length: int      # value length in bytes
    writable: bool = False

# Dehumidifier spec IDs
DEHUMIDIFIER_SPECS = {
    1:  SpecDef("power",              "01", 1, writable=True),
    2:  SpecDef("timer",              "00", 0, writable=True),   # variable length
    3:  SpecDef("drainage",           "01", 1, writable=True),
    4:  SpecDef("dehumidification",   "01", 1, writable=True),
    5:  SpecDef("target_hum",         "02", 1, writable=True),
    6:  SpecDef("work_time",          "02", 4),
    7:  SpecDef("total_work_time",    "02", 4),
    8:  SpecDef("compressor_status",  "04", 1),
    10: SpecDef("air_intake_temp",    "02", 1),
    11: SpecDef("air_intake_hum",     "02", 1),
    12: SpecDef("air_outlet_temp",    "02", 1),
    13: SpecDef("air_outlet_hum",     "02", 1),
    14: SpecDef("eva_temp",           "02", 1),
    15: SpecDef("wind_speed",         "02", 1),
    16: SpecDef("error",              "05", 1),
    17: SpecDef("defrost",            "01", 1),
    18: SpecDef("timer_remind_time",  "00", 0),
}

DEHUMIDIFIER_QUERY_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18]

# Signed temperature spec IDs (dehumidifier)
DEHUMIDIFIER_SIGNED_SPECS = {10, 12, 14}

# Water heater spec IDs
WATER_HEATER_SPECS = {
    1:   SpecDef("power",                 "01", 1, writable=True),
    2:   SpecDef("bathroom_mode",         "00", 0, writable=True),
    7:   SpecDef("setting_water_temp",    "02", 1, writable=True),
    11:  SpecDef("inlet_water_temp",      "02", 1),
    13:  SpecDef("outlet_water_temp",     "02", 1),
    17:  SpecDef("wind_status",           "01", 1),
    27:  SpecDef("discharge",             "02", 1),
    102: SpecDef("water_status",          "01", 1),
    103: SpecDef("fire_status",           "01", 1),
    104: SpecDef("equipment_failure",     "05", 1),
    105: SpecDef("cruise_insulation_temp","02", 1, writable=True),
    106: SpecDef("zero_cold_water_mode",  "02", 1, writable=True),
    107: SpecDef("eco_cruise",            "01", 1, writable=True),
    108: SpecDef("water_pressurization",  "01", 1, writable=True),
    109: SpecDef("single_cruise",         "01", 1, writable=True),
    110: SpecDef("diandong",              "01", 1, writable=True),
    111: SpecDef("zero_cold_water",       "01", 1, writable=True),
}

WATER_HEATER_QUERY_IDS = [1, 2, 7, 11, 13, 17, 27, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111]

# Signed temperature spec IDs (water heater)
WATER_HEATER_SIGNED_SPECS = {11, 13}

# Combined spec lookup (union of both)
ALL_SPECS = {**DEHUMIDIFIER_SPECS, **WATER_HEATER_SPECS}

BATHROOM_MODES = {
    1: ("normal", 50),
    2: ("kitchen", 42),
    4: ("eco", 40),
    5: ("season", None),
}

BATHROOM_MODE_NAME_TO_VALUE = {name: code for code, (name, _temp) in BATHROOM_MODES.items()}


def intimate_mode_count(profile: DeviceProfile) -> int:
    return INTIMATE_MODE_COUNTS.get(profile, 0)


def intimate_mode_labels(profile: DeviceProfile) -> list[str]:
    return list(INTIMATE_MODE_LABELS.get(profile, ()))


def intimate_custom_step_limit(profile: DeviceProfile) -> int:
    return INTIMATE_CUSTOM_STEP_LIMITS.get(profile, 0)


def bathroom_mode_options() -> list[dict[str, str]]:
    return [{"value": name, "label": name.replace("_", " ").title()} for name in BATHROOM_MODE_NAME_TO_VALUE]

# Junk data filter
JUNK_DATA = "000102030405060708090A0B0C0D0E"

# ---------------------------------------------------------------------------
# KEY_DICTIONARY for XOR encryption
# ---------------------------------------------------------------------------

KEY_DICTIONARY = [
    226, 103,  87, 132,  63,  66,  59,  88, 176, 241, 188, 194, 123, 228, 209,  42,
     19, 100, 195, 219, 189, 176, 198,  24, 138, 237, 115, 187,  61, 152,  67, 146,
    176, 179, 140,  48, 182, 156,  17, 161, 183,  69, 137, 207,  17,  23,  47, 211,
     70, 177, 182, 141, 226,   4,  93, 106, 105,  24, 226,   2,  50,  89, 176, 161,
     51, 178, 182, 145, 201, 170, 180, 158, 158, 113, 175,  58,  94, 208, 239, 254,
     88, 147,  56,  27, 161, 254,  17,  48, 108, 109, 230,   7, 134, 147, 109, 130,
     12,  54,  36,   0,  61,   0,  41, 219, 129, 210, 119, 239,  42, 201,  35, 244,
     80, 133,  85,   7, 146,  55,  24, 124, 199, 165,  95,  11, 231, 161,  95, 149,
    192, 141,  35,   3, 129, 126,  45,  82,  50, 254, 114, 183, 222,   1, 163,  73,
    121,  75,   4, 181, 179, 196, 195, 200, 176, 113, 144,  44, 110, 181,  15,  76,
     19,  24, 231, 190, 104, 161, 131, 175,  47, 194, 186,  64, 156,  88,  37,  26,
     80,  53,  90, 165,  78, 228, 119, 240, 253, 144, 192,  67, 109,  14,  38, 145,
    139, 187, 101, 250, 179, 191,  68, 217,  46, 165, 120, 198,  52, 175, 106,  95,
      3,  99,  78,  16, 226, 248, 217, 149, 230, 131,   1, 203,  57,  11,  49, 216,
     92, 242, 131, 189,  53,  76,  93, 152,  33,  18, 138, 156, 246,   1, 227,  81,
    167,  20,  19, 209, 253, 243,  65, 104,  80,   2,   3, 148, 129, 167, 114, 187,
]

DEFAULT_ENCRYPTION_KEY = "gwin0801"
PROV_HOST = "10.10.100.254"
PROV_PORT = 9091
WRITE_DELAY = 0.25  # 250ms between BLE writes


# ---------------------------------------------------------------------------
# Protocol: encoding & decoding
# ---------------------------------------------------------------------------

class TingonProtocol:
    """Encode commands and decode responses for the TINGON BLE protocol."""

    @staticmethod
    def _pad(hex_str: str, width: int) -> str:
        return hex_str.zfill(width)

    @staticmethod
    def _get_spec_encoding(spec_id: int) -> tuple[str, int]:
        """Return (data_type, value_length) for a given spec ID."""
        if spec_id in (1, 3, 4, 17) or (spec_id in range(102, 112) and spec_id not in (104, 105, 106)):
            return ("01", 1)
        if spec_id in (5, 27, 105, 106) or spec_id in range(10, 16):
            return ("02", 1)
        if spec_id in (6, 7):
            return ("02", 4)
        if spec_id in (8, 9):
            return ("04", 1)
        if spec_id in (16, 104):
            return ("05", 1)
        if spec_id in (2, 18):
            return ("00", 0)  # variable
        # Fallback: treat as 1-byte int
        return ("02", 1)

    @staticmethod
    def encode_command(spec_id: int, value) -> str:
        """Encode a single-property command as a hex string."""
        data_type, val_len = TingonProtocol._get_spec_encoding(spec_id)
        spec_hex = TingonProtocol._pad(format(spec_id, "x"), 4)

        if data_type == "00":
            # Raw/variable: value is already a hex string
            val_hex = str(value)
            length_hex = TingonProtocol._pad(format(len(val_hex) // 2, "x"), 4)
        else:
            val_hex = TingonProtocol._pad(format(int(value), "x"), val_len * 2)
            length_hex = TingonProtocol._pad(format(val_len, "x"), 4)

        return f"01{spec_hex}{data_type}{length_hex}{val_hex}"

    @staticmethod
    def encode_multi_command(specs: dict) -> str:
        """Encode a multi-property command. specs = {spec_id: value, ...}"""
        items = list(specs.items())
        if len(items) == 1:
            return TingonProtocol.encode_command(items[0][0], items[0][1])

        count = TingonProtocol._pad(format(len(items), "x"), 2)
        parts = []
        for i, (spec_id, value) in enumerate(items):
            data_type, val_len = TingonProtocol._get_spec_encoding(spec_id)
            spec_hex = TingonProtocol._pad(format(spec_id, "x"), 4)

            if data_type == "00":
                val_hex = str(value)
                length_hex = TingonProtocol._pad(format(len(val_hex) // 2, "x"), 4)
            else:
                val_hex = TingonProtocol._pad(format(int(value), "x"), val_len * 2)
                length_hex = TingonProtocol._pad(format(val_len, "x"), 4)

            parts.append(f"{spec_hex}{data_type}{length_hex}{val_hex}")

        return count + "".join(parts)

    @staticmethod
    def build_query(spec_ids: list[int]) -> bytes:
        """Build a query JSON payload for the cc service."""
        payload = {
            "time": int(time.time() * 1000),
            "data": spec_ids,
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def parse_response(hex_str: str, signed_specs: set[int] | None = None) -> dict:
        """Parse a TLV hex response into {spec_id: value}."""
        if not hex_str or len(hex_str) < 4:
            return {}

        result = {}
        pos = 2  # skip header (2 hex chars = 1 byte)

        while pos + 10 <= len(hex_str):  # need at least specId(4) + type(2) + length(4)
            spec_id = int(hex_str[pos:pos + 4], 16)
            data_type = hex_str[pos + 4:pos + 6]
            data_len = int(hex_str[pos + 6:pos + 10], 16)
            pos += 10

            data_end = pos + data_len * 2
            if data_end > len(hex_str):
                break

            data_hex = hex_str[pos:data_end]
            pos = data_end

            if data_type == "00":
                # Raw value (timer data) - keep as hex string
                result[spec_id] = data_hex
            else:
                raw_val = int(data_hex, 16) if data_hex else 0
                if signed_specs and spec_id in signed_specs:
                    raw_val = TingonProtocol.signed_value(raw_val, data_len * 8)
                result[spec_id] = raw_val

        return result

    @staticmethod
    def signed_value(raw: int, bits: int = 16) -> int:
        """Convert unsigned int to signed using two's complement."""
        if raw >= (1 << (bits - 1)):
            raw -= (1 << bits)
        return raw

    @staticmethod
    def hex_to_bytes(hex_str: str) -> bytes:
        """Convert hex string to bytes."""
        hex_str = hex_str.replace(" ", "")
        return bytes.fromhex(hex_str)

    @staticmethod
    def bytes_to_hex(data: bytes) -> str:
        """Convert bytes to uppercase hex string."""
        return data.hex().upper()


@dataclass
class IntimateStatus:
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


class IntimateProtocol:
    POSITION_BYTES = {
        "front": "60",
        "middle": "61",
        "back": "62",
        "front_middle": "63",
        "middle_back": "64",
        "all": "65",
    }
    N2_MODE_LABELS = {
        0: "vibration",
        1: "electric_shock",
        2: "vibration_and_electric_shock",
    }

    @staticmethod
    def pad(hex_str: str, width: int = 2) -> str:
        return hex_str.zfill(width)

    @staticmethod
    def normalize_slider(value: int) -> int:
        value = max(0, min(100, int(value)))
        if value == 0:
            return 0
        if value <= 17:
            return 5
        if value <= 35:
            return 6
        if value <= 51:
            return 7
        if value <= 68:
            return 8
        if value <= 86:
            return 9
        return 10

    @staticmethod
    def encode_play(play: bool, mode: int = 1) -> str:
        return "0A0100" if not play else f"0A01{IntimateProtocol.pad(format(mode, 'x'))}"

    @staticmethod
    def encode_mode(mode: int) -> str:
        return f"0A01{IntimateProtocol.pad(format(mode, 'x'))}"

    @staticmethod
    def encode_dual_output(motor1: int, motor2: int, *, quantized: bool = False) -> str:
        if quantized:
            left = IntimateProtocol.normalize_slider(motor1)
            right = IntimateProtocol.normalize_slider(motor2)
        else:
            left = max(0, min(10, int(motor1) // 10))
            right = max(0, min(10, int(motor2) // 10))
        return (
            f"0A0240{IntimateProtocol.pad(format(left, 'x'))}"
            f"41{IntimateProtocol.pad(format(right, 'x'))}"
        )

    @staticmethod
    def encode_single_output(motor1: int) -> str:
        value = max(0, min(10, int(motor1) // 10))
        return f"0A0240{IntimateProtocol.pad(format(value, 'x'))}"

    @staticmethod
    def encode_position_speed(position: str, speed: int) -> str:
        pos_byte = IntimateProtocol.POSITION_BYTES[position]
        value = max(0, min(10, int(speed) // 10))
        return f"0A0202{pos_byte}{IntimateProtocol.pad(format(value, 'x'))}"

    @staticmethod
    def clamp_range_point(value: int) -> int:
        return max(0, min(92, int(value)))

    @staticmethod
    def normalize_range(start: int, end: int) -> tuple[int, int]:
        left = IntimateProtocol.clamp_range_point(start)
        right = IntimateProtocol.clamp_range_point(end)
        if left > right:
            left, right = right, left
        return left, right

    @staticmethod
    def divide_range(start: int, end: int, segments: int = 3) -> list[tuple[int, int]]:
        left, right = IntimateProtocol.normalize_range(start, end)
        span = (right - left) / float(segments)
        ranges: list[tuple[int, int]] = []
        for index in range(segments):
            seg_start = int(left + index * span)
            seg_end = int(left + (index + 1) * span)
            ranges.append((seg_start, seg_end))
        return ranges

    @staticmethod
    def encode_custom_range(start: int, end: int) -> str:
        parts = []
        for base, (seg_start, seg_end) in zip((0x50, 0x52, 0x54), IntimateProtocol.divide_range(start, end)):
            parts.append(f"{base:02X}{seg_start:02X}{base + 1:02X}{seg_end:02X}")
        return f"0A060C{''.join(parts)}"

    @staticmethod
    def encode_query_custom(slot_id: int) -> str:
        return f"0B02{IntimateProtocol.pad(format(slot_id, 'x'))}"

    @staticmethod
    def encode_custom(slot_id: int, items: list[tuple[int, int]]) -> str:
        body = "".join(
            f"{IntimateProtocol.pad(format(int(mode), 'x'))}"
            f"{IntimateProtocol.pad(format(int(sec), 'x'))}"
            for mode, sec in items
        )
        return (
            f"0A04{IntimateProtocol.pad(format(slot_id, 'x'))}"
            f"{IntimateProtocol.pad(format(len(body) // 2, 'x'))}{body}"
        )

    @staticmethod
    def decode_custom_hex(hex_str: str) -> list[dict[str, int]]:
        items = []
        for idx in range(0, len(hex_str), 4):
            chunk = hex_str[idx:idx + 4]
            if len(chunk) == 4:
                items.append({"mode": int(chunk[:2], 16), "sec": int(chunk[2:], 16)})
        return items

    @staticmethod
    def parse_notify(hex_str: str, profile: DeviceProfile) -> dict[str, int]:
        if not hex_str.startswith("02") or len(hex_str) < 4:
            return {}
        code = hex_str[2:4]
        if code == "40":
            if profile == DeviceProfile.M1 and len(hex_str) >= 10 and hex_str[6:8] == "41":
                return {
                    "motor1": int(hex_str[4:6], 16) * 10,
                    "motor2": int(hex_str[8:10], 16) * 10,
                }
            return {"motor1": int(hex_str[4:6], 16) * 10}
        if code == "41":
            return {"motor2": int(hex_str[4:6], 16) * 10}
        return {"mode": int(code, 16)}


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

class TingonEncryption:
    """XOR encryption/decryption for WiFi provisioning."""

    @staticmethod
    def xor_encrypt(plaintext: str, device_key: str) -> str:
        """XOR-encrypt a plaintext string, return lowercase hex."""
        data = plaintext.encode("utf-8")
        rand_byte = randint(0, 255)
        idx = int(device_key, 16) ^ rand_byte

        encrypted = bytearray(len(data))
        for i in range(len(data)):
            if idx >= len(KEY_DICTIONARY):
                idx = 0
            encrypted[i] = KEY_DICTIONARY[idx] ^ data[i]
            idx += 1

        return format(rand_byte, "02x") + encrypted.hex()

    @staticmethod
    def xor_decrypt(encrypted_hex: str, device_key: str) -> str:
        """XOR-decrypt an encrypted hex string, return plaintext."""
        rand_byte = int(encrypted_hex[:2], 16)
        ciphertext = bytes.fromhex(encrypted_hex[2:])
        idx = int(device_key, 16) ^ rand_byte

        decrypted = bytearray(len(ciphertext))
        for i in range(len(ciphertext)):
            if idx >= len(KEY_DICTIONARY):
                idx = 0
            decrypted[i] = KEY_DICTIONARY[idx] ^ ciphertext[i]
            idx += 1

        return decrypted.decode("utf-8", errors="replace")

    @staticmethod
    def extract_device_key(manufacturer_data: bytes) -> str:
        """Extract the 2-char hex encryption key from manufacturer advertisement data."""
        hex_str = manufacturer_data.hex()
        if len(hex_str) >= 8:
            return hex_str[-8:-6]
        return "41"  # default fallback

    @staticmethod
    def crc_xmodem(data: bytes) -> int:
        """CRC-XModem checksum."""
        crc = 0
        for byte in data:
            for bit in range(8):
                xor_flag = ((byte >> (7 - bit)) & 1) == 1
                crc_msb = ((crc >> 15) & 1) == 1
                crc <<= 1
                if xor_flag ^ crc_msb:
                    crc ^= 0x1021
        return crc & 0xFFFF


# ---------------------------------------------------------------------------
# BLE Device
# ---------------------------------------------------------------------------

@dataclass
class ScannedDevice:
    address: str
    name: str
    rssi: int
    device_type: Optional[DeviceType] = None
    profile: Optional[DeviceProfile] = None
    mac_from_adv: Optional[str] = None
    device_key: str = "41"
    raw_manufacturer_data: Optional[bytes] = None


class TingonDevice:
    """Async BLE controller for TINGON IoT devices."""

    def __init__(self):
        self._client: Optional[BleakClient] = None
        self._address: Optional[str] = None
        self._device_type: Optional[DeviceType] = None
        self._profile: Optional[DeviceProfile] = None
        self._device_key: str = "41"
        self._response_data: str = ""
        self._response_event = asyncio.Event()
        self._query_data: str = ""
        self._query_event = asyncio.Event()
        self._intimate_status = IntimateStatus()

    @property
    def is_dehumidifier(self) -> bool:
        return self._device_type in DEHUMIDIFIER_TYPES

    @property
    def is_water_heater(self) -> bool:
        return self._device_type in WATER_HEATER_TYPES

    @property
    def profile(self) -> Optional[DeviceProfile]:
        return self._profile

    @property
    def profile_meta(self) -> Optional[ProfileInfo]:
        return profile_info(self._profile) if self._profile else None

    @property
    def is_appliance(self) -> bool:
        return self.profile_meta is not None and self.profile_meta.family == ProtocolFamily.APPLIANCE

    @property
    def is_intimate(self) -> bool:
        return self.profile_meta is not None and self.profile_meta.family == ProtocolFamily.INTIMATE

    def has_capability(self, capability: str) -> bool:
        return self.profile_meta is not None and capability in self.profile_meta.capabilities

    def require_capability(self, capability: str):
        if not self.has_capability(capability):
            prof = self._profile.value if self._profile else "unknown"
            raise ValueError(f"Profile '{prof}' does not support '{capability}'")

    @property
    def specs(self) -> dict[int, SpecDef]:
        if self.is_water_heater:
            return WATER_HEATER_SPECS
        return DEHUMIDIFIER_SPECS

    @property
    def query_ids(self) -> list[int]:
        if self.is_water_heater:
            return WATER_HEATER_QUERY_IDS
        return DEHUMIDIFIER_QUERY_IDS

    @property
    def signed_specs(self) -> set[int]:
        if self.is_water_heater:
            return WATER_HEATER_SIGNED_SPECS
        return DEHUMIDIFIER_SIGNED_SPECS

    # -- Scanning --

    @staticmethod
    def _require_bleak():
        if BleakClient is None or BleakScanner is None:
            raise RuntimeError("bleak is not installed. Install it with: pip install bleak")

    @staticmethod
    async def scan(name_filter: str = "", timeout: float = 10.0) -> list[ScannedDevice]:
        """Scan for TINGON BLE devices."""
        TingonDevice._require_bleak()
        found: dict[str, ScannedDevice] = {}

        def callback(device: BLEDevice, adv: AdvertisementData):
            if name_filter and device.name and name_filter.lower() not in device.name.lower():
                return
            if not device.name:
                return

            sd = ScannedDevice(
                address=device.address,
                name=device.name or "Unknown",
                rssi=adv.rssi,
            )

            # Parse manufacturer data
            if adv.manufacturer_data:
                for _company_id, mfr_data in adv.manufacturer_data.items():
                    sd.raw_manufacturer_data = mfr_data
                    sd.device_key = TingonEncryption.extract_device_key(mfr_data)
                    if len(mfr_data) > 11:
                        dev_type_byte = mfr_data[10]
                        sub_version = mfr_data[11] if len(mfr_data) > 11 else 0
                        if dev_type_byte == 0 and sub_version == 2:
                            sd.device_type = DeviceType.FJB_SECOND
                        elif dev_type_byte in (0, 1, 2, 3):
                            sd.device_type = DeviceType(dev_type_byte)
                    if len(mfr_data) >= 19:
                        mac_bytes = mfr_data[13:19]
                        sd.mac_from_adv = ":".join(f"{b:02X}" for b in mac_bytes)
                    break

            if sd.device_type is not None:
                sd.profile = APPLIANCE_TYPE_TO_PROFILE[sd.device_type]
            else:
                sd.profile = DeviceProfile.parse(sd.name, fuzzy=True)

            found[device.address] = sd

        scanner = BleakScanner(detection_callback=callback)
        await scanner.start()
        await asyncio.sleep(timeout)
        await scanner.stop()

        return list(found.values())

    # -- Connection --

    async def connect(
        self,
        address: str,
        device_type: Optional[DeviceType] = None,
        profile: Optional[DeviceProfile] = None,
    ):
        """Connect to a TINGON device."""
        self._require_bleak()
        self._address = address
        self._device_type = device_type
        self._profile = profile or (APPLIANCE_TYPE_TO_PROFILE[device_type] if device_type is not None else None)
        if self._profile is not None and self.profile_meta and self.profile_meta.appliance_type is not None:
            self._device_type = self.profile_meta.appliance_type
        self._client = BleakClient(address)
        await self._client.connect()

        # Subscribe to notifications
        try:
            await self._client.start_notify(CHR_CMD_NOTIFY, self._cmd_notification_handler)
        except Exception as e:
            print(f"Warning: Could not subscribe to command notifications (ee04): {e}")

        if self.is_appliance or self._profile is None:
            try:
                await self._client.start_notify(CHR_QUERY_NOTIFY, self._query_notification_handler)
            except Exception as e:
                print(f"Warning: Could not subscribe to query notifications (cc03): {e}")

        print(f"Connected to {address}")
        if self.profile_meta is not None:
            print(f"Profile: {self.profile_meta.display_name} ({self.profile_meta.category})")
        elif self._device_type is not None:
            category = "Dehumidifier" if self.is_dehumidifier else "Water Heater"
            print(f"Device type: {self._device_type.name} ({category})")

    async def disconnect(self):
        """Disconnect from the device."""
        if self._client and self._client.is_connected:
            await self._client.disconnect()
            print("Disconnected")
        self._client = None

    # -- Notification handlers --

    def _cmd_notification_handler(self, _characteristic, data: bytearray):
        hex_data = data.hex().upper()
        if hex_data == JUNK_DATA:
            return
        self._response_data += hex_data
        if self.is_intimate:
            parsed = IntimateProtocol.parse_notify(hex_data, self._profile)
            if "mode" in parsed:
                self._intimate_status.mode = parsed["mode"]
                self._intimate_status.play = parsed["mode"] != 0
            if "motor1" in parsed:
                self._intimate_status.motor1 = parsed["motor1"]
                self._intimate_status.play = self._intimate_status.motor1 > 0 or self._intimate_status.motor2 > 0
            if "motor2" in parsed:
                self._intimate_status.motor2 = parsed["motor2"]
                self._intimate_status.play = self._intimate_status.motor1 > 0 or self._intimate_status.motor2 > 0
        if len(data) < 20:
            self._response_event.set()

    def _query_notification_handler(self, _characteristic, data: bytearray):
        hex_data = data.hex().upper()
        self._query_data += hex_data
        if len(data) < 20:
            self._query_event.set()

    # -- Low-level writes --

    async def _write_ee(self, data: bytes):
        """Write to the ee02 command characteristic."""
        await self._client.write_gatt_char(CHR_CMD_WRITE, data, response=True)
        await asyncio.sleep(WRITE_DELAY)

    async def _write_cc(self, data: bytes):
        """Write to the cc02 query characteristic."""
        await self._client.write_gatt_char(CHR_QUERY_WRITE, data, response=True)
        await asyncio.sleep(WRITE_DELAY)

    async def _write_ff_chunked(self, data: bytes) -> Optional[str]:
        """Write chunked data to the ff03 provisioning characteristic."""
        chunk_size = 18
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        packet_id = randint(0, 255)

        # Subscribe to provisioning notifications
        prov_data = ""
        prov_event = asyncio.Event()

        def prov_handler(_char, recv_data: bytearray):
            nonlocal prov_data
            prov_data += recv_data.hex().upper()
            if len(recv_data) < 20:
                prov_event.set()

        await self._client.start_notify(CHR_PROV_NOTIFY, prov_handler)

        for i, chunk in enumerate(chunks):
            packet = bytes([packet_id, i + 1]) + chunk
            await self._client.write_gatt_char(CHR_PROV_WRITE, packet, response=True)
            await asyncio.sleep(WRITE_DELAY)

        # Send terminator if last chunk was exactly 18 bytes
        if len(chunks[-1]) == chunk_size:
            terminator = bytes([packet_id, len(chunks) + 1])
            await self._client.write_gatt_char(CHR_PROV_WRITE, terminator, response=True)

        # Wait for response
        try:
            await asyncio.wait_for(prov_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            print("Provisioning response timeout")
            return None
        finally:
            await self._client.stop_notify(CHR_PROV_NOTIFY)

        return prov_data

    # -- Generic commands --

    async def send_command(self, spec_id: int, value) -> Optional[dict]:
        """Send a single-property command and return parsed response."""
        hex_cmd = TingonProtocol.encode_command(spec_id, value)
        self._response_data = ""
        self._response_event.clear()

        await self._write_ee(TingonProtocol.hex_to_bytes(hex_cmd))

        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            print("Command response timeout")
            return None

        return TingonProtocol.parse_response(self._response_data, self.signed_specs)

    async def send_multi_command(self, specs: dict) -> Optional[dict]:
        """Send a multi-property command and return parsed response."""
        hex_cmd = TingonProtocol.encode_multi_command(specs)
        self._response_data = ""
        self._response_event.clear()

        await self._write_ee(TingonProtocol.hex_to_bytes(hex_cmd))

        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            print("Command response timeout")
            return None

        return TingonProtocol.parse_response(self._response_data, self.signed_specs)

    async def send_raw_hex(self, hex_str: str):
        """Send a raw hex string command."""
        await self._write_ee(TingonProtocol.hex_to_bytes(hex_str))

    # -- Queries --

    async def query_all(self) -> Optional[dict]:
        """Query all device properties, returns {spec_id: value}."""
        return await self.query_specs(self.query_ids)

    async def query_specs(self, spec_ids: list[int]) -> Optional[dict]:
        """Query specific device properties."""
        if self.is_intimate:
            raise ValueError("Spec queries are only supported for appliance profiles")
        query_bytes = TingonProtocol.build_query(spec_ids)
        self._query_data = ""
        self._query_event.clear()

        await self._write_cc(query_bytes)

        try:
            await asyncio.wait_for(self._query_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            print("Query response timeout")
            return None

        return TingonProtocol.parse_response(self._query_data, self.signed_specs)

    async def get_status(self) -> Optional[dict]:
        """Query all properties and return a human-readable dict with named keys."""
        if self.is_intimate:
            result = {
                "play": self._intimate_status.play,
                "mode": self._intimate_status.mode,
                "motor1": self._intimate_status.motor1,
                "motor2": self._intimate_status.motor2,
                "custom_mode": self._intimate_status.custom_mode,
            }
            if self.has_capability(CAP_POSITION):
                result["position"] = self._intimate_status.position
                result["range_start"] = self._intimate_status.range_start
                result["range_end"] = self._intimate_status.range_end
            if self.has_capability(CAP_N2_MODE):
                result["n2_mode"] = IntimateProtocol.N2_MODE_LABELS.get(
                    self._intimate_status.n2_mode,
                    self._intimate_status.n2_mode,
                )
            for slot_id, items in self._intimate_status.custom_slots.items():
                result[f"custom_{slot_id}"] = items
            return result

        raw = await self.query_all()
        if raw is None:
            return None

        result = {}
        specs = self.specs
        for spec_id, value in raw.items():
            if spec_id in specs:
                result[specs[spec_id].name] = value
            else:
                result[f"spec_{spec_id}"] = value

        return result

    # -- Convenience: power (both device types) --

    async def set_power(self, on: bool) -> Optional[dict]:
        return await self.send_command(1, 1 if on else 0)

    # -- Convenience: dehumidifier --

    async def set_target_humidity(self, percent: int) -> Optional[dict]:
        return await self.send_command(5, percent)

    async def set_drainage(self, on: bool) -> Optional[dict]:
        return await self.send_command(3, 1 if on else 0)

    async def set_dehumidification(self, on: bool) -> Optional[dict]:
        return await self.send_command(4, 1 if on else 0)

    async def set_timer(self, timer_hex: str, remind_hex: str = "") -> Optional[dict]:
        specs = {2: timer_hex}
        if remind_hex:
            specs[18] = remind_hex
        return await self.send_multi_command(specs)

    # -- Convenience: water heater --

    async def set_water_temperature(self, temp: int) -> Optional[dict]:
        return await self.send_command(7, temp)

    async def set_bathroom_mode(self, mode: int) -> Optional[dict]:
        """Set bathroom mode: 1=normal, 2=kitchen, 4=eco, 5=season."""
        return await self.send_command(2, format(mode, "02x"))

    async def set_cruise_insulation_temp(self, temp: int) -> Optional[dict]:
        return await self.send_command(105, temp)

    async def set_zero_cold_water_mode(self, mode: int) -> Optional[dict]:
        """Set zero-cold-water mode: 0=off, 1=on, 3=enhanced."""
        return await self.send_command(106, mode)

    async def set_eco_cruise(self, on: bool) -> Optional[dict]:
        return await self.send_command(107, 1 if on else 0)

    async def set_water_pressurization(self, on: bool) -> Optional[dict]:
        return await self.send_command(108, 1 if on else 0)

    # -- Convenience: intimate devices --

    async def intimate_play(self, play: bool, mode: Optional[int] = None):
        self.require_capability(CAP_PLAY)
        current_mode = mode if mode is not None else max(self._intimate_status.mode, 1)
        await self.send_raw_hex(IntimateProtocol.encode_play(play, current_mode))
        self._intimate_status.play = play
        if not play:
            self._intimate_status.mode = 0
            self._intimate_status.custom_mode = None

    async def intimate_set_mode(self, mode: int):
        self.require_capability(CAP_PRESET_MODE)
        await self.send_raw_hex(IntimateProtocol.encode_mode(mode))
        self._intimate_status.mode = int(mode)
        self._intimate_status.play = mode != 0
        self._intimate_status.custom_mode = None
        self._intimate_status.motor1 = 0
        self._intimate_status.motor2 = 0

    async def intimate_use_custom(self, slot_id: int):
        self.require_capability(CAP_CUSTOM)
        if slot_id not in (32, 33, 34):
            raise ValueError("Custom slots must be 32, 33, or 34")
        await self.send_raw_hex(IntimateProtocol.encode_mode(slot_id))
        self._intimate_status.play = True
        self._intimate_status.mode = 0
        self._intimate_status.custom_mode = int(slot_id)
        self._intimate_status.motor1 = 0
        self._intimate_status.motor2 = 0

    async def intimate_set_output(self, motor1: int, motor2: Optional[int] = None):
        self.require_capability(CAP_MOTOR1)
        if self._profile == DeviceProfile.M2:
            await self.send_raw_hex(
                IntimateProtocol.encode_position_speed(
                    self._intimate_status.position,
                    motor1,
                )
            )
            self._intimate_status.motor1 = int(motor1)
        elif self._profile == DeviceProfile.M1:
            self.require_capability(CAP_MOTOR2)
            if motor2 is None:
                motor2 = self._intimate_status.motor2
            await self.send_raw_hex(
                IntimateProtocol.encode_dual_output(motor1, motor2, quantized=True)
            )
            self._intimate_status.motor1 = int(motor1)
            self._intimate_status.motor2 = int(motor2)
        elif self._profile == DeviceProfile.N2:
            if motor2 is not None:
                await self.send_raw_hex(
                    IntimateProtocol.encode_dual_output(motor1, motor2, quantized=False)
                )
                self._intimate_status.motor2 = int(motor2)
            else:
                await self.send_raw_hex(IntimateProtocol.encode_single_output(motor1))
            self._intimate_status.motor1 = int(motor1)
        else:
            await self.send_raw_hex(IntimateProtocol.encode_single_output(motor1))
            self._intimate_status.motor1 = int(motor1)

        self._intimate_status.play = self._intimate_status.motor1 > 0 or self._intimate_status.motor2 > 0
        self._intimate_status.mode = 0
        self._intimate_status.custom_mode = None

    async def intimate_set_position(self, position: str):
        self.require_capability(CAP_POSITION)
        normalized = position.lower().replace("-", "_")
        if normalized not in IntimateProtocol.POSITION_BYTES:
            raise ValueError(f"Unknown position '{position}'")
        self._intimate_status.position = normalized
        await self.send_raw_hex(
            IntimateProtocol.encode_position_speed(normalized, self._intimate_status.motor1)
        )

    async def intimate_set_custom_range(self, start: int, end: int):
        self.require_capability(CAP_CUSTOM_RANGE)
        normalized_start, normalized_end = IntimateProtocol.normalize_range(start, end)
        await self.send_raw_hex(IntimateProtocol.encode_custom_range(normalized_start, normalized_end))
        self._intimate_status.range_start = normalized_start
        self._intimate_status.range_end = normalized_end

    async def intimate_set_n2_mode(self, mode_name: str):
        self.require_capability(CAP_N2_MODE)
        lookup = {label: idx for idx, label in IntimateProtocol.N2_MODE_LABELS.items()}
        if mode_name not in lookup:
            raise ValueError(f"Unknown N2 mode '{mode_name}'")
        self._intimate_status.n2_mode = lookup[mode_name]

    async def intimate_query_custom(self, slot_id: int) -> list[dict[str, int]]:
        self.require_capability(CAP_CUSTOM)
        if slot_id not in (32, 33, 34):
            raise ValueError("Custom slots must be 32, 33, or 34")
        self._response_data = ""
        self._response_event.clear()
        await self.send_raw_hex(IntimateProtocol.encode_query_custom(slot_id))
        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            return self._intimate_status.custom_slots[slot_id]

        if self._response_data.startswith("0A04") and len(self._response_data) >= 8:
            payload_len = int(self._response_data[6:8], 16) * 2
            body = self._response_data[8:8 + payload_len]
            self._intimate_status.custom_slots[slot_id] = IntimateProtocol.decode_custom_hex(body)
        return self._intimate_status.custom_slots[slot_id]

    async def intimate_set_custom(self, slot_id: int, items: list[tuple[int, int]]):
        self.require_capability(CAP_CUSTOM)
        if slot_id not in (32, 33, 34):
            raise ValueError("Custom slots must be 32, 33, or 34")
        await self.send_raw_hex(IntimateProtocol.encode_custom(slot_id, items))
        self._intimate_status.custom_slots[slot_id] = [
            {"mode": int(mode), "sec": int(sec)} for mode, sec in items
        ]

    # -- WiFi Provisioning --

    async def provision_wifi(self, ssid: str, password: str,
                             config_url: str = "", encrypt: bool = True) -> Optional[dict]:
        """Provision WiFi credentials via BLE (ff service)."""
        payload = {
            "CID": 30005,
            "PL": {"SSID": ssid, "Password": password},
            "URL": config_url,
        }
        json_str = json.dumps(payload, separators=(",", ":"))

        if encrypt:
            encrypted_hex = TingonEncryption.xor_encrypt(json_str, self._device_key)
            data = bytes.fromhex(encrypted_hex)
        else:
            data = json_str.encode("utf-8")

        response_hex = await self._write_ff_chunked(data)
        if not response_hex:
            return None

        # Decrypt and parse response
        try:
            if encrypt:
                decrypted = TingonEncryption.xor_decrypt(response_hex.lower(), self._device_key)
                # Extract JSON from decrypted string
                start = decrypted.index("{")
                end = decrypted.rindex("}") + 1
                json_str = decrypted[start:end]
            else:
                json_str = bytes.fromhex(response_hex).decode("utf-8", errors="replace")

            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"Failed to parse provisioning response: {e}")
            return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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


def add_profile_arg(parser, required: bool = True):
    parser.add_argument(
        "--profile",
        required=required,
        help="Profile: fjb, fjb2, gs, rj, a1, n1, n2, m1, m2",
    )


def resolve_profile_arg(args) -> DeviceProfile:
    profile = DeviceProfile.parse(getattr(args, "profile", None))
    if profile is None:
        raise ValueError("--profile is required")
    return profile


async def connect_for_args(args) -> TingonDevice:
    dev = TingonDevice()
    profile = resolve_profile_arg(args)
    meta = profile_info(profile)
    await dev.connect(args.address, device_type=meta.appliance_type, profile=profile)
    return dev


async def cmd_scan(args):
    print(f"Scanning for TINGON devices ({args.timeout}s)...")
    devices = await TingonDevice.scan(name_filter=args.name or "", timeout=args.timeout)
    if not devices:
        print("No devices found.")
        return

    print(f"\nFound {len(devices)} device(s):\n")
    for d in devices:
        type_str = f" [{d.profile.value}]" if d.profile is not None else ""
        mac_str = f" (ADV MAC: {d.mac_from_adv})" if d.mac_from_adv else ""
        print(f"  {d.address}  {d.name}  RSSI: {d.rssi}{type_str}{mac_str}")


async def cmd_status(args):
    dev = await connect_for_args(args)
    try:
        status = await dev.get_status()
        if status:
            print("\nDevice Status:")
            print(format_status(status, dev.profile))
        else:
            print("Failed to get device status.")
    finally:
        await dev.disconnect()


async def cmd_power(args):
    dev = await connect_for_args(args)
    try:
        on = args.state.lower() == "on"
        result = await dev.set_power(on)
        print(f"Power {'ON' if on else 'OFF'}: {result}")
    finally:
        await dev.disconnect()


async def cmd_humidity(args):
    dev = await connect_for_args(args)
    try:
        result = await dev.set_target_humidity(args.percent)
        print(f"Target humidity set to {args.percent}%: {result}")
    finally:
        await dev.disconnect()


async def cmd_temp(args):
    dev = await connect_for_args(args)
    try:
        result = await dev.set_water_temperature(args.degrees)
        print(f"Water temperature set to {args.degrees}C: {result}")
    finally:
        await dev.disconnect()


async def cmd_mode(args):
    dev = await connect_for_args(args)
    try:
        if dev.is_appliance:
            mode_val = BATHROOM_MODE_NAME_TO_VALUE.get(args.mode.lower())
            if mode_val is None:
                raise ValueError("Unknown bathroom mode. Use: normal, kitchen, eco, season")
            result = await dev.set_bathroom_mode(mode_val)
            print(f"Bathroom mode set to {args.mode}: {result}")
        else:
            await dev.intimate_set_mode(int(args.mode))
            print(f"Preset mode set to {args.mode}")
    finally:
        await dev.disconnect()


async def cmd_play(args):
    dev = await connect_for_args(args)
    try:
        await dev.intimate_play(args.state == "on", args.mode)
        print(f"Playback {'started' if args.state == 'on' else 'stopped'}")
    finally:
        await dev.disconnect()


async def cmd_motor(args):
    dev = await connect_for_args(args)
    try:
        await dev.intimate_set_output(args.motor1, args.motor2)
        print(f"Output updated: motor1={args.motor1}, motor2={args.motor2}")
    finally:
        await dev.disconnect()


async def cmd_position(args):
    dev = await connect_for_args(args)
    try:
        await dev.intimate_set_position(args.position)
        print(f"Position set to {args.position}")
    finally:
        await dev.disconnect()


async def cmd_n2_mode(args):
    dev = await connect_for_args(args)
    try:
        await dev.intimate_set_n2_mode(args.name)
        print(f"N2 mode set to {args.name}")
    finally:
        await dev.disconnect()


async def cmd_custom_get(args):
    dev = await connect_for_args(args)
    try:
        items = await dev.intimate_query_custom(args.slot)
        print(json.dumps(items, indent=2))
    finally:
        await dev.disconnect()


async def cmd_custom_set(args):
    dev = await connect_for_args(args)
    try:
        items = []
        for item in args.items:
            mode_raw, sec_raw = item.split(":", 1)
            items.append((int(mode_raw), int(sec_raw)))
        await dev.intimate_set_custom(args.slot, items)
        print(f"Custom slot {args.slot} updated with {len(items)} step(s)")
    finally:
        await dev.disconnect()


async def cmd_provision(args):
    dev = await connect_for_args(args)
    try:
        result = await dev.provision_wifi(args.ssid, args.password, config_url=args.url or "")
        if result:
            print("\nProvisioning result:")
            for k, v in result.items():
                print(f"  {k}: {v}")
        else:
            print("Provisioning failed or timed out.")
    finally:
        await dev.disconnect()


async def cmd_raw(args):
    dev = await connect_for_args(args)
    try:
        await dev.send_raw_hex(args.hex)
        print("Sent raw command")
    finally:
        await dev.disconnect()


async def cmd_interactive(args):
    dev = await connect_for_args(args)
    print("\nInteractive mode. Commands:")
    print("  status")
    if dev.is_appliance:
        print("  power on/off")
        if dev.has_capability(CAP_HUMIDITY):
            print("  humidity <n>")
            print("  drainage on/off")
            print("  dehum on/off")
        if dev.has_capability(CAP_WATER_TEMP):
            print("  temp <n>")
            print("  mode normal|kitchen|eco|season")
    else:
        print("  play on/off [mode]")
        print("  mode <n>")
        print("  motor <n> [motor2]")
        if dev.has_capability(CAP_POSITION):
            print("  position front|middle|back|front_middle|middle_back|all")
        if dev.has_capability(CAP_N2_MODE):
            print("  n2mode vibration|electric_shock|vibration_and_electric_shock")
        if dev.has_capability(CAP_CUSTOM):
            print("  custom_get <32|33|34>")
            print("  custom_set <slot> <mode:sec> [mode:sec] ...")
    print("  raw <hex>")
    print("  quit")
    print()

    try:
        while True:
            try:
                line = input("tingon> ").strip()
            except EOFError:
                break
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()
            try:
                if cmd in {"quit", "exit"}:
                    break
                if cmd == "status":
                    status = await dev.get_status()
                    if status:
                        print(format_status(status, dev.profile))
                elif cmd == "raw" and len(parts) > 1:
                    await dev.send_raw_hex("".join(parts[1:]))
                    print("Sent raw command")
                elif dev.is_appliance and cmd == "power" and len(parts) > 1:
                    print(await dev.set_power(parts[1].lower() == "on"))
                elif dev.is_appliance and cmd == "humidity" and len(parts) > 1:
                    print(await dev.set_target_humidity(int(parts[1])))
                elif dev.is_appliance and cmd == "drainage" and len(parts) > 1:
                    print(await dev.set_drainage(parts[1].lower() == "on"))
                elif dev.is_appliance and cmd == "dehum" and len(parts) > 1:
                    print(await dev.set_dehumidification(parts[1].lower() == "on"))
                elif dev.is_appliance and cmd == "temp" and len(parts) > 1:
                    print(await dev.set_water_temperature(int(parts[1])))
                elif dev.is_appliance and cmd == "mode" and len(parts) > 1:
                    print(await dev.set_bathroom_mode(BATHROOM_MODE_NAME_TO_VALUE[parts[1].lower()]))
                elif dev.is_intimate and cmd == "play" and len(parts) > 1:
                    await dev.intimate_play(parts[1].lower() == "on", int(parts[2]) if len(parts) > 2 else None)
                elif dev.is_intimate and cmd == "mode" and len(parts) > 1:
                    await dev.intimate_set_mode(int(parts[1]))
                elif dev.is_intimate and cmd == "motor" and len(parts) > 1:
                    await dev.intimate_set_output(int(parts[1]), int(parts[2]) if len(parts) > 2 else None)
                elif dev.is_intimate and cmd == "position" and len(parts) > 1:
                    await dev.intimate_set_position(parts[1])
                elif dev.is_intimate and cmd == "n2mode" and len(parts) > 1:
                    await dev.intimate_set_n2_mode(parts[1])
                elif dev.is_intimate and cmd == "custom_get" and len(parts) > 1:
                    print(json.dumps(await dev.intimate_query_custom(int(parts[1])), indent=2))
                elif dev.is_intimate and cmd == "custom_set" and len(parts) > 2:
                    items = []
                    for item in parts[2:]:
                        mode_raw, sec_raw = item.split(":", 1)
                        items.append((int(mode_raw), int(sec_raw)))
                    await dev.intimate_set_custom(int(parts[1]), items)
                else:
                    print(f"Unknown command: {line}")
            except Exception as exc:
                print(f"Error: {exc}")
    finally:
        await dev.disconnect()


class MockTingonDevice:
    """Reusable in-memory controller for testing without BLE hardware."""

    def __init__(self, address: str, profile: DeviceProfile, name: str):
        self._address = address
        self._profile = profile
        self._name = name
        self._status = default_mock_status(profile)

    @property
    def profile(self) -> DeviceProfile:
        return self._profile

    @property
    def profile_meta(self) -> ProfileInfo:
        return profile_info(self._profile)

    def has_capability(self, capability: str) -> bool:
        return capability in self.profile_meta.capabilities

    async def connect(self, _address: str, profile: Optional[DeviceProfile] = None):
        if profile is not None:
            self._profile = profile

    async def disconnect(self):
        return None

    async def get_status(self) -> dict:
        return json.loads(json.dumps(self._status))

    async def set_power(self, on: bool):
        self._status["power"] = 1 if on else 0

    async def set_target_humidity(self, percent: int):
        self._status["target_hum"] = percent

    async def set_drainage(self, on: bool):
        self._status["drainage"] = 1 if on else 0

    async def set_dehumidification(self, on: bool):
        self._status["dehumidification"] = 1 if on else 0

    async def set_water_temperature(self, temp: int):
        self._status["setting_water_temp"] = temp
        self._status["outlet_water_temp"] = max(0, temp - 2)

    async def set_bathroom_mode(self, mode: int):
        self._status["bathroom_mode"] = mode
        if mode in BATHROOM_MODES and BATHROOM_MODES[mode][1] is not None:
            self._status["setting_water_temp"] = BATHROOM_MODES[mode][1]

    async def intimate_play(self, play: bool, mode: Optional[int]):
        self._status["play"] = play
        if mode is not None:
            self._status["mode"] = mode
        if play and self._status.get("motor1", 0) == 0 and self.has_capability(CAP_MOTOR1):
            self._status["motor1"] = 50
        if not play:
            self._status["motor1"] = 0
            if self.has_capability(CAP_MOTOR2):
                self._status["motor2"] = 0

    async def intimate_set_mode(self, mode: int):
        self._status["mode"] = mode
        self._status["play"] = True
        self._status["custom_mode"] = None

    async def intimate_use_custom(self, slot_id: int):
        self._status["play"] = True
        self._status["mode"] = 0
        self._status["custom_mode"] = slot_id

    async def intimate_set_output(self, motor1: int, motor2: Optional[int]):
        self._status["motor1"] = motor1
        if motor2 is not None and self.has_capability(CAP_MOTOR2):
            self._status["motor2"] = motor2
        self._status["play"] = motor1 > 0 or self._status.get("motor2", 0) > 0
        self._status["mode"] = 0
        self._status["custom_mode"] = None

    async def intimate_set_position(self, position: str):
        self._status["position"] = position

    async def intimate_set_custom_range(self, start: int, end: int):
        start, end = IntimateProtocol.normalize_range(start, end)
        self._status["range_start"] = start
        self._status["range_end"] = end

    async def intimate_set_n2_mode(self, mode_name: str):
        self._status["n2_mode"] = mode_name

    async def intimate_query_custom(self, _slot_id: int):
        return None

    async def intimate_set_custom(self, slot_id: int, items: list[tuple[int, int]]):
        self._status[f"custom_{slot_id}"] = [{"mode": mode, "sec": sec} for mode, sec in items]


def mock_device_catalog() -> list[tuple[DeviceProfile, str]]:
    return [
        (DeviceProfile.FJB, "XPOWER Dry 120"),
        (DeviceProfile.FJB2, "XPOWER Dry 220"),
        (DeviceProfile.GS, "Wanhe Heater GS"),
        (DeviceProfile.RJ, "Wanhe Heater RJ"),
        (DeviceProfile.A1, "TINGON A1"),
        (DeviceProfile.N1, "TINGON N1"),
        (DeviceProfile.N2, "TINGON N2"),
        (DeviceProfile.M1, "TINGON M1"),
        (DeviceProfile.M2, "TINGON M2"),
    ]


def default_mock_status(profile: DeviceProfile) -> dict:
    if profile in {DeviceProfile.FJB, DeviceProfile.FJB2}:
        return {
            "power": 1,
            "target_hum": 55 if profile == DeviceProfile.FJB else 48,
            "drainage": 0,
            "dehumidification": 1,
            "air_intake_temp": 24,
            "air_intake_hum": 62,
            "air_outlet_temp": 28,
            "air_outlet_hum": 46,
            "eva_temp": 18,
            "wind_speed": 3,
            "compressor_status": 1,
            "error": 0,
            "defrost": 0,
            "work_time": 1380,
            "total_work_time": 22410,
        }
    if profile in {DeviceProfile.GS, DeviceProfile.RJ}:
        return {
            "power": 1,
            "bathroom_mode": 1 if profile == DeviceProfile.GS else 2,
            "setting_water_temp": 50 if profile == DeviceProfile.GS else 42,
            "inlet_water_temp": 22,
            "outlet_water_temp": 48 if profile == DeviceProfile.GS else 40,
            "wind_status": 1,
            "discharge": 0,
            "water_status": 1,
            "fire_status": 1,
            "equipment_failure": 0,
            "zero_cold_water_mode": 1,
            "eco_cruise": 0,
        }
    base = {
        "play": False,
        "mode": 1,
        "motor1": 0,
        "motor2": 0,
        "custom_mode": None,
    }
    if profile == DeviceProfile.M1:
        base.update({"play": True, "motor1": 65, "motor2": 28})
    elif profile == DeviceProfile.A1:
        base.update({"play": True, "motor1": 54})
    elif profile == DeviceProfile.N1:
        base.update({"play": True, "motor1": 36})
    elif profile == DeviceProfile.M2:
        base.update({"play": True, "motor1": 72, "position": "middle", "range_start": 12, "range_end": 78})
    elif profile == DeviceProfile.N2:
        base.update({"play": True, "motor1": 48, "motor2": 22, "n2_mode": "vibration"})
    for slot_id, items in {
        32: [{"mode": 1, "sec": 12}, {"mode": 4, "sec": 8}],
        33: [{"mode": 2, "sec": 10}, {"mode": 6, "sec": 6}, {"mode": 3, "sec": 9}],
        34: [{"mode": 5, "sec": 14}],
    }.items():
        base[f"custom_{slot_id}"] = items
    return base


def mock_scan_devices(name_filter: str = "") -> list[ScannedDevice]:
    query = name_filter.lower().strip()
    devices: list[ScannedDevice] = []
    for index, (profile, device_name) in enumerate(mock_device_catalog(), start=1):
        if query and query not in device_name.lower() and query not in profile.value.lower():
            continue
        address = f"FA:KE:00:00:{index:02X}:{index + 16:02X}"
        devices.append(
            ScannedDevice(
                address=address,
                name=device_name,
                rssi=-32 - index * 4,
                profile=profile,
                mac_from_adv=address,
            )
        )
    return devices


def main():
    parser = argparse.ArgumentParser(
        prog="tingon",
        description="TINGON IoT BLE Device Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tingon scan
  tingon status AA:BB:CC:DD:EE:FF --profile fjb
  tingon humidity AA:BB:CC:DD:EE:FF 50 --profile fjb2
  tingon temp AA:BB:CC:DD:EE:FF 42 --profile gs
  tingon play AA:BB:CC:DD:EE:FF on --profile m2 --mode 1
  tingon motor AA:BB:CC:DD:EE:FF 70 30 --profile m1
  tingon position AA:BB:CC:DD:EE:FF front --profile m2
  tingon custom-set AA:BB:CC:DD:EE:FF 32 1:10 2:20 --profile n2
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    p_scan = subparsers.add_parser("scan", help="Scan for TINGON devices")
    p_scan.add_argument("--name", default="", help="Filter by device name")
    p_scan.add_argument("--timeout", type=float, default=10.0, help="Scan timeout in seconds")

    p_status = subparsers.add_parser("status", help="Query device status")
    p_status.add_argument("address", help="Device BLE address")
    add_profile_arg(p_status)

    p_power = subparsers.add_parser("power", help="Set appliance power")
    p_power.add_argument("address", help="Device BLE address")
    p_power.add_argument("state", choices=["on", "off"], help="Power state")
    add_profile_arg(p_power)

    p_hum = subparsers.add_parser("humidity", help="Set target humidity")
    p_hum.add_argument("address", help="Device BLE address")
    p_hum.add_argument("percent", type=int, help="Target humidity percentage")
    add_profile_arg(p_hum)

    p_temp = subparsers.add_parser("temp", help="Set water temperature")
    p_temp.add_argument("address", help="Device BLE address")
    p_temp.add_argument("degrees", type=int, help="Target temperature in Celsius")
    add_profile_arg(p_temp)

    p_mode = subparsers.add_parser("mode", help="Set bathroom mode or intimate preset mode")
    p_mode.add_argument("address", help="Device BLE address")
    p_mode.add_argument("mode", help="Bathroom mode name or intimate mode number")
    add_profile_arg(p_mode)

    p_play = subparsers.add_parser("play", help="Start or stop intimate playback")
    p_play.add_argument("address", help="Device BLE address")
    p_play.add_argument("state", choices=["on", "off"], help="Playback state")
    p_play.add_argument("--mode", type=int, default=None, help="Mode to use when starting playback")
    add_profile_arg(p_play)

    p_motor = subparsers.add_parser("motor", help="Set intimate manual output")
    p_motor.add_argument("address", help="Device BLE address")
    p_motor.add_argument("motor1", type=int, help="Primary output 0-100")
    p_motor.add_argument("motor2", type=int, nargs="?", default=None, help="Secondary output 0-100")
    add_profile_arg(p_motor)

    p_position = subparsers.add_parser("position", help="Set M2 position selector")
    p_position.add_argument("address", help="Device BLE address")
    p_position.add_argument("position", choices=sorted(IntimateProtocol.POSITION_BYTES.keys()), help="Position selector")
    add_profile_arg(p_position)

    p_n2 = subparsers.add_parser("n2-mode", help="Set N2 mode family")
    p_n2.add_argument("address", help="Device BLE address")
    p_n2.add_argument("name", choices=list(IntimateProtocol.N2_MODE_LABELS.values()), help="N2 mode")
    add_profile_arg(p_n2)

    p_cget = subparsers.add_parser("custom-get", help="Read intimate custom slot")
    p_cget.add_argument("address", help="Device BLE address")
    p_cget.add_argument("slot", type=int, choices=[32, 33, 34], help="Custom slot ID")
    add_profile_arg(p_cget)

    p_cset = subparsers.add_parser("custom-set", help="Write intimate custom slot")
    p_cset.add_argument("address", help="Device BLE address")
    p_cset.add_argument("slot", type=int, choices=[32, 33, 34], help="Custom slot ID")
    p_cset.add_argument("items", nargs="+", help="Sequence of mode:sec pairs")
    add_profile_arg(p_cset)

    p_prov = subparsers.add_parser("provision", help="Provision WiFi credentials")
    p_prov.add_argument("address", help="Device BLE address")
    p_prov.add_argument("ssid", help="WiFi SSID")
    p_prov.add_argument("password", help="WiFi password")
    p_prov.add_argument("--url", default="", help="Config URL")
    add_profile_arg(p_prov)

    p_raw = subparsers.add_parser("raw", help="Send raw hex command")
    p_raw.add_argument("address", help="Device BLE address")
    p_raw.add_argument("hex", help="Raw hex command")
    add_profile_arg(p_raw)

    p_inter = subparsers.add_parser("interactive", help="Interactive control session")
    p_inter.add_argument("address", help="Device BLE address")
    add_profile_arg(p_inter)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    cmd_map = {
        "scan": cmd_scan,
        "status": cmd_status,
        "power": cmd_power,
        "humidity": cmd_humidity,
        "temp": cmd_temp,
        "mode": cmd_mode,
        "play": cmd_play,
        "motor": cmd_motor,
        "position": cmd_position,
        "n2-mode": cmd_n2_mode,
        "custom-get": cmd_custom_get,
        "custom-set": cmd_custom_set,
        "provision": cmd_provision,
        "raw": cmd_raw,
        "interactive": cmd_interactive,
    }

    asyncio.run(cmd_map[args.command](args))


if __name__ == "__main__":
    main()
