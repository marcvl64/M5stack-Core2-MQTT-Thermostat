# Smart thermostat, built for M5Stack Core2.
#
# Key features:
# - all thermostat logic is built into this Python script and runs on Core2
# - thermostat supports auto, manual, fan, heat, cool modes
# - minimum cycle duration can be set (THERMO_MIN_CYCLE)
# - swing mode is enabled and can be customized (THERMO_COLD_TOLERANCE and THERMO_HEAT_TOLERANCE)
#
# Configuration considerations:
# - Relies on separate config.py file to store secrets (WiFI and MQTT connection details)
# - Gets actual temperature through ENVII sensor, connected to the Core2. But you could easily set up another
#   external temperature sensor and communicate values to the Core2 through MQTT
# - Uses MQTT to communicate with relays that turn on/off furnace, fan, and AC. You need to configure the right
#   topics and payloads to establish that communication (variables starting with RELAY_)
# - Graphics files for heat/cool/fan need to be stored in the /res directory (from materialdesignicons.com, 24x24 px, R:66, G:165, B:245)
#
# Home Assistant integration:
# - Integrates with Home Assistant through MQTT (you need MQTT enabled on the HA side)
# - Supports MQTT auto-discovery. No configuration needed on the HA side.
# - Will create 'Core2 Thermostat' device with following entities:
#    - 3 sensors for temperature, humidity, and pressure (if using the ENVII)
#    - 1 thermostat entity
#    - 2 switch entities for manually turning on/off heater/ac (fan is not implemented yet)
# - The thermostat entity allows you to control target temperature and thermostat mode through HA. Any changes will be reflected on the Core2.
# - When you manually switch a device on/off through the HA interface, the thermostat entity will be switched to 'off'
#   while the Core2 will automatically switch to manual mode (HA doesn't support a 'manual mode' for the thermostat)
# - The switch entities in HA are subscribed to the same MQTT topics you've configured to communicate with your appliances. However, when HA issues
#   a switch change, the command will go only to the Core2, who will process it, switch the termostat to manual mode, and then executes a state change.
#
# Usage notes:
# - Upon start the thermostat will be OFF. Tapping the OFF label will run the thermostat through the various modes: OFF - AUTO - MAN - HEAT - COOL - FAN
# - When in manual mode, use the A/B/C buttons to turn on/off heat pump, AC, Fan. Only 1 device can be on at a given time.
# - When min cycle duration requirement isn't met, the Core2 display will blink until it is able to implement the change
# - Blinking is not supported on the Lovelace thermostat card. The HA dashboard will not change until the min cycle duration requirement is met.
# - Core2 can display temperature in Celsius or Fahrenheit (set DISP_TEMPERATURE accordingly). Default is Fahrenheit.
#   Home Assistant will display temperature depending on your HA preferences (metric vs imperial) 

from m5stack import *
from m5stack_ui import *
from uiflow import *
import wifiCfg
from m5mqtt import M5mqtt
import unit
import math
from numbers import Number
import lvgl as lv
import json
import config

# Device information
ATTR_MANUFACTURER = "M5Stack"
ATTR_MODEL = "Core 2"
ATTR_NAME = "Core 2 Thermostat"

# Default topics used to communicate with Home Assistant
DEFAULT_DISC_PREFIX = "homeassistant/"
DEFAULT_TOPIC_THERMOSTAT_PREFIX = "core2/thermostat/"
DEFAULT_TOPIC_SENSOR_PREFIX = "core2/env2/"
DEFAULT_TOPIC_DEBUG = "core2/debug/"
DEFAULT_TOPIC_SWITCH_PREFIX = "core2/switch/"

# Topics to send/receive commands to other sensors directly
MASTER_SWITCH_TOPIC = "test-master-switch/switch/master_switch/state"

# Details on how the information on the Core2 display should be rendered
DISP_R1 = 90
DISP_R2 = 70
DISP_XCOORD = 160
DISP_YCOORD = 98
DISP_COLOR_COOL = 0x3366ff
DISP_COLOR_HEAT = 0xff6600
DISP_LBL_TARGET_OFFSET = -20
DISP_LBL_ACTION_OFFSET = -51
DISP_LBL_MODE_OFFSET = 55
DISP_TEMPERATURE = "F" # change to "C" if your prefer Celsius

# MQTT connection details
MQTT_IP = config.MQTT_IP
MQTT_PORT = config.MQTT_PORT
MQTT_ID = 'Thermostat'
MQTT_USER = config.MQTT_USER
MQTT_PASS = config.MQTT_PASS
MQTT_KEEPALIVE = 300

# JSON Keys used to configure the device with Home Assistant
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
KEY_ICON = "ic"

KEY_ACTION_TOPIC = "act_t"
KEY_CURRENT_TEMPERATURE_TOPIC = "curr_temp_t"
KEY_CURRENT_TEMPERATURE_TEMPLATE = "curr_temp_tpl"
KEY_INITIAL = "init"
KEY_MAX_TEMP = "max_temp"
KEY_MIN_TEMP = "min_temp"
KEY_MODE_COMMAND_TOPIC = "mode_cmd_t"
KEY_MODE_STATE_TOPIC = "mode_stat_t"
KEY_SEND_IF_OFF = "send_if_off"
KEY_TEMPERATURE_COMMAND_TOPIC = "temp_cmd_t"
KEY_TEMPERATURE_STATE_TOPIC = "temp_stat_t"
KEY_TEMPERATURE_UNIT = "temp_unit"
KEY_MODE_STATE_TEMPLATE = "mode_stat_tpl"
KEY_PAYLOAD_OFF = "pl_off"
KEY_PAYLOAD_ON = "pl_on"
KEY_UNIT_OF_MEASUREMENT = "unit_of_meas"

# Topic and Payload details used to communicate with the furnace, AC, and fan(s)
RELAY_HEAT_TOPIC = "core2/heat"
RELAY_COOL_TOPIC = "core2/cool"
RELAY_FAN_TOPIC = "core2/fan"
RELAY_HEAT_PAYLOAD_ON = "ON"
RELAY_HEAT_PAYLOAD_OFF = "OFF"
RELAY_COOL_PAYLOAD_ON = "ON"
RELAY_COOL_PAYLOAD_OFF = "OFF"
RELAY_FAN_PAYLOAD_ON = "ON"
RELAY_FAN_PAYLOAD_OFF = "OFF"

# Construction of topics for communication with Home Assistant
TOPIC_ANNOUNCE = "announce"
TOPIC_STATUS = "status"
TOPIC_STATE = "state"
TOPIC_MODE_STATE = "mode/state"
TOPIC_ACTION = "action"
TOPIC_MODE_COMMAND = "mode/command"
TOPIC_TEMPERATURE_COMMAND = "temperature/command"
TOPIC_HEATER_COMMAND = "heater/command"
TOPIC_AC_COMMAND = "ac/command"
TOPIC_HEATER_STATUS = "heater/status"
TOPIC_AC_STATUS = "ac/status"
TOPIC_DISCOVERY = "discovery"

# Instructions on how the payload is structured and should be parsed by Home Assistant
TPL_TEMPERATURE = "{{value_json.temperature}}"
TPL_PRESSURE = "{{value_json.pressure}}"
TPL_HUMIDITY = "{{value_json.humidity}}"
TPL_MODE_STATE = '{% set values = {"off":"off", "auto":"auto", "man":"off", "heat":"heat", "cool":"cool", "fan":"fan_only"} %} {{ values[value] }}'
    

WIFI_SSID = config.WIFI_SSID
WIFI_PASS = config.WIFI_PASS

THERMO_MIN_TEMP = 0            # C
THERMO_MAX_TEMP = 40           # C
THERMO_MIN_TARGET = 15         # C
THERMO_MAX_TARGET = 25         # C
THERMO_MIN_CYCLE = 5           # seconds
THERMO_COLD_TOLERANCE = 0.5      # C
THERMO_HEAT_TOLERANCE = 0.5      # C
THERMO_UPDATE_FREQUENCY = 20   # seconds
THERMO_MODES = ["off", "auto", "man", "heat", "cool", "fan"]

screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x000000)

# Using lvgl library to implement an invisible touch area (behind the mode label) to switch thermostat mode
lv.init()
scr = lv.obj() 
scr.set_style_local_bg_color(scr.PART.MAIN, lv.STATE.DEFAULT, lv.color_hex(0x000000))

path_ease_out = lv.anim_path_t()
path_ease_out.init()

# create button
btn = lv.btn(scr) 
btn.set_size(40, 20)
btn.align(None, lv.ALIGN.CENTER, 0, 55)
# set button style to make it invisible and implement a cool touch feedback effect
btn.set_style_local_bg_color(scr.PART.MAIN,lv.STATE.DEFAULT, lv.color_hex(0x0000ff))
styleButton = lv.style_t() # create style
styleButton.set_bg_color(lv.STATE.DEFAULT, lv.color_hex(0x0000ff))
styleButton.set_transition_time(lv.STATE.PRESSED, 300)
styleButton.set_transition_time(lv.STATE.DEFAULT, 0)
styleButton.set_transition_delay(lv.STATE.DEFAULT, 300)
styleButton.set_bg_opa(lv.STATE.DEFAULT, 0)
styleButton.set_bg_opa(lv.STATE.PRESSED, lv.OPA._80)
styleButton.set_border_width(lv.STATE.DEFAULT, 0)
styleButton.set_outline_width(lv.STATE.DEFAULT, 0)
styleButton.set_transform_width(lv.STATE.DEFAULT, -20)
styleButton.set_transform_height(lv.STATE.DEFAULT, -20)
styleButton.set_transform_width(lv.STATE.PRESSED, 0)
styleButton.set_transform_height(lv.STATE.PRESSED, 0)
styleButton.set_transition_path(lv.STATE.DEFAULT, path_ease_out)
styleButton.set_transition_prop_1(lv.STATE.DEFAULT, lv.STYLE.BG_OPA)
styleButton.set_transition_prop_2(lv.STATE.DEFAULT, lv.STYLE.TRANSFORM_WIDTH)
styleButton.set_transition_prop_3(lv.STATE.DEFAULT, lv.STYLE.TRANSFORM_HEIGHT)
btn.add_style(btn.PART.MAIN,styleButton) #define this style

# button press callback action (ie. change thermostat mode)
def change_mode(btn, event):
    global src, thermo_state
    if(event == lv.EVENT.CLICKED):
        btn.set_style_local_bg_color(btn.PART.MAIN, lv.STATE.DEFAULT, lv.color_hex(0xffccf9))
        thermo_state = THERMO_MODES[(THERMO_MODES.index(thermo_state) + 1) % 6]
        m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_MODE_STATE, str(thermo_state)) 
        thermostat_decision_logic()
    
# define callback  
btn.set_event_cb(change_mode)

# load the screen
lv.scr_load(scr)

env20 = unit.get(unit.ENV2, unit.PORTA)
img_BtnA = M5Img("res/heat.png", x=40, y=207, parent=None)
img_BtnB = M5Img("res/cool.png", x=146, y=207, parent=None)
img_BtnC = M5Img("res/fan.png", x=252, y=207, parent=None)
slider_target = M5Slider(x=125, y=128, w=70, h=12, min=15, max=25, bg_c=0xa0a0a0, color=0x08A2B0, parent=None)
slider_target.set_hidden(True)
lbl_target = M5Label('', x=160, y=70, color=0x000, font=FONT_MONT_40, parent=None)
lbl_action = M5Label('', x=160, y=60, color=0x000, font=FONT_MONT_12, parent=None)
lbl_mode = M5Label('', x=160, y=168, color=0xffffff, font=FONT_MONT_12, parent=None)
lbl_target.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
lbl_action.set_align(ALIGN_CENTER, 0, DISP_LBL_ACTION_OFFSET)
lbl_mode.set_align(ALIGN_CENTER, 0, DISP_LBL_MODE_OFFSET)

# Setup initial comms and register with Home Assistant (through auto-discovery)
def comms_init():
    global m5mqtt
    wifiCfg.doConnect(WIFI_SSID, WIFI_PASS)
    m5mqtt = M5mqtt(MQTT_ID, MQTT_IP, MQTT_PORT, MQTT_USER, MQTT_PASS, MQTT_KEEPALIVE)
    
    # Subscribe to HA thermostat mode changes
    m5mqtt.subscribe(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_MODE_COMMAND, rcv_thermo_state)
    
    # Subscribe to HA target temperature changes
    m5mqtt.subscribe(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_TEMPERATURE_COMMAND, rcv_target_temp)

    # Subscribe to HA manual heater changes
    m5mqtt.subscribe(DEFAULT_TOPIC_SWITCH_PREFIX + TOPIC_HEATER_COMMAND, rcv_heater_status)    
    
    # Subscribe to HA manual AC changes
    m5mqtt.subscribe(DEFAULT_TOPIC_SWITCH_PREFIX + TOPIC_AC_COMMAND, rcv_ac_status)     

    # Subscribe to Master OFF switch commands
    m5mqtt.subscribe(MASTER_SWITCH_TOPIC, rcv_master_off)         

    # Subscribe to Home Assistant registration requests
    m5mqtt.subscribe(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_DISCOVERY, rcv_discovery)
    
    m5mqtt.start()
    mqtt_registration()
    mqtt_initialization()

def mqtt_registration():
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
        KEY_UNIT_OF_MEASUREMENT: chr(186) + "C",
        KEY_STATE_TOPIC: "~" + TOPIC_STATE,
        "~": DEFAULT_TOPIC_SENSOR_PREFIX,
        KEY_AVAILABILITY_TOPIC: "~" + TOPIC_STATUS,
        KEY_VALUE_TEMPLATE: TPL_TEMPERATURE
    }
    m5mqtt.publish(topic, json.dumps(payload).encode('utf-8'))

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
        KEY_UNIT_OF_MEASUREMENT: "hPa",        
        KEY_STATE_TOPIC: "~" + TOPIC_STATE,
        "~": DEFAULT_TOPIC_SENSOR_PREFIX,
        KEY_AVAILABILITY_TOPIC: "~" + TOPIC_STATUS,
        KEY_VALUE_TEMPLATE: TPL_PRESSURE
    }
    m5mqtt.publish(topic, str(json.dumps(payload)))    

    # Register ENVII Humidity sensor with Home Assistant
    topic = "%ssensor/core2/core2-humid/config" % DEFAULT_DISC_PREFIX
    payload = {        
        KEY_NAME: "Core2 Humidity",
        KEY_PAYLOAD_AVAILABLE: "on",
        KEY_PAYLOAD_NOT_AVAILABLE: "off",
        KEY_DEVICE_CLASS: "humidity",
        KEY_UNIQUE_ID: "122347",
        KEY_DEVICE: {
            KEY_IDENTIFIERS: ["12234"],
            KEY_NAME: ATTR_NAME,
            KEY_MODEL: ATTR_MODEL,
            KEY_MANUFACTURER: ATTR_MANUFACTURER
        },
        KEY_UNIT_OF_MEASUREMENT: "%", 
        KEY_STATE_TOPIC: "~" + TOPIC_STATE,
        "~": DEFAULT_TOPIC_SENSOR_PREFIX,
        KEY_AVAILABILITY_TOPIC: "~" + TOPIC_STATUS,
        KEY_VALUE_TEMPLATE: TPL_HUMIDITY
    }
    m5mqtt.publish(topic, str(json.dumps(payload)))
 
    # Register Core2 as HVAC device with Home Assistant
    topic = "%sclimate/core2/config" % DEFAULT_DISC_PREFIX
    payload = {
        KEY_NAME: "Core2 Thermostat",
        KEY_PAYLOAD_AVAILABLE: "on",
        KEY_PAYLOAD_NOT_AVAILABLE: "off",
        KEY_UNIQUE_ID: "122348",
        KEY_DEVICE: {
            KEY_IDENTIFIERS: ["12234"],
            KEY_NAME: ATTR_NAME,
            KEY_MODEL: ATTR_MODEL,
            KEY_MANUFACTURER: ATTR_MANUFACTURER
        },
        "~": DEFAULT_TOPIC_THERMOSTAT_PREFIX,
        KEY_ACTION_TOPIC: "~" + TOPIC_ACTION,
        KEY_AVAILABILITY_TOPIC: "~" + TOPIC_STATUS,
        KEY_CURRENT_TEMPERATURE_TOPIC: DEFAULT_TOPIC_SENSOR_PREFIX + TOPIC_STATE,
        KEY_CURRENT_TEMPERATURE_TEMPLATE: TPL_TEMPERATURE,
        KEY_INITIAL: 20,
        KEY_MAX_TEMP: THERMO_MAX_TARGET,
        KEY_MIN_TEMP: THERMO_MIN_TARGET,
        KEY_MODE_COMMAND_TOPIC: "~" + TOPIC_MODE_COMMAND,
        KEY_MODE_STATE_TOPIC: "~" + TOPIC_MODE_STATE,
        KEY_SEND_IF_OFF: True,
        KEY_TEMPERATURE_COMMAND_TOPIC: "~" + TOPIC_TEMPERATURE_COMMAND,
        KEY_TEMPERATURE_STATE_TOPIC: "~" + TOPIC_STATE,
        KEY_TEMPERATURE_UNIT: "C",
        KEY_MODE_STATE_TEMPLATE: TPL_MODE_STATE
        }
    m5mqtt.publish(topic, str(json.dumps(payload)))

    # Register Heater for manual control with Home Assistant
    topic = "%sswitch/core2/core2-heater/config" % DEFAULT_DISC_PREFIX
    payload = {
        KEY_NAME: "Core2 Heater",
        KEY_PAYLOAD_AVAILABLE: "on",
        KEY_PAYLOAD_NOT_AVAILABLE: "off",
        KEY_UNIQUE_ID: "122349",
        KEY_DEVICE: {
            KEY_IDENTIFIERS: ["12234"],
            KEY_NAME: ATTR_NAME,
            KEY_MODEL: ATTR_MODEL,
            KEY_MANUFACTURER: ATTR_MANUFACTURER
        },
        "~": DEFAULT_TOPIC_SWITCH_PREFIX,
        KEY_PAYLOAD_OFF: RELAY_HEAT_PAYLOAD_OFF,
        KEY_PAYLOAD_ON: RELAY_HEAT_PAYLOAD_ON,
        KEY_AVAILABILITY_TOPIC: "~" + TOPIC_HEATER_STATUS,
        KEY_COMMAND_TOPIC: "~" + TOPIC_HEATER_COMMAND,
        KEY_STATE_TOPIC: RELAY_HEAT_TOPIC,
        KEY_ICON: "mdi:radiator"
        }
    m5mqtt.publish(topic, str(json.dumps(payload)))    
        
    # Register AC for manual control with Home Assistant
    topic = "%sswitch/core2/core2-ac/config" % DEFAULT_DISC_PREFIX
    payload = {
        KEY_NAME: "Core2 AC",
        KEY_PAYLOAD_AVAILABLE: "on",
        KEY_PAYLOAD_NOT_AVAILABLE: "off",
        KEY_UNIQUE_ID: "122350",
        KEY_DEVICE: {
            KEY_IDENTIFIERS: ["12234"],
            KEY_NAME: ATTR_NAME,
            KEY_MODEL: ATTR_MODEL,
            KEY_MANUFACTURER: ATTR_MANUFACTURER
        },
        "~": DEFAULT_TOPIC_SWITCH_PREFIX,
        KEY_PAYLOAD_OFF: RELAY_COOL_PAYLOAD_OFF,
        KEY_PAYLOAD_ON: RELAY_COOL_PAYLOAD_ON,
        KEY_AVAILABILITY_TOPIC: "~" + TOPIC_AC_STATUS,
        KEY_COMMAND_TOPIC: "~" + TOPIC_AC_COMMAND,
        KEY_STATE_TOPIC: RELAY_COOL_TOPIC,
        KEY_ICON: "mdi:snowflake"
        }
    m5mqtt.publish(topic, str(json.dumps(payload)))

def mqtt_initialization():
    # Send Availability notices to Home Assistant
    m5mqtt.publish(DEFAULT_TOPIC_SENSOR_PREFIX + TOPIC_STATUS, "on")
    m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_STATUS, "on")
    m5mqtt.publish(DEFAULT_TOPIC_SWITCH_PREFIX + TOPIC_HEATER_STATUS, "on")
    m5mqtt.publish(DEFAULT_TOPIC_SWITCH_PREFIX + TOPIC_AC_STATUS, "on")
    
    # Send initial state information to Home Assistant
    update_mqtt_state_topics()
    m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_ACTION, "idle") 
    m5mqtt.publish(RELAY_HEAT_TOPIC, RELAY_HEAT_PAYLOAD_OFF)
    m5mqtt.publish(RELAY_COOL_TOPIC, RELAY_COOL_PAYLOAD_OFF)
    
def thermostat_init():
    global action, actual_temp, blink, change_ignored, cycle, delay, ticks, thermo_state, fan_state, cooling_state, heating_state, target_temp, manual_command
    action = 0
    actual_temp = env20.temperature
    blink = 0
    change_ignored = 0
    cycle = 0
    delay = 0      # initial delay of 10s so that user can select the right mode without appliances suddenly turning on
    slider_target.set_range(THERMO_MIN_TARGET, THERMO_MAX_TARGET)
    slider_target.set_value(20)
    thermo_state = THERMO_MODES[0]
    target_temp = slider_target.get_value()
    ticks = 0
    
    # initial state of thermostat is OFF and all appliances are OFF
    fan_state = 0
    cooling_state = 0
    heating_state = 0
    manual_command = 0

# update display everytime there is a change (due to incoming HA info, screen interaction, or sensor data changes)
def update_display():
    lcd.clear()
    lbl_mode.set_text(thermo_state)
    lbl_mode.set_align(ALIGN_CENTER, 0, DISP_LBL_MODE_OFFSET)
    target_temp_display = round(target_temp if DISP_TEMPERATURE == "C" else target_temp * 9 / 5 + 32)
    actual_temp_display = actual_temp if DISP_TEMPERATURE == "C" else actual_temp * 9 / 5 + 32
    
    # If mode is manual
    if thermo_state == THERMO_MODES[2]:    
        img_BtnA.set_hidden(False)
        img_BtnB.set_hidden(False)
        img_BtnC.set_hidden(False)
        slider_target.set_hidden(True)
        lbl_target.set_text("")
        lbl_target.set_text_color(0xffffff)
        lbl_target.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
        if heating_state ==1:
            lbl_action.set_text('HEATING')
            lbl_action.set_text_color(DISP_COLOR_HEAT)
            lbl_action.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
            lbl_action.set_text_color(DISP_COLOR_HEAT)
            if change_ignored == 1:
                timerSch.run("blink_now", 305, 0x00)
            else:
                timerSch.stop("blink_now")
                lbl_target.set_text_color(DISP_COLOR_HEAT)
        elif cooling_state ==1:
            lbl_action.set_text('COOLING')
            lbl_action.set_text_color(DISP_COLOR_COOL)
            lbl_action.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
            lbl_target.set_text_color(DISP_COLOR_COOL)
            if change_ignored == 1:
                timerSch.run("blink_now", 305, 0x00)
            else:
                timerSch.stop("blink_now")
                lbl_target.set_text_color(DISP_COLOR_COOL)    
        elif fan_state ==1:
            lbl_action.set_text('FAN')
            lbl_action.set_text_color(0xffffff)
            lbl_action.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
            lbl_target.set_text_color(0xffffff)
            if change_ignored == 1:
                timerSch.run("blink_now", 305, 0x00)
            else:
                timerSch.stop("blink_now")
                lbl_target.set_text_color(0xffffff)
        else:
            lbl_action.set_text('IDLE')
            lbl_action.set_text_color(0xffffff)
            lbl_action.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
            if change_ignored == 1:
                timerSch.run("blink_now", 305, 0x00)
            else:
                timerSch.stop("blink_now")
                lbl_target.set_text_color(0xffffff)            
    else:
        img_BtnA.set_hidden(True)
        img_BtnB.set_hidden(True)
        img_BtnC.set_hidden(True)
        
    # If mode is off
    if thermo_state == THERMO_MODES[0] and change_ignored == 0:
        lcd.font(lcd.FONT_DejaVu40)
        lbl_action.set_text('')
        lbl_target.set_text("---")
        lbl_target.set_text_color(0xffffff)
        lbl_target.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
        
    # If cooling is on
    elif cooling_state == 1 and thermo_state != THERMO_MODES[2]:
        lbl_action.set_text('COOLING')
        lbl_action.set_text_color(DISP_COLOR_COOL)
        lbl_action.set_align(ALIGN_CENTER, 0, DISP_LBL_ACTION_OFFSET)
        lbl_target.set_text(str(target_temp_display))
        lbl_target.set_text_color(DISP_COLOR_COOL)
        lbl_target.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
        slider_target.set_hidden(False)
        if change_ignored == 1:
            timerSch.run("blink_now", 305, 0x00)
        else:
            timerSch.stop("blink_now")
            lbl_target.set_text_color(DISP_COLOR_COOL)
        
    # if heating is on
    elif heating_state == 1 and thermo_state != THERMO_MODES[2]:
        lbl_action.set_text('HEATING')
        lbl_action.set_text_color(DISP_COLOR_HEAT)
        lbl_action.set_align(ALIGN_CENTER, 0, DISP_LBL_ACTION_OFFSET)
        lbl_target.set_text(str(target_temp_display))
        lbl_target.set_text_color(DISP_COLOR_HEAT)
        lbl_target.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
        slider_target.set_hidden(False)
        if change_ignored == 1:
            timerSch.run("blink_now", 305, 0x00)
        else:
            timerSch.stop("blink_now")
            lbl_target.set_text_color(DISP_COLOR_HEAT)

    # if fan is on
    elif fan_state == 1 and thermo_state != THERMO_MODES[2]:
        lbl_action.set_text('FAN')
        lbl_action.set_text_color(0xffffff)
        lbl_action.set_align(ALIGN_CENTER, 0, DISP_LBL_ACTION_OFFSET)
        lbl_target.set_text(str(target_temp_display))
        lbl_target.set_text_color(0xffffff)
        lbl_target.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
        slider_target.set_hidden(False)
        if change_ignored == 1:
            timerSch.run("blink_now", 305, 0x00)
        else:
            timerSch.stop("blink_now")
            lbl_target.set_text_color(0xffffff)
            
   # if none of the above conditions are true (ie. thermostat is on, but idle)   
    elif thermo_state != THERMO_MODES[2]:
        lbl_action.set_text('IDLE')
        lbl_action.set_text_color(0xffffff)
        lbl_action.set_align(ALIGN_CENTER, 0, DISP_LBL_ACTION_OFFSET)
        lbl_target.set_text(str(target_temp_display))
        lbl_target.set_text_color(0xffffff)
        lbl_target.set_align(ALIGN_CENTER, 0, DISP_LBL_TARGET_OFFSET)
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
            round(actual_temp_display),
            int(DISP_R1 * math.sin(((actual_temp * 8 + 200) % 360 +4) / 180 * math.pi) + DISP_XCOORD),
            int(DISP_YCOORD - DISP_R1 * math.cos(((actual_temp * 8 +200) % 360 +4) / 180 * math.pi)),
            0xffffff)
    else:
        lcd.print(
            round(actual_temp_display),
            int(DISP_R1 * math.sin(((actual_temp * 8 + 200) % 360 -20) / 180 * math.pi) + DISP_XCOORD),
            int(DISP_YCOORD - DISP_R1 * math.cos(((actual_temp * 8 +200) % 360 -20) / 180 * math.pi)),
            0xffffff)

# This is where the key decisions happen
# -- First we handle the 'manual' use case.
# -- Then we handle all the use cases wher the thermostat is on (auto/heat/cool/fan)
# -- if thermostat mode is 'off', all devices are turned off.

def thermostat_decision_logic():
    global actual_temp, target_temp, manual_command
    actual_temp = env20.temperature
    target_temp = slider_target.get_value()
    
    if thermo_state == THERMO_MODES[2]: 
        if manual_command == "heating on" and heating_state == 0:
            change_to("heating on")
        elif manual_command == "heating off" and heating_state == 1:
            change_to("heating off")
        elif manual_command == "cooling on" and cooling_state == 0:
            change_to("cooling on")
        elif manual_command == "cooling off" and cooling_state == 1:
            change_to("cooling off")
        elif manual_command == "fan on" and fan_state == 0:
            change_to("fan on")
        elif manual_command == "fan off" and fan_state == 1:
            change_to("fan off")
        else:
            timerSch.stop("blink_now")
            update_display()
        return
    
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
         thermo_state in [THERMO_MODES[index] for index in [0,4,5]]) and        
         heating_state == 1):
        # thermostat needs to turn off heating
        change_to("heating off")
    elif (
        (actual_temp <= target_temp or
         thermo_state in [THERMO_MODES[index] for index in [0,3,5]]) and
         cooling_state == 1):
        # thermostat needs to turn off cooling
        change_to ("cooling off")
    elif (
        (actual_temp <= target_temp or
         thermo_state in [THERMO_MODES[index] for index in [0,3,4]]) and
         fan_state == 1):
        # thermostat needs to turn off fan
        change_to ("fan off")
    else:
        # no action
        timerSch.stop("blink_now")
        update_display()

# Here's where the appliances are turned on/off using MQTT messages.
# Here's where we also check for minimum cycle time and ignore change requests
#  if the minimum cycle time hasn't been reached.
def change_to (action):
    global change_ignored, heating_state, cooling_state, fan_state, m5mqtt, delay
    if delay == 0 or THERMO_MIN_CYCLE == 0:
        change_ignored = 0
        if action == "heating on":
            m5mqtt.publish(RELAY_HEAT_TOPIC, RELAY_HEAT_PAYLOAD_ON)
            m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_ACTION, "heating") 
            heating_state = 1
            if cooling_state == 1:
                m5mqtt.publish(RELAY_COOL_TOPIC, RELAY_COOL_PAYLOAD_OFF)
                cooling_state = 0
            if fan_state == 1:
                m5mqtt.publish(RELAY_FAN_TOPIC, RELAY_FAN_PAYLOAD_OFF)
                fan_state = 0
        elif action == "cooling on":
            m5mqtt.publish(RELAY_COOL_TOPIC, RELAY_COOL_PAYLOAD_ON)
            m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_ACTION, "cooling") 
            cooling_state = 1
            if heating_state == 1:
                m5mqtt.publish(RELAY_HEAT_TOPIC, RELAY_HEAT_PAYLOAD_OFF)
                heating_state = 0
            if fan_state == 1:
                m5mqtt.publish(RELAY_FAN_TOPIC, RELAY_FAN_PAYLOAD_OFF)
                fan_state = 0
        elif action == "fan on":
            m5mqtt.publish(RELAY_FAN_TOPIC, RELAY_FAN_PAYLOAD_ON)
            m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_ACTION, "fan") 
            fan_state = 1
            if heating_state == 1:
                m5mqtt.publish(RELAY_HEAT_TOPIC, RELAY_HEAT_PAYLOAD_OFF)
                heating_state = 0
            if cooling_state == 1:
                m5mqtt.publish(RELAY_COOL_TOPIC, RELAY_COOL_PAYLOAD_OFF)
                cooling_state = 0           
        elif action == "heating off":
            m5mqtt.publish(RELAY_HEAT_TOPIC, RELAY_HEAT_PAYLOAD_OFF)
            m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_ACTION, "idle") 
            heating_state = 0
        elif action == "cooling off":
            m5mqtt.publish(RELAY_COOL_TOPIC, RELAY_COOL_PAYLOAD_OFF)
            m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_ACTION, "idle") 
            cooling_state = 0
        elif action == "fan off":
            m5mqtt.publish(RELAY_FAN_TOPIC, RELAY_FAN_PAYLOAD_OFF)
            m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_ACTION, "idle") 
            fan_state = 0           
        delay = THERMO_MIN_CYCLE
        timerSch.run("delayed_start", 1000, 0x00)
        timerSch.stop("blink_now")
        update_display()
    else:
        change_ignored = 1
        update_display()


def update_mqtt_state_topics():
    #update state of ENV sensors
    payload = {
        "temperature": env20.temperature,
        "humidity": env20.humidity,
        "pressure": env20.pressure
        }
    m5mqtt.publish(DEFAULT_TOPIC_SENSOR_PREFIX + TOPIC_STATE,str(json.dumps(payload)))
    
    #update state of thermostat target temperature
    m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_STATE, str(target_temp))
    
    #update state of thermostat mode
    m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_MODE_STATE, str(thermo_state))    
        
@timerSch.event("delayed_start")
def tdelayed_start():
    global delay
    delay -= 1
    if delay == 0:
        timerSch.stop("delayed_start")
        thermostat_decision_logic()

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
    m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_STATE, str(target_temp))
    thermostat_decision_logic()

slider_target.changed(slider_target_changed)

def rcv_target_temp (topic_data):
    global target_temp
    slider_target.set_value(round(float(topic_data)))
    thermostat_decision_logic()

def rcv_thermo_state (topic_data):
    global thermo_state
    thermo_state = str(topic_data) if str(topic_data) != "fan_only" else "fan"
    m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_MODE_STATE, str(thermo_state)) 
    thermostat_decision_logic()

def rcv_heater_status (topic_data):
    global thermo_state, manual_command
    thermo_state = THERMO_MODES[2]
    manual_command = "heating on" if str(topic_data) == RELAY_HEAT_PAYLOAD_ON else "heating off"
    thermostat_decision_logic()

def rcv_ac_status (topic_data):
    global thermo_state, manual_command
    thermo_state = THERMO_MODES[2]
    manual_command = "cooling on" if str(topic_data) == RELAY_COOL_PAYLOAD_ON else "cooling off"
    thermostat_decision_logic()
    
def rcv_master_off (topic_data):
    global thermo_state
    thermo_state = THERMO_MODES[0]
    thermostat_decision_logic()

def rcv_discovery (topic_data):
    mqtt_registration()
    m5mqtt.publish(DEFAULT_TOPIC_SENSOR_PREFIX + TOPIC_STATUS, "on")
    m5mqtt.publish(DEFAULT_TOPIC_THERMOSTAT_PREFIX + TOPIC_STATUS, "on")
    m5mqtt.publish(DEFAULT_TOPIC_SWITCH_PREFIX + TOPIC_HEATER_STATUS, "on")
    m5mqtt.publish(DEFAULT_TOPIC_SWITCH_PREFIX + TOPIC_AC_STATUS, "on")
    thermostat_decision_logic()
    
thermostat_init()
comms_init()
thermostat_decision_logic()
timerSch.run("main_loop", 999, 0x00)

while True:
    
# We ignore button presses unless the Thermostat is in manual mode
    if btnA.wasPressed() and thermo_state == THERMO_MODES[2]:
        if heating_state == 0:
            manual_command = "heating on"
        elif heating_state == 1:
            manual_command = "heating off"
        thermostat_decision_logic()
        
    if btnB.wasPressed() and thermo_state == THERMO_MODES[2]:
        if cooling_state == 0:
            manual_command = "cooling on"
        elif cooling_state == 1:
            manual_command = "cooling off"
        thermostat_decision_logic()
        
    if btnC.wasPressed() and thermo_state == THERMO_MODES[2]:
        if fan_state == 0:
            manual_command = "fan on"
        elif fan_state == 1:
            manual_command = "fan off"
        thermostat_decision_logic()
            
    if ticks == THERMO_UPDATE_FREQUENCY:
        thermostat_decision_logic()
        update_mqtt_state_topics()
        ticks = 0
    wait_ms(2)
    
