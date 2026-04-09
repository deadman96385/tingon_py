import unittest

import tingon_py
from tingon_py import DeviceProfile, TingonClient, TingonProtocolError, TingonUnsupportedCapability
from tingon_py.core import CAP_WATER_TEMP


class PublicApiTests(unittest.TestCase):
    def test_package_root_exports_only_curated_api(self):
        self.assertIs(tingon_py.TingonClient, TingonClient)
        self.assertFalse(hasattr(tingon_py, "TingonDevice"))
        self.assertFalse(hasattr(tingon_py, "MockTingonDevice"))

    def test_unknown_profile_raises_typed_error(self):
        with self.assertRaises(TingonProtocolError):
            DeviceProfile.parse("not-a-real-profile")

    def test_client_capability_checks_raise_typed_error(self):
        client = TingonClient()
        client._device._profile = DeviceProfile.A1

        with self.assertRaises(TingonUnsupportedCapability):
            client.require_capability(CAP_WATER_TEMP)
