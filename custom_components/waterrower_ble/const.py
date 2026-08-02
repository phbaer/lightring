"""Constants for the WaterRower Local BLE integration."""

from typing import Final

DOMAIN: Final = "waterrower_ble"
CONF_ADDRESS: Final = "address"
CONF_DEVICE_TYPE: Final = "device_type"

LOCAL_NAME: Final = "LightRing BF"
DEVICE_NAME: Final = "WaterRower LightRing"
MANUFACTURER: Final = "WaterRower"
MODEL: Final = "LightRing Bluetooth"

SERVICE_UUID: Final = "e54b1234-67f5-479e-8711-b3b99198ce6c"
CONTROL_CHARACTERISTIC_UUID: Final = "e54b0003-67f5-479e-8711-b3b99198ce6c"

DEVICE_TYPE_LIGHTRING: Final = "lightring"
DEVICE_TYPE_SMARTROW: Final = "smartrow"
SMARTROW_LOCAL_NAME: Final = "SmartRow"
SMARTROW_DEVICE_NAME: Final = "SmartRow"
SMARTROW_MODEL: Final = "SmartRow power meter"
SMARTROW_SERVICE_UUID: Final = "00001234-0000-1000-8000-00805f9b34fb"
SMARTROW_COMMAND_CHARACTERISTIC_UUID: Final = "00001235-0000-1000-8000-00805f9b34fb"
SMARTROW_TELEMETRY_CHARACTERISTIC_UUID: Final = "00001236-0000-1000-8000-00805f9b34fb"
SMARTROW_HEARTBEAT_COMMAND: Final = b"$"
SMARTROW_HEARTBEAT_INTERVAL_SECONDS: Final = 2
SMARTROW_START_SESSION_COMMAND: Final = b"\rV@\r"
SMARTROW_CONFIG_REQUEST_COMMAND: Final = b"*"
SMARTROW_REMOTE_REQUEST_COMMAND: Final = b"\rREMOTE>\r"
SMARTROW_KEYLOCK_REQUEST_COMMAND: Final = b"#"

# Proprietary command byte for displaying one solid RGB colour.
COMMAND_SOLID_COLOR: Final = 0x00
COMMAND_PIXEL_FRAME: Final = 0x02
COMMAND_START_FRAME: Final = 0x03
LED_COUNT: Final = 52

SERVICE_SET_PIXELS: Final = "set_pixels"
ATTR_ADDRESS: Final = "address"
ATTR_PIXELS: Final = "pixels"
