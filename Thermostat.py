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
import json
import config

ATTR_MANUFACTURER = "M5Stack"
ATTR_MODEL = "Core 2"
ATTR_NAME = "Core 2 Thermostat"

DEFAULT_DISC_PREFIX = "homeassistant/"
DEFAULT_TOPIC_HVAC = "core2/hvac/"
DEFAULT_TOPIC_SENSOR_PREFIX = "core2/env2/"
DEFAULT_TOPIC_DEBUG = "core2/debug/"

DISP_R1 = 90
DISP_R2 = 70
DISP_XCOORD = 157
DISP_YCOORD = 98
DISP_COLOR_COOL = 0x3366ff
DISP_COLOR_HEAT = 0xff6600

MQTT_IP = config.MQTT_IP
MQTT_PORT = config.MQTT_PORT
MQTT_ID = 'Thermostat'
MQTT_USER = config.MQTT_USER
MQTT_PASS = config.MQTT_PASS
MQTT_KEEPALIVE = 300

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

RELAY_TOPIC_HEAT = "core2/heat"
RELAY_TOPIC_COOL = "core2/cool"
RELAY_TOPIC_FAN = "core2/fan"

TOPIC_ANNOUNCE = "announce"
TOPIC_STATUS = "status"
TOPIC_STATE = "state"

TPL_TEMPERATURE = "{{value_json.temperature}}"
TPL_PRESSURE = "{{value_json.pressure}}"
TPL_HUMIDITY = "{{value_json.humidity}}"

WIFI_SSID = config.WIFI_SSID
WIFI_PASS = config.WIFI_PASS

THERMO_MIN_TEMP = 0            # C
THERMO_MAX_TEMP = 40           # C
THERMO_MIN_TARGET = 15         # C
THERMO_MAX_TARGET = 25         # C
THERMO_MIN_CYCLE = 10          # seconds
THERMO_COLD_TOLERANCE = 0      # C
THERMO_HEAT_TOLERANCE = 0      # C
THERMO_UPDATE_FREQUENCY = 20   # seconds
THERMO_MODES = ["off", "auto", "man", "heat", "cool", "fan"]

screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x000000)
env20 = unit.get(unit.ENV2, unit.PORTA)
img_fan = M5Img("res/fan.png", x=132, y=195, parent=None)
img_settings = M5Img("res/settings.png", x=240, y=195, parent=None)
img_thermo = M5Img("res/Thermo_off.png", x=24, y=195, parent=None)
slider_target = M5Slider(x=125, y=128, w=70, h=12, min=15, max=25, bg_c=0xa0a0a0, color=0x08A2B0, parent=None)
slider_target.set_hidden(True)
lbl_target = M5Label('', x=135, y=80, color=0x000, font=FONT_MONT_40, parent=None)
lbl_action = M5Label('', x=135, y=60, color=0x000, font=FONT_MONT_12, parent=None)
lbl_mode = M5Label('', x=141, y=168, color=0xffffff, font=FONT_MONT_12, parent=None)


# Setup initial comms and register with Home Assistant (through auto-discovery)
def comms_init():
    global m5mqtt
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
        "~": DEFAULT_TOPIC_SENSOR_PREFIX,
        KEY_AVAILABILITY_TOPIC: "~status",
        KEY_VALUE_TEMPLATE: TPL_TEMPERATURE
    }
    m5mqtt.publish(topic, str(json.dumps(payload)))
    
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
        "~": DEFAULT_TOPIC_SENSOR_PREFIX,
        KEY_AVAILABILITY_TOPIC: "~status",
        KEY_VALUE_TEMPLATE: TPL_PRESSURE
    }
    m5mqtt.publish(topic, str(json.dumps(payload)))    

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
        "~": DEFAULT_TOPIC_SENSOR_PREFIX,
        KEY_AVAILABILITY_TOPIC: "~status",
        KEY_VALUE_TEMPLATE: TPL_HUMIDITY
    }
    m5mqtt.publish(topic, str(json.dumps(payload)))
    
    # Send Availability notice to Home Assistant
    m5mqtt.publish('%sstatus' % DEFAULT_TOPIC_SENSOR_PREFIX,'on')

#    m5mqtt.publish(str('homeassistant/sensor/core2/core2-temp/config'),str('{"name":"Core2 Temperature","pl_avail":"on","pl_not_avail":"off","device_class":"temperature","uniq_id":"12234","device":{"name":"Core2 Thermostat","ids":["12234"],"mdl":"Core 2","mf":"M5 Stack"},"~":"core2/env2/","state_topic":"~state","availability_topic":"~status","value_template":"{{value_json.temperature}}"}'))

def thermostat_init():
    global action, actual_temp, blink, change_ignored, cycle, delay, ticks, thermo_state, fan_state, cooling_state, heating_state, target_temp
    action = 0
    actual_temp = env20.temperature
    blink = 0
    change_ignored = 0
    cycle = 0
    delay = 0
    slider_target.set_range(THERMO_MIN_TARGET, THERMO_MAX_TARGET)
    slider_target.set_value(20)
    thermo_state = THERMO_MODES[0]
    target_temp = slider_target.get_value()
    ticks = 0
    
    # initial state of thermostat is OFF and all appliances are OFF
    fan_state = 0
    cooling_state = 0
    heating_state = 0

# update display everytime there is a change (due to incoming HA info, screen interaction, or sensor data changes)
def update_display():
    lcd.clear()
    lbl_mode.set_text(thermo_state)
    
    # If mode is off, manual
    if thermo_state in [THERMO_MODES[index] for index in [0,2]]:
        lcd.font(lcd.FONT_DejaVu40)
        lbl_action.set_text('')
        lbl_target.set_text("---")
        lbl_target.set_text_color(0xffffff)
        
    # If cooling is on
    elif cooling_state == 1:
        lbl_action.set_text('COOLING')
        lbl_action.set_text_color(DISP_COLOR_COOL)
        lbl_target.set_text(str(target_temp))
        lbl_target.set_text_color(DISP_COLOR_COOL)
        slider_target.set_hidden(False)
        if change_ignored == 1:
            timerSch.run("blink_now", 305, 0x00)
        else:
            timerSch.stop("blink_now")
            lbl_target.set_text_color(DISP_COLOR_COOL)
        
    # if heating is on
    elif heating_state == 1:
        lbl_action.set_text('HEATING')
        lbl_action.set_text_color(DISP_COLOR_HEAT)
        lbl_target.set_text(str(target_temp))
        lbl_target.set_text_color(DISP_COLOR_HEAT)
        slider_target.set_hidden(False)
        if change_ignored == 1:
            timerSch.run("blink_now", 305, 0x00)
        else:
            timerSch.stop("blink_now")
            lbl_target.set_text_color(DISP_COLOR_HEAT)

    # if fan is on
    elif fan_state == 1:
        lbl_action.set_text('FAN')
        lbl_action.set_text_color(0xffffff)
        lbl_target.set_text(str(target_temp))
        lbl_target.set_text_color(0xffffff)
        slider_target.set_hidden(False)
        if change_ignored == 1:
            timerSch.run("blink_now", 305, 0x00)
        else:
            timerSch.stop("blink_now")
            lbl_target.set_text_color(0xffffff)
            
   # if none of the above conditions are true     
    else:
        lbl_action.set_text('')
        lbl_target.set_text(str(target_temp))
        lbl_target.set_text_color(0xffffff)
        slider_target.set_hidden(False)
        if change_ignored == 1:
            timerSch.run("blink_now", 305, 0x00)
        else:
            timerSch.stop("blink_now")
            lbl_target.set_text_color(0xffffff)
            
# Draw the temperature arc
    t = THERMO_MIN_TEMP
    while t <= THERMO_MAX_TEMP:
        angle = (t * 8 + 200) % 360
        lcd.font(lcd.FONT_DejaVu18)
        if t > min(round(actual_temp),target_temp) and t < max(round(actual_temp), target_temp) and thermo_state in [THERMO_MODES[index] for index in [1,3,4]]:
            lcd.line(
                int(DISP_R1 * math.sin(angle / 180 * math.pi) + DISP_XCOORD),
                int(DISP_YCOORD - DISP_R1 * math.cos(angle / 180 * math.pi)),
                int(DISP_R2 * math.sin(angle / 180 * math.pi) + DISP_XCOORD),
                int(DISP_YCOORD - DISP_R2 * math.cos(angle / 180 * math.pi)),
                0xffffff)
        elif t == round(actual_temp):
            lcd.line(
                int(DISP_R1 * math.sin(angle / 180 * math.pi) + DISP_XCOORD),
                int(DISP_YCOORD - DISP_R1 * math.cos(angle / 180 * math.pi)),
                int((DISP_R2 - 10) * math.sin(angle / 180 * math.pi) + DISP_XCOORD),
                int(DISP_YCOORD - (DISP_R2 - 10) * math.cos(angle / 180 * math.pi)),
                0xffffff)
        else:
            lcd.line(
                int(DISP_R1 * math.sin(angle / 180 * math.pi) + DISP_XCOORD),
                int(DISP_YCOORD - DISP_R1 * math.cos(angle / 180 * math.pi)),
                int(DISP_R2 * math.sin(angle / 180 * math.pi) + DISP_XCOORD),
                int(DISP_YCOORD - DISP_R2 * math.cos(angle / 180 * math.pi)),
                0x333333)
        t += 0.5    
    if round(actual_temp) >= target_temp or thermo_state in [THERMO_MODES[index] for index in [0,2,5]]:
        lcd.print(
            round(actual_temp),
            int(DISP_R1 * math.sin(((actual_temp * 8 + 200) % 360 +4) / 180 * math.pi) + DISP_XCOORD),
            int(DISP_YCOORD - DISP_R1 * math.cos(((actual_temp * 8 +200) % 360 +4) / 180 * math.pi)),
            0xffffff)
    else:
        lcd.print(
            round(actual_temp),
            int(DISP_R1 * math.sin(((actual_temp * 8 + 200) % 360 -20) / 180 * math.pi) + DISP_XCOORD),
            int(DISP_YCOORD - DISP_R1 * math.cos(((actual_temp * 8 +200) % 360 -20) / 180 * math.pi)),
            0xffffff)
    img_thermo.set_hidden(False)

def thermostat_decision_logic():
    global actual_temp, target_temp
    actual_temp = env20.temperature
    target_temp = slider_target.get_value()
    if (
        actual_temp <= target_temp - THERMO_COLD_TOLERANCE and
        heating_state == 0 and
        thermo_state in [THERMO_MODES[index] for index in [1,3]]):
        # thermostat needs to turn on heating
        change_to("heating on")
    elif (
        actual_temp >= target_temp + THERMO_HEAT_TOLERANCE and
        cooling_state == 0 and
        thermo_state in [THERMO_MODES[index] for index in [1,4]]):
        # thermostat needs to turn on cooling
        change_to("cooling on")
    elif (
        actual_temp >= target_temp + THERMO_HEAT_TOLERANCE and
        fan_state == 0 and
        thermo_state in [THERMO_MODES[index] for index in [5]]):
        # thermostat needs to turn on fan cooling
        change_to("fan on")

    elif (
        (actual_temp >= target_temp or
         thermo_state in [THERMO_MODES[index] for index in [0,2,4,5]]) and        
         heating_state == 1):
        # thermostat needs to turn off heating
        change_to("heating off")
    elif (
        (actual_temp <= target_temp or
         thermo_state in [THERMO_MODES[index] for index in [0,2,3,5]]) and
         cooling_state == 1):
        # thermostat needs to turn off cooling
        change_to ("cooling off")
    elif (
        (actual_temp <= target_temp or
         thermo_state in [THERMO_MODES[index] for index in [0,2,3,4]]) and
         fan_state == 1):
        # thermostat needs to turn off fan
        change_to ("fan off")
    else:
        # no action
        timerSch.stop("blink_now")
        update_display()


def change_to (action):
    global change_ignored, heating_state, cooling_state, fan_state, m5mqtt, delay
    if delay == 0:
        change_ignored = 0
        if action == "heating on":
            m5mqtt.publish(RELAY_TOPIC_HEAT,"on")
            heating_state = 1
            if cooling_state == 1:
                m5mqtt.publish(RELAY_TOPIC_COOL, "off")
                cooling_state = 0
            if fan_state == 1:
                m5mqtt.publish(RELAY_TOPIC_FAN, "off")
                fan_state = 0
        elif action == "cooling on":
            m5mqtt.publish(RELAY_TOPIC_COOL, "on")
            cooling_state = 1
            if heating_state == 1:
                m5mqtt.publish(RELAY_TOPIC_HEAT, "off")
                heating_state = 0
            if fan_state == 1:
                m5mqtt.publish(RELAY_TOPIC_FAN, "off")
                fan_state = 0
        elif action == "fan on":
            m5mqtt.publish(RELAY_TOPIC_FAN, "on")
            fan_state = 1
            if heating_state == 1:
                m5mqtt.publish(RELAY_TOPIC_HEAT, "off")
                heating_state = 0
            if cooling_state == 1:
                m5mqtt.publish(RELAY_TOPIC_COOL, "off")
                cooling_state = 0           
        elif action == "heating off":
            m5mqtt.publish(RELAY_TOPIC_HEAT,"off")
            heating_state = 0
        elif action == "cooling off":
            m5mqtt.publish(RELAY_TOPIC_COOL, "off")
            cooling_state = 0
        elif action == "fan off":
            m5mqtt.publish(RELAY_TOPIC_FAN, "off")
            fan_state = 0           
        delay = THERMO_MIN_CYCLE
        timerSch.run("delayed_start", 1000, 0x00)
        timerSch.stop("blink_now")
        update_display()
    else:
        change_ignored = 1
        update_display()



def update_mqtt_state_topics():
    payload = {
        "temperature": env20.temperature,
        "humidity": env20.humidity,
        "pressure": env20.pressure
        }
    m5mqtt.publish(DEFAULT_TOPIC_SENSOR_PREFIX + TOPIC_STATE,str(json.dumps(payload)))
        
@timerSch.event("delayed_start")
def tdelayed_start():
    global delay
    delay -= 1
    if delay == 0:
        timerSch.stop("delayed_start")

@timerSch.event("main_loop")
def tmain_loop():
    global ticks
    ticks += 1
            
@timerSch.event("blink_now")
def tblink_now():
    global blink
    if heating_state == 1:
        color = DISP_COLOR_HEAT
    elif cooling_state == 1:
        color = DISP_COLOR_COOL
    else:
        color = 0xffffff
    if blink == 0:
        lbl_target.set_text_color(0x000000)
        lbl_action.set_text_color(0x000000)
        blink = 1
    else:
        lbl_target.set_text_color(color)
        lbl_action.set_text_color(color)
        blink = 0        

def slider_target_changed(target_temp):
    thermostat_decision_logic()

slider_target.changed(slider_target_changed)

comms_init()
thermostat_init()
thermostat_decision_logic()
timerSch.run("main_loop", 999, 0x00)
while True:
    if btnA.wasPressed():
        m5mqtt.publish(DEFAULT_TOPIC_DEBUG,'DEBUG-Pressed A')
        thermo_state = THERMO_MODES[(THERMO_MODES.index(thermo_state) + 1) % 6]
        thermostat_decision_logic()
        
    if btnB.wasPressed():
        m5mqtt.publish(DEFAULT_TOPIC_DEBUG,'DEBUG-Pressed B')
        
    if btnC.wasPressed():
        m5mqtt.publish(DEFAULT_TOPIC_DEBUG,'DEBUG-Pressed C')

    if ticks == THERMO_UPDATE_FREQUENCY:
        thermostat_decision_logic()
        update_mqtt_state_topics()
        ticks = 0
    wait_ms(2)
    