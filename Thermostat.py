# Smart thermostat, built for M5Stack Core2, using MQTT to communicate with relays.
# Integrated with Home Assistant (through MQTT). Autodiscovery of ENV sensor HVAC platform
# Requires M5Stack Core2 and ENVII sensor
# Work in progress. Non-functional.

from m5stack import *
from m5stack_ui import *
from uiflow import *
import wifiCfg
from m5mqtt import M5mqtt
import unit
import math
from numbers import Number
import config

ATTR_MANUFACTURER = "M5Stack"
ATTR_MODEL = "Core 2"
ATTR_NAME = "Core 2 Thermostat"

DEFAULT_DISC_PREFIX = "homeassistant/"
DEFAULT_TOPIC_HVAC = "core2/hvac/"
DEFAULT_TOPIC_SENSORS = "core2/env2/"
DEFAULT_TOPIC_DEBUG = "core2/debug/"

DISP_R1 = 90
DISP_R2 = 70
DISP_XCOORD = 157
DISP_YCOORD = 98

MQTT_IP = config.MQTT_IP
MQTT_PORT = config.MQTT_PORT
MQTT_ID = 'Thermostat'
MQTT_USER = config.MQTT_USER
MQTT_PASS = config.MQTT_PASS
MQTT_KEEPALIVE = 300

WIFI_SSID = config.WIFI_SSID
WIFI_PASS = config.WIFI_PASS

KEY_AVAILABILITY_TOPIC = "avty_t"
KEY_COMMAND_TOPIC = "cmd_t"
KEY_DEVICE = "dev"
KEY_DEVICE_CLASS = "dev_cla"
KEY_IDENTIFIERS = "ids"
KEY_MANUFACTURER = "mf"
KEY_MODEL = "mdl"
KEY_NAME = "name"
KEY_PAYLOAD_AVAILABLE = "pl_avail"
KEY_PAYLOAD_NOT_AVAILABLE = "pl_not_avail"
KEY_STATE_TOPIC = "stat_t"
KEY_UNIQUE_ID = "uniq_id"
KEY_VALUE_TEMPLATE = "val_tpl"

TOPIC_ANNOUNCE = "announce"
TOPIC_STATUS = "status"
TOPIC_STATE = "state"

TPL_TEMPERATURE = "{{value_json.temperature}}"
TPL_PRESSURE = "{{value_json.pressure}}"
TPL_HUMIDITY = "{{value_json.humidity}}"

screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x000000)
img_fan = M5Img("res/fan.png", x=132, y=195, parent=None)
img_settings = M5Img("res/settings.png", x=240, y=195, parent=None)
img_thermo = M5Img("res/Thermo_off.png", x=24, y=195, parent=None)
slider_target = M5Slider(x=125, y=128, w=70, h=12, min=15, max=25, bg_c=0xa0a0a0, color=0x08A2B0, parent=None)
slider_target.set_hidden(True)
lbl_target = M5Label('20', x=135, y=80, color=0x000, font=FONT_MONT_40, parent=None)
lbl_action = M5Label('', x=135, y=60, color=0x000, font=FONT_MONT_12, parent=None)

# Setup initial comms and register with Home Assistant (through auto-discovery)
def comms_setup():
    wifiCfg.doConnect(WIFI_SSID, WIFI_PASS)
    m5mqtt = M5mqtt(MQTT_ID, MQTT_IP, MQTT_PORT, MQTT_USER, MQTT_PASS, MQTT_KEEPALIVE)
    m5mqtt.start()
    
    # Register ENVII Temperature sensor with Home Assistant
    topic = "%ssensor/core2/core2-temp/config" % DEFAULT_DISC_PREFIX
    payload = {        
        KEY_NAME: "Core2 Temperature",
        KEY_PAYLOAD_AVAILABLE: "on",
        KEY_PAYLOAD_NOT_AVAILABLE: "off",
        KEY_DEVICE_CLASS: "temperature",
        KEY_UNIQUE_ID: "12234",
        KEY_DEVICE: {
            KEY_IDENTIFIERS: ["12234"],
            KEY_NAME: ATTR_NAME,
            KEY_MODEL: ATTR_MODEL,
            KEY_MANUFACTURER: ATTR_MANUFACTURER
        },
        KEY_STATE_TOPIC: "~state",
        "~": DEFAULT_TOPIC_SENSORS,
        KEY_AVAILABILITY_TOPIC: "~status",
        KEY_VALUE_TEMPLATE: TPL_TEMPERATURE
    }
    m5mqtt.publish(topic, str(payload))
    
    # Register ENVII Pressure sensor with Home Assistant
    topic = "%ssensor/core2/core2-pressure/config" % DEFAULT_DISC_PREFIX
    payload = {        
        KEY_NAME: "Core2 Pressure",
        KEY_PAYLOAD_AVAILABLE: "on",
        KEY_PAYLOAD_NOT_AVAILABLE: "off",
        KEY_DEVICE_CLASS: "pressure",
        KEY_UNIQUE_ID: "122346",
        KEY_DEVICE: {
            KEY_IDENTIFIERS: ["12234"],
            KEY_NAME: ATTR_NAME,
            KEY_MODEL: ATTR_MODEL,
            KEY_MANUFACTURER: ATTR_MANUFACTURER
        },
        KEY_STATE_TOPIC: "~state",
        "~": DEFAULT_TOPIC_SENSORS,
        KEY_AVAILABILITY_TOPIC: "~status",
        KEY_VALUE_TEMPLATE: TPL_PRESSURE
    }
    m5mqtt.publish(topic, str(payload))    

    # Register ENVII Humidity sensor with Home Assistant
    topic = "%ssensor/core2/core2-humid/config" % DEFAULT_DISC_PREFIX
    payload = {        
        KEY_NAME: "Core2 Humidity",
        KEY_PAYLOAD_AVAILABLE: "on",
        KEY_PAYLOAD_NOT_AVAILABLE: "off",
        KEY_DEVICE_CLASS: "pressure",
        KEY_UNIQUE_ID: "122347",
        KEY_DEVICE: {
            KEY_IDENTIFIERS: ["12234"],
            KEY_NAME: ATTR_NAME,
            KEY_MODEL: ATTR_MODEL,
            KEY_MANUFACTURER: ATTR_MANUFACTURER
        },
        KEY_STATE_TOPIC: "~state",
        "~": DEFAULT_TOPIC_SENSORS,
        KEY_AVAILABILITY_TOPIC: "~status",
        KEY_VALUE_TEMPLATE: TPL_HUMIDITY
    }
    m5mqtt.publish(topic, str(payload))
    
    # Send Availability notice to Home Assistant
    m5mqtt.publish('%sstatus' % DEFAULT_TOPIC_SENSORS,'on')
    
comms_setup()
