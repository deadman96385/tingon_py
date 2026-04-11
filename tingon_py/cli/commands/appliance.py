"""`tingon` appliance-family commands (power, humidity, temp, mode, etc.)."""

from __future__ import annotations

from ...appliances.specs import BATHROOM_MODE_NAME_TO_VALUE
from ...exceptions import TingonProtocolError
from ._common import add_profile_arg, connect_for_args


ZERO_COLD_WATER_MODE_VALUES = {"off": 0, "on": 1, "enhanced": 3}


def _on_off(state: str) -> bool:
    return state.lower() == "on"


async def cmd_power(args) -> None:
    dev = await connect_for_args(args)
    try:
        on = _on_off(args.state)
        result = await dev.set_power(on)
        print(f"Power {'ON' if on else 'OFF'}: {result}")
    finally:
        await dev.disconnect()


async def cmd_humidity(args) -> None:
    dev = await connect_for_args(args)
    try:
        result = await dev.set_target_humidity(args.percent)
        print(f"Target humidity set to {args.percent}%: {result}")
    finally:
        await dev.disconnect()


async def cmd_drainage(args) -> None:
    dev = await connect_for_args(args)
    try:
        on = _on_off(args.state)
        result = await dev.set_drainage(on)
        print(f"Drainage {'ON' if on else 'OFF'}: {result}")
    finally:
        await dev.disconnect()


async def cmd_dehum(args) -> None:
    dev = await connect_for_args(args)
    try:
        on = _on_off(args.state)
        result = await dev.set_dehumidification(on)
        print(f"Dehumidification {'ON' if on else 'OFF'}: {result}")
    finally:
        await dev.disconnect()


async def cmd_temp(args) -> None:
    dev = await connect_for_args(args)
    try:
        result = await dev.set_water_temperature(args.degrees)
        print(f"Water temperature set to {args.degrees}C: {result}")
    finally:
        await dev.disconnect()


async def cmd_mode(args) -> None:
    dev = await connect_for_args(args)
    try:
        if dev.is_appliance:
            mode_val = BATHROOM_MODE_NAME_TO_VALUE.get(args.mode.lower())
            if mode_val is None:
                raise TingonProtocolError("Unknown bathroom mode. Use: normal, kitchen, eco, season")
            result = await dev.set_bathroom_mode(mode_val)
            print(f"Bathroom mode set to {args.mode}: {result}")
        else:
            await dev.intimate_set_mode(int(args.mode))
            print(f"Preset mode set to {args.mode}")
    finally:
        await dev.disconnect()


async def cmd_cruise_temp(args) -> None:
    dev = await connect_for_args(args)
    try:
        result = await dev.set_cruise_insulation_temp(args.degrees)
        print(f"Cruise insulation temperature set to {args.degrees}C: {result}")
    finally:
        await dev.disconnect()


async def cmd_zcw_mode(args) -> None:
    dev = await connect_for_args(args)
    try:
        mode_val = ZERO_COLD_WATER_MODE_VALUES.get(args.mode.lower())
        if mode_val is None:
            raise TingonProtocolError("Unknown mode. Use: off, on, enhanced")
        result = await dev.set_zero_cold_water_mode(mode_val)
        print(f"Zero cold water mode set to {args.mode}: {result}")
    finally:
        await dev.disconnect()


async def cmd_eco_cruise(args) -> None:
    dev = await connect_for_args(args)
    try:
        on = _on_off(args.state)
        result = await dev.set_eco_cruise(on)
        print(f"Eco cruise {'ON' if on else 'OFF'}: {result}")
    finally:
        await dev.disconnect()


async def cmd_pressurize(args) -> None:
    dev = await connect_for_args(args)
    try:
        on = _on_off(args.state)
        result = await dev.set_water_pressurization(on)
        print(f"Water pressurization {'ON' if on else 'OFF'}: {result}")
    finally:
        await dev.disconnect()


async def cmd_single_cruise(args) -> None:
    dev = await connect_for_args(args)
    try:
        on = _on_off(args.state)
        result = await dev.set_single_cruise(on)
        print(f"Single cruise {'ON' if on else 'OFF'}: {result}")
    finally:
        await dev.disconnect()


async def cmd_jogging(args) -> None:
    dev = await connect_for_args(args)
    try:
        on = _on_off(args.state)
        result = await dev.set_diandong(on)
        print(f"Jogging+ {'ON' if on else 'OFF'}: {result}")
    finally:
        await dev.disconnect()


async def cmd_zcw(args) -> None:
    dev = await connect_for_args(args)
    try:
        on = _on_off(args.state)
        result = await dev.set_zero_cold_water(on)
        print(f"Zero cold water {'ON' if on else 'OFF'}: {result}")
    finally:
        await dev.disconnect()


def _parse_timer_entry(raw: str) -> dict:
    """Parse ``on:4`` / ``off:12`` / ``on:4:disabled`` into a timer entry dict."""
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise TingonProtocolError(
            f"Invalid timer entry '{raw}'. Expected 'on:<hours>' or 'off:<hours>[:disabled]'"
        )
    action = parts[0].lower()
    if action not in {"on", "off"}:
        raise TingonProtocolError(f"Timer action must be 'on' or 'off', got '{parts[0]}'")
    try:
        hours = int(parts[1])
    except ValueError as exc:
        raise TingonProtocolError(f"Timer hours must be an integer, got '{parts[1]}'") from exc
    if hours < 1 or hours > 23:
        raise TingonProtocolError("Timer hours must be between 1 and 23")
    status = 1
    if len(parts) == 3:
        flag = parts[2].lower()
        if flag == "disabled":
            status = 0
        elif flag != "enabled":
            raise TingonProtocolError(f"Timer flag must be 'enabled' or 'disabled', got '{parts[2]}'")
    return {"switch": 1 if action == "on" else 0, "status": status, "hours": hours}


async def cmd_timer(args) -> None:
    dev = await connect_for_args(args)
    try:
        if args.clear:
            entries: list[dict] = []
        else:
            entries = [_parse_timer_entry(raw) for raw in args.entries]
        result = await dev.set_timer(entries)
        if not entries:
            print(f"Cleared all timers: {result}")
        else:
            summary = ", ".join(
                f"{'On' if e['switch'] else 'Off'} in {e['hours']}h"
                + ("" if e["status"] else " (disabled)")
                for e in entries
            )
            print(f"Set {len(entries)} timer(s): {summary}: {result}")
    finally:
        await dev.disconnect()


def register(subparsers) -> None:
    p_power = subparsers.add_parser("power", help="Set appliance power")
    p_power.add_argument("address", help="Device BLE address")
    p_power.add_argument("state", choices=["on", "off"], help="Power state")
    add_profile_arg(p_power)
    p_power.set_defaults(func=cmd_power)

    p_hum = subparsers.add_parser("humidity", help="Set target humidity")
    p_hum.add_argument("address", help="Device BLE address")
    p_hum.add_argument("percent", type=int, help="Target humidity percentage")
    add_profile_arg(p_hum)
    p_hum.set_defaults(func=cmd_humidity)

    p_drain = subparsers.add_parser("drainage", help="Toggle dehumidifier drainage mode")
    p_drain.add_argument("address", help="Device BLE address")
    p_drain.add_argument("state", choices=["on", "off"], help="Drainage state")
    add_profile_arg(p_drain)
    p_drain.set_defaults(func=cmd_drainage)

    p_dehum = subparsers.add_parser("dehum", help="Toggle active dehumidification")
    p_dehum.add_argument("address", help="Device BLE address")
    p_dehum.add_argument("state", choices=["on", "off"], help="Dehumidification state")
    add_profile_arg(p_dehum)
    p_dehum.set_defaults(func=cmd_dehum)

    p_temp = subparsers.add_parser("temp", help="Set water temperature")
    p_temp.add_argument("address", help="Device BLE address")
    p_temp.add_argument("degrees", type=int, help="Target temperature in Celsius")
    add_profile_arg(p_temp)
    p_temp.set_defaults(func=cmd_temp)

    p_mode = subparsers.add_parser("mode", help="Set bathroom mode or intimate preset mode")
    p_mode.add_argument("address", help="Device BLE address")
    p_mode.add_argument("mode", help="Bathroom mode name or intimate mode number")
    add_profile_arg(p_mode)
    p_mode.set_defaults(func=cmd_mode)

    p_cruise = subparsers.add_parser("cruise-temp", help="Set cruise insulation temperature")
    p_cruise.add_argument("address", help="Device BLE address")
    p_cruise.add_argument("degrees", type=int, help="Cruise insulation temperature in Celsius")
    add_profile_arg(p_cruise)
    p_cruise.set_defaults(func=cmd_cruise_temp)

    p_zcwm = subparsers.add_parser("zcw-mode", help="Set zero cold water mode")
    p_zcwm.add_argument("address", help="Device BLE address")
    p_zcwm.add_argument("mode", choices=["off", "on", "enhanced"], help="Zero cold water mode")
    add_profile_arg(p_zcwm)
    p_zcwm.set_defaults(func=cmd_zcw_mode)

    p_eco = subparsers.add_parser("eco-cruise", help="Toggle eco cruise insulation")
    p_eco.add_argument("address", help="Device BLE address")
    p_eco.add_argument("state", choices=["on", "off"], help="Eco cruise state")
    add_profile_arg(p_eco)
    p_eco.set_defaults(func=cmd_eco_cruise)

    p_press = subparsers.add_parser("pressurize", help="Toggle water pressurization")
    p_press.add_argument("address", help="Device BLE address")
    p_press.add_argument("state", choices=["on", "off"], help="Water pressurization state")
    add_profile_arg(p_press)
    p_press.set_defaults(func=cmd_pressurize)

    p_sc = subparsers.add_parser("single-cruise", help="Toggle single cruise insulation cycle")
    p_sc.add_argument("address", help="Device BLE address")
    p_sc.add_argument("state", choices=["on", "off"], help="Single cruise state")
    add_profile_arg(p_sc)
    p_sc.set_defaults(func=cmd_single_cruise)

    p_jog = subparsers.add_parser("jogging", help="Toggle Jogging+ (diandong) motorized assist")
    p_jog.add_argument("address", help="Device BLE address")
    p_jog.add_argument("state", choices=["on", "off"], help="Jogging+ state")
    add_profile_arg(p_jog)
    p_jog.set_defaults(func=cmd_jogging)

    p_zcw = subparsers.add_parser("zcw", help="Trigger one-shot zero cold water circulation")
    p_zcw.add_argument("address", help="Device BLE address")
    p_zcw.add_argument("state", choices=["on", "off"], help="Zero cold water state")
    add_profile_arg(p_zcw)
    p_zcw.set_defaults(func=cmd_zcw)

    p_timer = subparsers.add_parser(
        "timer",
        help="Schedule dehumidifier timers",
        description="Entries use 'on:<hours>' or 'off:<hours>[:disabled]' (hours 1-23).",
    )
    p_timer.add_argument("address", help="Device BLE address")
    p_timer.add_argument("entries", nargs="*", help="Timer entries like on:4 off:12:disabled")
    p_timer.add_argument("--clear", action="store_true", help="Clear all timer entries")
    add_profile_arg(p_timer)
    p_timer.set_defaults(func=cmd_timer)
