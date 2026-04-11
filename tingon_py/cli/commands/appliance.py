"""`tingon` appliance-family commands (power, humidity, temp, mode)."""

from __future__ import annotations

from ...appliances.specs import BATHROOM_MODE_NAME_TO_VALUE
from ...exceptions import TingonProtocolError
from ._common import add_profile_arg, connect_for_args


async def cmd_power(args) -> None:
    dev = await connect_for_args(args)
    try:
        on = args.state.lower() == "on"
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
