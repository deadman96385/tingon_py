"""Tests for the TingonDevice / TingonClient callback registry surface.

These are deliberately transport-free: they poke ``_fire_callbacks`` /
``_handle_disconnect`` directly and verify listener behaviour around
``register_callback``. Integration against a real BLE transport is out
of scope for unit tests.
"""

from __future__ import annotations

import unittest

from tingon_py import DeviceProfile, TingonClient, TingonDevice
from tingon_py.mock.device import MockTingonDevice


class RegisterCallbackTests(unittest.TestCase):
    def test_register_callback_fires_on_state_change(self):
        device = TingonDevice()
        calls: list[int] = []

        device.register_callback(lambda: calls.append(1))
        device._fire_callbacks()
        device._fire_callbacks()

        self.assertEqual(calls, [1, 1])

    def test_unregister_function_removes_listener(self):
        device = TingonDevice()
        calls: list[int] = []

        unregister = device.register_callback(lambda: calls.append(1))
        device._fire_callbacks()
        unregister()
        device._fire_callbacks()

        self.assertEqual(calls, [1])

    def test_second_unregister_call_is_a_noop(self):
        device = TingonDevice()
        unregister = device.register_callback(lambda: None)

        unregister()
        unregister()  # must not raise

    def test_raising_listener_does_not_block_others(self):
        device = TingonDevice()
        calls: list[str] = []

        def boom():
            raise RuntimeError("boom")

        device.register_callback(boom)
        device.register_callback(lambda: calls.append("ok"))
        device._fire_callbacks()

        # The healthy listener must still have fired.
        self.assertEqual(calls, ["ok"])

    def test_client_register_callback_forwards_to_device(self):
        client = TingonClient()
        calls: list[int] = []

        client.register_callback(lambda: calls.append(1))
        client._device._fire_callbacks()

        self.assertEqual(calls, [1])


class AvailabilityTests(unittest.TestCase):
    def test_device_available_flips_false_on_disconnect_hook(self):
        device = TingonDevice()
        # Simulate that a connect happened so _handle_disconnect has
        # something meaningful to flip.
        device._available = True
        calls: list[int] = []
        device.register_callback(lambda: calls.append(1))

        device._handle_disconnect(None)

        self.assertFalse(device.available)
        self.assertEqual(calls, [1])

    def test_device_disconnect_hook_invokes_consumer_callback(self):
        device = TingonDevice()
        device._available = True
        consumer_calls: list[int] = []

        device._handle_disconnect(lambda: consumer_calls.append(1))

        self.assertEqual(consumer_calls, [1])


class MockDeviceCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_mock_register_callback_and_disconnect(self):
        mock = MockTingonDevice("AA:BB:CC:DD:EE:FF", DeviceProfile.M2, "TINGON M2")
        calls: list[int] = []
        mock.register_callback(lambda: calls.append(1))

        await mock.connect(profile=DeviceProfile.M2)
        self.assertTrue(mock.available)

        await mock.disconnect()
        self.assertFalse(mock.available)
        self.assertEqual(calls, [1])

    async def test_mock_appliance_state_as_dict_roundtrip(self):
        mock = MockTingonDevice("AA:BB:CC:DD:EE:FF", DeviceProfile.GS, "TINGON GS")
        await mock.connect(profile=DeviceProfile.GS)

        state = mock.appliance_state
        self.assertIsNotNone(state)
        as_dict = state.as_dict()
        self.assertIn("power", as_dict)
        self.assertIn("setting_water_temp", as_dict)

    async def test_mock_intimate_status_dict_available(self):
        mock = MockTingonDevice("AA:BB:CC:DD:EE:FF", DeviceProfile.M2, "TINGON M2")
        await mock.connect(profile=DeviceProfile.M2)

        status = mock.intimate_status_dict()
        self.assertIsNotNone(status)
        self.assertIn("play", status)


if __name__ == "__main__":
    unittest.main()
