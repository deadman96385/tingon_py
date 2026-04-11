"""`tingon provision`, `tingon raw`, and `tingon interactive` commands."""

from __future__ import annotations

import json

from ...appliances.specs import BATHROOM_MODE_NAME_TO_VALUE
from ...profiles import (
    CAP_CRUISE_TEMP,
    CAP_CUSTOM,
    CAP_CUSTOM_RANGE,
    CAP_DIANDONG,
    CAP_ECO_CRUISE,
    CAP_HUMIDITY,
    CAP_N2_MODE,
    CAP_POSITION,
    CAP_SINGLE_CRUISE,
    CAP_TIMER,
    CAP_WATER_PRESSURIZATION,
    CAP_WATER_TEMP,
    CAP_ZERO_COLD_WATER,
    CAP_ZERO_COLD_WATER_MODE,
)
from ..formatters import format_status
from ._common import add_profile_arg, connect_for_args
from .appliance import ZERO_COLD_WATER_MODE_VALUES, _parse_timer_entry


async def cmd_provision(args) -> None:
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


async def cmd_raw(args) -> None:
    dev = await connect_for_args(args)
    try:
        await dev.send_raw_hex(args.hex)
        print("Sent raw command")
    finally:
        await dev.disconnect()


async def cmd_interactive(args) -> None:
    dev = await connect_for_args(args)
    print("\nInteractive mode. Commands:")
    print("  status")
    if dev.is_appliance:
        print("  power on/off")
        if dev.has_capability(CAP_HUMIDITY):
            print("  humidity <n>")
            print("  drainage on/off")
            print("  dehum on/off")
        if dev.has_capability(CAP_TIMER):
            print("  timer <on|off:hours[:disabled]> ... | timer clear")
        if dev.has_capability(CAP_WATER_TEMP):
            print("  temp <n>")
            print("  mode normal|kitchen|eco|season")
        if dev.has_capability(CAP_CRUISE_TEMP):
            print("  cruise_temp <n>")
        if dev.has_capability(CAP_ZERO_COLD_WATER_MODE):
            print("  zcw_mode off|on|enhanced")
        if dev.has_capability(CAP_ECO_CRUISE):
            print("  eco_cruise on/off")
        if dev.has_capability(CAP_WATER_PRESSURIZATION):
            print("  pressurize on/off")
        if dev.has_capability(CAP_SINGLE_CRUISE):
            print("  single_cruise on/off")
        if dev.has_capability(CAP_DIANDONG):
            print("  jogging on/off")
        if dev.has_capability(CAP_ZERO_COLD_WATER):
            print("  zcw on/off")
    else:
        print("  play on/off [mode]")
        print("  mode <n>")
        print("  motor <n> [motor2]")
        if dev.has_capability(CAP_POSITION):
            print("  position front|middle|back|front_middle|middle_back|all")
        if dev.has_capability(CAP_N2_MODE):
            print("  n2mode vibration|electric_shock|vibration_and_electric_shock  # local selector")
        if dev.has_capability(CAP_CUSTOM):
            print("  custom_get <32|33|34>")
            print("  custom_set <slot> <mode:sec> [mode:sec] ...")
            print("  custom_use <32|33|34>")
        if dev.has_capability(CAP_CUSTOM_RANGE):
            print("  range <start> <end>")
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
                elif dev.is_appliance and cmd == "cruise_temp" and len(parts) > 1:
                    print(await dev.set_cruise_insulation_temp(int(parts[1])))
                elif dev.is_appliance and cmd == "zcw_mode" and len(parts) > 1:
                    mode_val = ZERO_COLD_WATER_MODE_VALUES.get(parts[1].lower())
                    if mode_val is None:
                        print("Unknown mode. Use: off, on, enhanced")
                    else:
                        print(await dev.set_zero_cold_water_mode(mode_val))
                elif dev.is_appliance and cmd == "eco_cruise" and len(parts) > 1:
                    print(await dev.set_eco_cruise(parts[1].lower() == "on"))
                elif dev.is_appliance and cmd == "pressurize" and len(parts) > 1:
                    print(await dev.set_water_pressurization(parts[1].lower() == "on"))
                elif dev.is_appliance and cmd == "single_cruise" and len(parts) > 1:
                    print(await dev.set_single_cruise(parts[1].lower() == "on"))
                elif dev.is_appliance and cmd == "jogging" and len(parts) > 1:
                    print(await dev.set_diandong(parts[1].lower() == "on"))
                elif dev.is_appliance and cmd == "zcw" and len(parts) > 1:
                    print(await dev.set_zero_cold_water(parts[1].lower() == "on"))
                elif dev.is_appliance and cmd == "timer":
                    if len(parts) > 1 and parts[1].lower() == "clear":
                        print(await dev.set_timer([]))
                    else:
                        entries = [_parse_timer_entry(raw) for raw in parts[1:]]
                        print(await dev.set_timer(entries))
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
                elif dev.is_intimate and cmd == "custom_use" and len(parts) > 1:
                    await dev.intimate_use_custom(int(parts[1]))
                    print(f"Activated custom slot {parts[1]}")
                elif dev.is_intimate and cmd == "range" and len(parts) > 2:
                    await dev.intimate_set_custom_range(int(parts[1]), int(parts[2]))
                    print(f"Range set to {parts[1]}-{parts[2]}")
                else:
                    print(f"Unknown command: {line}")
            except Exception as exc:
                print(f"Error: {exc}")
    finally:
        await dev.disconnect()


def register(subparsers) -> None:
    p_prov = subparsers.add_parser("provision", help="Provision WiFi credentials")
    p_prov.add_argument("address", help="Device BLE address")
    p_prov.add_argument("ssid", help="WiFi SSID")
    p_prov.add_argument("password", help="WiFi password")
    p_prov.add_argument("--url", default="", help="Config URL")
    add_profile_arg(p_prov)
    p_prov.set_defaults(func=cmd_provision)

    p_raw = subparsers.add_parser("raw", help="Send raw hex command")
    p_raw.add_argument("address", help="Device BLE address")
    p_raw.add_argument("hex", help="Raw hex command")
    add_profile_arg(p_raw)
    p_raw.set_defaults(func=cmd_raw)

    p_inter = subparsers.add_parser("interactive", help="Interactive control session")
    p_inter.add_argument("address", help="Device BLE address")
    add_profile_arg(p_inter)
    p_inter.set_defaults(func=cmd_interactive)
