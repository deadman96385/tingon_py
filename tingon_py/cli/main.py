"""Entry point for the ``tingon`` command-line interface."""

from __future__ import annotations

import argparse
import asyncio

from .commands import appliance, intimate, provision, scan, status


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tingon",
        description="TINGON IoT BLE Device Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tingon scan
  tingon status AA:BB:CC:DD:EE:FF --profile fjb
  tingon humidity AA:BB:CC:DD:EE:FF 50 --profile fjb2
  tingon drainage AA:BB:CC:DD:EE:FF on --profile fjb
  tingon timer AA:BB:CC:DD:EE:FF on:4 off:12 --profile fjb2
  tingon temp AA:BB:CC:DD:EE:FF 42 --profile gs
  tingon mode AA:BB:CC:DD:EE:FF eco --profile gs
  tingon cruise-temp AA:BB:CC:DD:EE:FF 45 --profile rj
  tingon zcw-mode AA:BB:CC:DD:EE:FF enhanced --profile gs
  tingon eco-cruise AA:BB:CC:DD:EE:FF on --profile gs
  tingon pressurize AA:BB:CC:DD:EE:FF on --profile rj
  tingon single-cruise AA:BB:CC:DD:EE:FF on --profile gs
  tingon jogging AA:BB:CC:DD:EE:FF on --profile gs
  tingon zcw AA:BB:CC:DD:EE:FF on --profile gs
  tingon play AA:BB:CC:DD:EE:FF on --profile m2 --mode 1
  tingon motor AA:BB:CC:DD:EE:FF 70 30 --profile m1
  tingon position AA:BB:CC:DD:EE:FF front --profile m2
  tingon range AA:BB:CC:DD:EE:FF 10 80 --profile m2
  tingon custom-set AA:BB:CC:DD:EE:FF 32 1:10 2:20 --profile n2
  tingon custom-use AA:BB:CC:DD:EE:FF 32 --profile n2
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    scan.register(subparsers)
    status.register(subparsers)
    appliance.register(subparsers)
    intimate.register(subparsers)
    provision.register(subparsers)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
