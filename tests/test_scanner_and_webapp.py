import unittest
from unittest.mock import patch

import tingon_py
from tingon_py import DeviceProfile
from tingon_py.scanner import scan
from tingon_py.webapp import main as run_webapp


class FakeDevice:
    def __init__(self, address: str, name: str):
        self.address = address
        self.name = name


class FakeAdvertisement:
    def __init__(self, rssi: int = -42, manufacturer_data=None):
        self.rssi = rssi
        self.manufacturer_data = manufacturer_data or {}


class FakeScanner:
    def __init__(self):
        self._callback = None
        self.started = False
        self.stopped = False
        self.unregister_called = False

    def register_detection_callback(self, callback):
        self._callback = callback

        def unregister():
            self.unregister_called = True

        return unregister

    async def start(self):
        self.started = True
        if self._callback is not None:
            self._callback(FakeDevice("AA:BB:CC:DD:EE:FF", "TINGON M2"), FakeAdvertisement())

    async def stop(self):
        self.stopped = True


class ScannerAndWebappTests(unittest.IsolatedAsyncioTestCase):
    async def test_scanner_accepts_injected_backend(self):
        scanner = FakeScanner()

        devices = await scan(scanner=scanner, timeout=0)

        self.assertTrue(scanner.started)
        self.assertTrue(scanner.stopped)
        self.assertTrue(scanner.unregister_called)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].profile, DeviceProfile.M2)

    async def test_client_scan_uses_same_injected_backend(self):
        scanner = FakeScanner()

        devices = await tingon_py.TingonClient.scan(scanner=scanner, timeout=0)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].profile, DeviceProfile.M2)


class WebappEntryPointTests(unittest.TestCase):
    def test_webapp_requires_optional_dependencies(self):
        missing_dep = ModuleNotFoundError("No module named 'fastapi'", name="fastapi")

        with patch("tingon_py.webapp.importlib.import_module", side_effect=missing_dep):
            with self.assertRaises(SystemExit) as ctx:
                run_webapp()

        self.assertIn("tingon-py[web]", str(ctx.exception))
