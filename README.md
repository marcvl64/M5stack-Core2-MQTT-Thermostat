# M5stack-Core2-MQTT-Thermostat
## Smart thermostat, built for M5Stack Core2.

## Key features:
 - all thermostat logic is built into this Python script and runs on Core2
 - thermostat supports auto, manual, fan, heat, cool modes
 - minimum cycle duration can be set (THERMO_MIN_CYCLE)
 - swing mode is enabled and can be customized (THERMO_COLD_TOLERANCE and THERMO_HEAT_TOLERANCE)

## Configuration considerations:
 - Relies on separate config.py file to store secrets (WiFI and MQTT connection details)
 - Gets actual temperature through ENVII sensor, connected to the Core2. But you could easily set up another
   external temperature sensor and communicate values to the Core2 through MQTT
 - Uses MQTT to communicate with relays that turn on/off furnace, fan, and AC. You need to configure the right
   topics and payloads to establish that communication (variables starting with RELAY_)
 - Graphics files for heat/cool/fan need to be stored in the /res directory

## Home Assistant integration:
 - Integrates with Home Assistant through MQTT (you need MQTT enabled on the HA side)
 - Supports MQTT auto-discovery. No configuration needed on the HA side.
 - Will create 'Core2 Thermostat' device with following entities:
    - 3 sensors for temperature, humidity, and pressure (if using the ENVII)
    - 1 thermostat entity
 - The thermostat entity allows you to control target temperature and thermostat mode through HA. Any changes will be reflected on the Core2.
 - Manual mode is not supported by the HA thermostat entity. State of the devices (heating/cooling/fan on-off will be accurately reflected
   in home assistant, but the thermostat entity mode will be 'off' and you can't manually change the state of the devices from HA.

## Usage notes:
 - Upon start the thermostat will be OFF. Tapping the OFF label will run the thermostat through the various modes: OFF - AUTO - MAN - HEAT - COOL - FAN
 - When in manual mode, use the A/B/C buttons to turn on/off heat pump, AC, Fan. Only 1 device can be on at a given time.
 - When min cycle duration requirement isn't met, the Core2 display will blink until it is able to implement the change
 - Blinking is not supported on the Lovelace thermostat card. The HA dashboard will not change until the min cycle duration requirement is met.
 - Currently, the Core2 displays temperature in Celsius. Home Assistant will display temperature depending on your HA preferences (metric vs imperial) 

