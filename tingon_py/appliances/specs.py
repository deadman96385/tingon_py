"""Appliance spec tables and constants.

Defines the TLV spec IDs, query ID lists, and metadata used by the
appliance protocol and controller.
"""

from __future__ import annotations

from ..models import SpecDef
from ..profiles import DeviceType


# Dehumidifier spec IDs
DEHUMIDIFIER_SPECS: dict[int, SpecDef] = {
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
DEHUMIDIFIER_SIGNED_SPECS: set[int] = {10, 12, 14}

# Water heater spec IDs
WATER_HEATER_SPECS: dict[int, SpecDef] = {
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
WATER_HEATER_SIGNED_SPECS: set[int] = {11, 13}

# Combined spec lookup (union of both)
ALL_SPECS: dict[int, SpecDef] = {**DEHUMIDIFIER_SPECS, **WATER_HEATER_SPECS}

BATHROOM_MODES: dict[int, tuple[str, int | None]] = {
    1: ("normal", 50),
    2: ("kitchen", 42),
    4: ("eco", 40),
    5: ("season", None),
}

BATHROOM_MODE_NAME_TO_VALUE: dict[str, int] = {
    name: code for code, (name, _temp) in BATHROOM_MODES.items()
}


def bathroom_mode_options() -> list[dict[str, str]]:
    return [
        {"value": name, "label": name.replace("_", " ").title()}
        for name in BATHROOM_MODE_NAME_TO_VALUE
    ]


# Device-type groupings
DEHUMIDIFIER_TYPES: set[DeviceType] = {DeviceType.FJB, DeviceType.FJB_SECOND}
WATER_HEATER_TYPES: set[DeviceType] = {DeviceType.GS, DeviceType.RJ}


# Product constants (informational — preserved for compatibility)
PRODUCT_KEYS: dict[DeviceType, str] = {
    DeviceType.FJB: "0003dbf0bd39ff10",
    DeviceType.GS: "00023f7390c6c770",
    DeviceType.FJB_SECOND: "000521df79128cd1",
}

PRODUCT_IDS: dict[DeviceType, str] = {
    DeviceType.FJB: "0003",
    DeviceType.GS: "0002",
    DeviceType.RJ: "0004",
    DeviceType.FJB_SECOND: "0005",
}
