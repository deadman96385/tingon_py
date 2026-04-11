"""BLE service and characteristic UUID constants for TINGON devices."""

from __future__ import annotations


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

# Junk-data filter for command notifications
JUNK_DATA = "000102030405060708090A0B0C0D0E"

# Provisioning host/port when device is in AP mode
PROV_HOST = "10.10.100.254"
PROV_PORT = 9091

# Delay between BLE writes
WRITE_DELAY = 0.25
