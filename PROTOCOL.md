# TINGON BLE Protocol Reference

Reference for the BLE protocols used by TINGON devices in app version `1.1.38`.

## Table of Contents

- [BLE Services](#ble-services)
- [Intimate Profiles](#intimate-profiles)
- [Intimate Commands](#intimate-commands)
- [Appliance Profiles](#appliance-profiles)
- [Appliance Command Format](#appliance-command-format)
- [Appliance Queries](#appliance-queries)
- [Appliance Response Parsing](#appliance-response-parsing)
- [Provisioning](#provisioning)
- [Advertisement Parsing](#advertisement-parsing)
- [Timing and Limits](#timing-and-limits)
- [Reference Sources](#reference-sources)

---

## BLE Services

All UUIDs use base `0000XXXX-0000-1000-8000-00805f9b34fb`.

| Purpose | Service | Write | Notify |
|---------|---------|-------|--------|
| command/control | `ee01` | `ee02` | `ee04` |
| appliance query/status | `cc01` | `cc02` | `cc03` |
| Wi-Fi provisioning | `ff01` | `ff03` | `ff02` |

CCCD: `2902`

---

## Intimate Profiles

The intimate devices use `ee01/ee02/ee04` only. They do **not** use the appliance TLV/spec format.

### Profile Map

| Local Type | Marketing Name | Profile ID | Main Controls |
|------------|----------------|------------|---------------|
| `0` | `TINGON M1` | `m1` | dual output, preset modes, custom slots |
| `1` | `TINGON A1` | `a1` | single output, preset modes, custom slots |
| `2` | `TINGON N1` | `n1` | single output, preset modes, custom slots |
| `3` | `TINGON M2` | `m2` | speed, position, custom slots, custom range |
| `4` | `TINGON N2` | `n2` | vibration, electric shock, preset modes, custom slots |

### Discovery and Local Type Assignment

Observed app behavior:

- intimate scan uses the device-name filter `XiYu`
- scan results are stored by `mac`
- scan results are merged with the cloud device list by `mac`
- the merged record's local `type` drives naming, hero image selection, and detail-screen routing

Confirmed local intimate types:

- `0` -> M1
- `1` -> A1
- `2` -> N1
- `3` -> M2
- `4` -> N2

Confidence notes:

- confirmed: local `type` values `0..4` exist and drive the intimate UI
- not confirmed: a dedicated intimate advertisement byte field equivalent to appliance manufacturer-data byte `10`
- current evidence suggests intimate product identity is resolved at the app/product layer, not solely by the native advertisement parser

### Default Names Used By The App

When no saved nickname is present, the original main intimate device list uses these defaults:

- `0` -> `TINGON M1`
- `1` -> `TINGON A1`
- `2` -> `TINGON N1`
- fallback -> `TINGON M2`

The detail views still have distinct support for `N2`. The fallback naming logic appears older than the final set of intimate profiles.

### Capabilities

| Profile | Mode Count | Manual Outputs | Extra Controls | Custom Step Limit |
|---------|------------|----------------|----------------|-------------------|
| `a1` | 12 | 1 | none | 4 |
| `n1` | 12 | 1 | none | 4 |
| `n2` | 12 | 2 | N2 mode family | 6 |
| `m1` | 10 | 2 | quantized dual output | 4 |
| `m2` | 12 | 1 | position selector, custom range | 6 |

### N2 Notes

- profile `n2` uses the same base intimate packet family as `a1`, `n1`, `m1`, and `m2`
- output 1 is presented as `vibration`
- output 2 is presented as `electric_shock`
- the app exposes three N2 selector states:
  - `vibration`
  - `electric_shock`
  - `vibration_and_electric_shock`
- dedicated selector assets exist for those three states in the React Native bundle
- no N2-exclusive BLE opcode has been confirmed from the React Native layer

### Playback Behavior

The original app also has a local playback scheduler:

- `loop`
- `random`
- `sequence`

This is app behavior layered on top of preset-mode writes. It is not a separate BLE packet type.

### Intimate Scope

- transport: BLE
- notify path: `ee04`
- custom slots: `32`, `33`, `34`
- cloud mirror keys used by app: `7`, `8`, `9`
- no Wi-Fi provisioning flow identified for intimate devices

---

## Intimate Commands

### Play / Preset / Custom Slot Select

```
0A01 00    stop
0A01 mm    play preset/custom mode mm
```

Examples:

```
0A0100    stop
0A0101    preset 1
0A0120    custom slot 32
0A0121    custom slot 33
0A0122    custom slot 34
```

### Manual Output

Single output:

```
0A02 40 vv
```

Dual output:

```
0A02 40 vv 41 ww
```

Fields:

- `40`: output 1
- `41`: output 2
- `vv`, `ww`: 1-byte output values

N2 mapping:

- `40` -> vibration
- `41` -> electric shock

### Output Scaling

`a1`, `n1`, `n2`, `m2` use `0..10` style values derived from the UI percentage.

`m1` uses quantized output:

| UI Value | Encoded |
|----------|---------|
| `0` | `0` |
| `1-17` | `5` |
| `18-35` | `6` |
| `36-51` | `7` |
| `52-68` | `8` |
| `69-86` | `9` |
| `87-100` | `10` |

### M2 Position + Speed

```
0A02 02 pp ss
```

| Position | Byte |
|----------|------|
| `front` | `60` |
| `middle` | `61` |
| `back` | `62` |
| `front_middle` | `63` |
| `middle_back` | `64` |
| `all` | `65` |

Fields:

- `pp`: position byte
- `ss`: speed byte

### M2 Custom Range

```
0A06 0C 50 aa 51 bb 52 cc 53 dd 54 ee 55 ff
```

Meaning:

- range points are clamped to `0..92`
- if `start > end`, swap them
- divide the selected span into 3 equal segments
- write segment boundaries as:
  - `50 start1`
  - `51 end1`
  - `52 start2`
  - `53 end2`
  - `54 start3`
  - `55 end3`

Example:

```
0A060C5000511E521E533C543C555C
```

### Custom Slot Query

```
0B02 20   query slot 32
0B02 21   query slot 33
0B02 22   query slot 34
```

### Custom Slot Write

```
0A04 ss ll [mode1 sec1 mode2 sec2 ...]
```

Fields:

- `ss`
  - `20` = slot `32`
  - `21` = slot `33`
  - `22` = slot `34`
- `ll`: payload length in bytes
- payload: repeated `(mode, seconds)` pairs

Example:

```
0A042004010A0214
```

Meaning:

- slot `32`
- payload length `04`
- step 1: mode `1`, `10` seconds
- step 2: mode `2`, `20` seconds

### Custom Slot Limits

Allowed durations:

- `10`
- `20`
- `30`
- `40`
- `50`
- `60`

Per-profile step limits:

- `a1`, `n1`, `m1`: up to 4 steps
- `n2`, `m2`: up to 6 steps

### Notifications

Observed `ee04` frames:

```
02 40 xx
02 41 yy
02 40 xx 41 yy
02 mm
```

Interpretation:

- `02 40 xx`: output 1 report
- `02 41 yy`: output 2 report
- `02 40 xx 41 yy`: combined dual-output report
- `02 mm`: current mode report when second byte is not `40` or `41`

### N2 Mode Family

App-level N2 modes:

- `vibration`
- `electric_shock`
- `vibration_and_electric_shock`

Observed behavior:

- the selector is rendered with dedicated N2-only assets in the React Native bundle
- the main BLE writes for N2 still use the shared intimate commands:
  - `0A01` for preset/custom playback
  - `0A02 40 vv 41 ww` for manual dual-output control
  - `0A04` / `0B02` for custom slots
- no separate N2 selector packet has been identified from the React Native control code

Current interpretation:

- the N2 selector changes the app's control mode and presentation
- the underlying device control still appears to be the standard dual-channel intimate protocol

---

## Appliance Profiles

Appliance products use the TLV/spec protocol over `ee01/ee02/ee04`, plus JSON queries over `cc01/cc02/cc03`.

### Profile Map

| Type | Name | Profile ID | PID | Product Key | Category |
|------|------|------------|-----|-------------|----------|
| `0` | FJB | `fjb` | `0003` | `0003dbf0bd39ff10` | dehumidifier |
| `1` | GS | `gs` | `0002` | `00023f7390c6c770` | water heater |
| `2` | RJ | `rj` | `0004` | not found in bundle | water heater |
| `3` | FJB2 | `fjb2` | `0005` | `000521df79128cd1` | dehumidifier |

Type is parsed from advertisement manufacturer data byte offset `10`.

### Dehumidifier Specs

| ID | Name | Type | Notes | R/W |
|----|------|------|-------|-----|
| `1` | `power` | bool | power on/off | W |
| `2` | `timer` | raw | timer payload | W |
| `3` | `drainage` | bool | drainage mode | W |
| `4` | `dehumidification` | bool | continuous dehumidify | W |
| `5` | `target_hum` | int | target humidity | W |
| `6` | `work_time` | int32 | current run time | R |
| `7` | `total_work_time` | int32 | lifetime run time | R |
| `8` | `compressor_status` | status | compressor state | R |
| `10` | `air_intake_temp` | signed int | intake temperature | R |
| `11` | `air_intake_hum` | int | intake humidity | R |
| `12` | `air_outlet_temp` | signed int | outlet temperature | R |
| `13` | `air_outlet_hum` | int | outlet humidity | R |
| `14` | `eva_temp` | signed int | evaporator temperature | R |
| `15` | `wind_speed` | int | fan speed | R |
| `16` | `error` | error | fault code | R |
| `17` | `defrost` | bool | defrost active | R |
| `18` | `timer_remind_time` | raw | timer remain payload | R |

Signed spec IDs: `10`, `12`, `14`

### Water Heater Specs

| ID | Name | Type | Notes | R/W |
|----|------|------|-------|-----|
| `1` | `power` | bool | power on/off | W |
| `2` | `bathroom_mode` | raw | operating mode | W |
| `7` | `setting_water_temp` | int | target water temp | W |
| `11` | `inlet_water_temp` | signed int | inlet temperature | R |
| `13` | `outlet_water_temp` | signed int | outlet temperature | R |
| `17` | `wind_status` | bool | fan/blower state | R |
| `27` | `discharge` | int | discharge/water flow value | R |
| `102` | `water_status` | bool | water flow detected | R |
| `103` | `fire_status` | bool | burner active | R |
| `104` | `equipment_failure` | error | fault code | R |
| `105` | `cruise_insulation_temp` | int | keep-warm temp | W |
| `106` | `zero_cold_water_mode` | int | `0/1/3` | W |
| `107` | `eco_cruise` | bool | eco cruise | W |
| `108` | `water_pressurization` | bool | pressurization | W |
| `109` | `single_cruise` | bool | single cruise | W |
| `110` | `diandong` | bool | jog/motorized mode | W |
| `111` | `zero_cold_water` | bool | zero-cold-water toggle | W |

Signed spec IDs: `11`, `13`

Bathroom modes:

| Mode | Name | Default Temp |
|------|------|--------------|
| `1` | `normal` | `50` |
| `2` | `kitchen` | `42` |
| `4` | `eco` | `40` |
| `5` | `season` | variable |

---

## Appliance Command Format

### Single Spec Write

```
01 + spec_id(4 hex) + type(2 hex) + length(4 hex) + value
```

### Multi Spec Write

```
count(2 hex) + repeated[ spec_id + type + length + value ]
```

### Type Rules

| Spec IDs | Type | Length | Meaning |
|----------|------|--------|---------|
| `1,3,4,17,102-103,107-111` | `01` | `0001` | bool |
| `5,10-15,27,105-106` | `02` | `0001` | int |
| `6,7` | `02` | `0004` | int32 |
| `8,9` | `04` | `0001` | status |
| `16,104` | `05` | `0001` | error |
| `2,18` | `00` | variable | raw hex |

### Examples

Power on:

```
01000101000101
```

Set target humidity to `50`:

```
01000502000132
```

Write behavior:

1. hex string -> bytes
2. write to `ee02` with response
3. keep ~250 ms between writes
4. parse reply from `ee04`

---

## Appliance Queries

Queries are JSON written to `cc02`.

### Dehumidifier Query

```json
{
  "time": 1712600000000,
  "data": [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18]
}
```

### Water Heater Query

```json
{
  "time": 1712600000000,
  "data": [1, 2, 7, 11, 13, 17, 27, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111]
}
```

Write behavior:

1. build JSON with millisecond timestamp
2. UTF-8 encode
3. write to `cc02`
4. parse reply from `cc03`

---

## Appliance Response Parsing

Response format:

```
header(2 hex) + repeated[
  spec_id(4)
  type(2)
  length(4)
  data(length * 2)
]
```

Parsing rules:

1. skip first byte
2. read `spec_id`, `type`, `length`
3. read `length` bytes of data
4. raw specs (`2`, `18`) stay as hex strings
5. all other specs parse as integers
6. apply signed conversion to signed temperature IDs

Signed conversion:

```python
def signed_value(raw, bits=16):
    if raw >= (1 << (bits - 1)):
        raw -= (1 << bits)
    return raw
```

Ignore junk notify payload:

```
000102030405060708090A0B0C0D0E
```

---

## Provisioning

Provisioning applies to the appliance side.

### BLE Provisioning

Transport:

- service `ff01`
- write `ff03`
- notify `ff02`

Payload:

```json
{
  "CID": 30005,
  "URL": "<cloud_config_url>",
  "PL": {
    "SSID": "<wifi_network_name>",
    "Password": "<wifi_password>"
  }
}
```

Flow:

1. serialize JSON
2. XOR-encrypt using device key
3. chunk BLE writes to `ff03`
4. collect reply from `ff02`
5. decrypt
6. parse JSON

### AP / UDP Provisioning

Flow:

1. connect to device hotspot
2. derive Wi-Fi key from SSID chars `[len-4:len-2]`
3. build same JSON payload
4. XOR-encrypt
5. send UDP to `10.10.100.254:9091`
6. receive response
7. decrypt and parse

### Provisioning Response

```json
{
  "CID": 30005,
  "RC": 0,
  "MAC": "AA:BB:CC:DD:EE:FF",
  "MID": "device_module_id",
  "FVER": "1.0.0",
  "PK": "product_key"
}
```

Notes:

- `RC = 0`: success
- `MID` falls back to `MAC` if empty

### XOR Encryption

Input:

- plaintext string
- device key: 2-char hex, for example `"41"`

Encrypt:

1. UTF-8 encode plaintext
2. generate random byte `R`
3. `start_index = int(device_key, 16) XOR R`
4. XOR each byte with `KEY_DICTIONARY[start_index]`, wrapping at 256
5. output `hex(R)` + encrypted hex

Decrypt:

1. read first byte as `R`
2. `start_index = int(device_key, 16) XOR R`
3. XOR ciphertext bytes with `KEY_DICTIONARY[start_index]`, wrapping at 256
4. decode UTF-8

Device key sources:

- BLE advertisement manufacturer data: hex slice `[len-8:len-6]`
- Wi-Fi SSID: chars `[len-4:len-2]`

### BLE Chunking

Chunk format:

```
[packet_id][sequence][up to 18 bytes payload]
```

Rules:

- same `packet_id` for all chunks in one message
- `sequence` starts at `1`
- if last chunk is exactly 18 bytes, send a 2-byte terminator:
  - `[packet_id][last_sequence + 1]`

---

## Advertisement Parsing

Advertisement uses normal AD structures.

Important manufacturer data offsets:

| Offset | Length | Meaning |
|--------|--------|---------|
| `10` | `1` | device type |
| `11` | `1` | sub-version |
| `13` | `6` | MAC address bytes |

Special case:

- if `device_type == 0` and `sub_version == 2`, treat as `FJB2`

This appliance mapping is confirmed in the native BLE module.

### Intimate Discovery Notes

The original app uses a separate intimate scan flow with the device-name filter `XiYu`.

Confirmed:

- intimate devices are discovered through the same BLE stack
- scan results are merged by `mac`
- intimate local `type` values `0..4` are used later by the UI

Not confirmed:

- a native advertisement-byte mapping for intimate products comparable to appliance `device_type`

Practical implication:

- appliance classification is advertisement-byte based
- intimate classification is currently best treated as app-level product mapping layered on top of scan results

MAC formatting:

```
XX:XX:XX:XX:XX:XX
```

The encryption key is extracted from the manufacturer data hex string at `[len-8:len-6]`.

---

## Timing and Limits

| Item | Value |
|------|-------|
| BLE write delay | `250 ms` |
| operation timeout | `5,000 ms` |
| default MTU | `23 bytes` |
| provisioning chunk payload | `18 bytes` |
| M2 range domain | `0..92` |
| intimate custom slots | `32`, `33`, `34` |

---

## Reference Sources

Primary local sources:

- [tingon.py](C:/Users/seanh/Desktop/tingon/tingon.py)
- [index.android.bundle](C:/Users/seanh/Desktop/tingon/resources/assets/index.android.bundle)
- [AndroidManifest.xml](C:/Users/seanh/Desktop/tingon/resources/AndroidManifest.xml)
