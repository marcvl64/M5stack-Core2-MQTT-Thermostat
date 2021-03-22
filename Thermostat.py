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