# tingon-py

Async Python library for TINGON BLE appliance and intimate devices, with a bundled CLI and optional local web UI built on top of the same core.

- Distribution: `tingon-py`
- Import package: `tingon_py`
- Requires: Python 3.10+ and `bleak`

## Install

```bash
pip install -e .           # library + CLI
pip install -e .[web]      # adds the FastAPI-based local web UI
```

The base install only pulls `bleak`. FastAPI and Uvicorn are optional and only needed for `tingon-web`.

## Quick start

```python
import asyncio

from bleak import BleakScanner

from tingon_py import DeviceProfile, TingonClient, scan


async def main() -> None:
    # 1. Discover nearby devices. Each result is a ScannedDevice with
    #    address, name, RSSI, and (when recognizable) an inferred profile.
    devices = await scan(timeout=5)
    for d in devices:
        print(d.address, d.name, d.profile)

    # 2. Resolve a BLEDevice for the target — the library does not own
    #    the adapter, callers pass in a ready-to-use BLEDevice.
    ble_device = await BleakScanner.find_device_by_address("AA:BB:CC:DD:EE:FF")
    if ble_device is None:
        raise SystemExit("device not found")

    # 3. Connect with an explicit profile and drive the device.
    client = TingonClient()
    await client.connect(ble_device, profile=DeviceProfile.M2)
    try:
        await client.intimate_play(True, mode=1)
        await client.intimate_set_output(70, 30)   # motor1, motor2
        await client.intimate_set_position("front")
    finally:
        await client.disconnect()


asyncio.run(main())
```

The same client also drives the (rarer) appliance profiles. Appliance
state is exposed as a cached snapshot that you refresh with `update()`:

```python
client = TingonClient()
await client.connect(ble_device, profile=DeviceProfile.FJB)
try:
    await client.update()                       # refresh cached state
    state = client.appliance_state              # ApplianceState or None
    if state is not None:
        print(state.as_dict())
    await client.set_power(True)
    await client.set_target_humidity(50)
finally:
    await client.disconnect()
```

## Public API

Everything re-exported from `tingon_py` is considered stable:

| Symbol | Purpose |
| --- | --- |
| `TingonClient` | Async facade for connecting, querying, and controlling a device. Picks the right controller (appliance vs intimate) based on the profile. |
| `TingonDevice` | Low-level orchestrator the client wraps. Accepts a Bleak `BLEDevice` plus `disconnected_callback` / `ble_device_callback`. Home Assistant integrations use it directly. |
| `scan` | Async BLE scan returning `ScannedDevice` objects. Accepts an injectable `scanner` for tests. |
| `parse_advertisement` | Pure function that turns `(name, manufacturer_data, rssi, address)` into a `ScannedDevice`. Home Assistant integrations call it from their own advertisement callback. |
| `ScannedDevice` | Dataclass with `address`, `name`, `rssi`, `device_type`, `profile`, and raw advertisement metadata. |
| `ApplianceState` | Frozen dataclass snapshot of appliance state. `TingonClient.appliance_state` returns the cached snapshot; call `as_dict()` to get a JSON-friendly view. |
| `IntimateStatus` | Dataclass mirroring the last-known intimate device state (push-only; updated from BLE notifications). |
| `DeviceProfile`, `DeviceType`, `ProtocolFamily` | Enums covering every supported device family and protocol. |
| `ProfileInfo`, `profile_info` | Metadata per profile (display name, capability flags, protocol family). Use `profile_info(DeviceProfile.M2)` to introspect. |
| `TingonError` and subclasses | `TingonConnectionError`, `TingonUnavailableError`, `TingonProtocolError`, `TingonUnsupportedCapability`, `TingonDependencyError`. Catch `TingonError` to handle anything the library raises; catch `TingonUnavailableError` specifically to distinguish "temporarily gone" from "fundamentally broken". |

## Using with Home Assistant

`tingon-py` is designed to drop into a Home Assistant custom component
without fighting the shared Bluetooth stack. The library never starts
its own `BleakScanner`, accepts a `BLEDevice` on `connect()`, and
exposes a zero-arg callback registry that fits the
`DataUpdateCoordinator` pattern.

Advertisement parsing is a pure function — feed it directly from the
HA advertisement callback:

```python
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from tingon_py import parse_advertisement, DeviceProfile


@callback
def _async_on_advertisement(info: BluetoothServiceInfoBleak) -> None:
    scanned = parse_advertisement(
        name=info.name,
        manufacturer_data=dict(info.manufacturer_data),
        rssi=info.rssi,
        address=info.address,
    )
    if scanned is None or scanned.profile is None:
        return
    # scanned.profile is a DeviceProfile enum the library understands.
```

Connecting uses HA's `async_ble_device_from_address` for both the
initial `BLEDevice` and for stale-device recovery via
`ble_device_callback`:

```python
from homeassistant.components.bluetooth import async_ble_device_from_address
from tingon_py import TingonDevice


device = TingonDevice()

# Stream state changes into the coordinator — consumers read
# device.appliance_state / device.intimate_status after being notified.
unregister = device.register_callback(coordinator.async_update_listeners)

await device.connect(
    ble_device,
    profile=scanned.profile,
    disconnected_callback=coordinator.async_set_unavailable,
    ble_device_callback=lambda: async_ble_device_from_address(
        hass, address, connectable=True
    ),
)
```

Your `DataUpdateCoordinator.update_method` then just calls
`device.update()` — for appliances that issues a fresh query and
populates `device.appliance_state`; intimate devices are push-only, so
`update()` is a no-op and state is already current from BLE
notifications. Catch `TingonUnavailableError` from `connect()` /
`update()` to surface availability cleanly through the coordinator.

---

Capability gating lets you write profile-agnostic code:

```python
from tingon_py import TingonClient, TingonUnsupportedCapability
from tingon_py.profiles import CAP_CUSTOM

client = TingonClient()
await client.connect(ble_device, profile=DeviceProfile.M2)

if client.has_capability(CAP_CUSTOM):
    await client.intimate_set_custom(32, [(1, 10), (2, 20)])
else:
    try:
        client.require_capability(CAP_CUSTOM)
    except TingonUnsupportedCapability as exc:
        print(exc)
```

Injecting a fake scanner for unit tests:

```python
from tingon_py import scan

devices = await scan(scanner=my_fake_scanner, timeout=0)
```

## Package layout

The package is organized by responsibility so each layer can be imported independently:

```
tingon_py/
  __init__.py        curated public API (re-exports only)
  client.py          TingonClient wrapper over TingonDevice
  device.py          TingonDevice orchestrator, dispatches by profile
  profiles.py        DeviceProfile, capability flags, profile metadata
  models.py          ScannedDevice, SpecDef dataclasses
  exceptions.py      TingonError and typed subclasses
  crypto.py          XOR encryption + CRC for WiFi provisioning
  ble/
    uuids.py         GATT UUID constants
    transport.py     BleakClient wrapper
    scan.py          device discovery
  appliances/        TLV protocol, specs, ApplianceController
  intimates/         intimate protocol, IntimateController, status
  mock/              MockTingonDevice and mock scan catalog
  cli/               argparse CLI (`tingon` entry point)
  webapp.py          `tingon-web` entry point (imports webapp_impl lazily)
  webapp_impl.py     FastAPI app + session manager (optional dep)
  web/               packaged static assets for the local UI
```

See [PROTOCOL.md](PROTOCOL.md) for the on-wire protocol reference.

## Supported devices

Intimate profiles (primary focus):

- `a1` — TINGON A1
- `n1` — TINGON N1
- `n2` — TINGON N2
- `m1` — TINGON M1
- `m2` — TINGON M2

Appliance profiles (limited userbase, included for completeness):

- `fjb` — XPOWER dehumidifier
- `fjb2` — XPOWER dehumidifier, second generation
- `gs` — Wanhe water heater
- `rj` — Wanhe water heater

## CLI

Installing the package registers a `tingon` console script on top of the library. Handy for quick manual checks without writing Python.

```bash
tingon scan
tingon scan --timeout 5

tingon status AA:BB:CC:DD:EE:FF --profile m2

# Intimate controls
tingon play       AA:BB:CC:DD:EE:FF on --profile m2 --mode 1
tingon motor      AA:BB:CC:DD:EE:FF 70 30 --profile m1
tingon position   AA:BB:CC:DD:EE:FF front --profile m2
tingon n2-mode    AA:BB:CC:DD:EE:FF vibration --profile n2
tingon custom-get AA:BB:CC:DD:EE:FF 32 --profile m2
tingon custom-set AA:BB:CC:DD:EE:FF 32 1:10 2:20 3:15 --profile n2

# Appliance controls
tingon power    AA:BB:CC:DD:EE:FF on  --profile fjb
tingon humidity AA:BB:CC:DD:EE:FF 50  --profile fjb2
tingon temp     AA:BB:CC:DD:EE:FF 42  --profile gs
tingon mode     AA:BB:CC:DD:EE:FF kitchen --profile rj

tingon provision AA:BB:CC:DD:EE:FF MyWifi password123 --profile fjb
```

Run `tingon --help` or `tingon <command> --help` for the full list.

## Web UI

The optional `tingon-web` console script launches a local FastAPI app that drives the library over HTTP.

```bash
pip install -e .[web]

tingon-web                                # bind 127.0.0.1:8765
tingon-web --mock                         # deterministic mock BLE backend
tingon-web --host 0.0.0.0 --port 8765     # expose on LAN

python -m tingon_py.webapp                # equivalent module form
```

Then open <http://127.0.0.1:8765>.

The UI currently covers:

- scan, connect, disconnect, live control, and status refresh
- intimate screens for `a1`, `n1`, `n2`, `m1`, `m2` including custom-slot editing
- appliance screens for `fjb`, `fjb2`, `gs`, `rj`
- mock BLE mode with deterministic test devices for every supported profile

## Notes

- Intimate devices use `ee01/ee02/ee04` with a command family built around `0A..` and `0B..` opcodes.
- Appliance devices reuse the same characteristics with a TLV/spec protocol plus `cc01/cc02/cc03` for status queries.
- BLE writes require the target device to be powered on and in range.

## Screenshots

Current local web UI examples:

![TINGON M2 desktop](screenshots/webui-m2-desktop.png)

![TINGON N1 desktop](screenshots/webui-n1-desktop.png)

![XPOWER FJB2 desktop](screenshots/webui-fjb2-desktop.png)

