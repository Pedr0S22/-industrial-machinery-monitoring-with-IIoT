from gpiozero import LED, Buzzer
import paho.mqtt.client as mqtt_publish
import time

# ========== Wait function =========== #

def wait(seconds):
    start_time = time.time()
    while time.time() - start_time < seconds:
        pass

# ======== MQTT Configuration ======== #
BROKER = "10.6.1.9"
PORT = 1883
GROUP_ID = "19"

TOPIC_COOLANT = f"machine_{GROUP_ID}/coolant"
TOPIC_PRESSURE = f"machine_{GROUP_ID}/pressure"
TOPIC_RPM = f"machine_{GROUP_ID}/rpm"
TOPIC_CONTROLLER = f"machine_{GROUP_ID}/controller"
SENSOR_TOPICS = [
    f"machine_{GROUP_ID}/status/coolant",
    f"machine_{GROUP_ID}/status/pressure",
    f"machine_{GROUP_ID}/status/rpm"
]

# ======= GPIO Pin Assignments ======= #
LED_PIN_RED = 17
LED_PIN_YELLOW = 27
LED_PIN_GREEN = 22
BUZZER_PIN = 19

# Setup GPIO devices
led_red = LED(LED_PIN_RED)
led_yellow = LED(LED_PIN_YELLOW)
led_green = LED(LED_PIN_GREEN)
buzzer = Buzzer(BUZZER_PIN)

# ========== State Variables ========== #
temp = None
pressure = None
rpm = None
alarm_enabled = None
sensor_status = {"coolant": None, "pressure": None, "rpm": None}
machine_status = "offline"
mqtt_connected = False

# ========== MQTT Callbacks ========== #
def on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    if rc == 0:
        print("Connected to MQTT Broker")
        client.subscribe([(TOPIC_COOLANT, 0), (TOPIC_PRESSURE, 0), (TOPIC_RPM, 0), (TOPIC_CONTROLLER, 0)])
        for sensor in SENSOR_TOPICS:
            client.subscribe([(sensor, 0)])
        mqtt_connected = True
    else:
        print(f"Failed to connect, return code {rc}")

def on_disconnect(client, userdata, rc, properties=None, packet_from_broker=False):
    print(f"Disconnected from broker with return code {rc}")

def on_message(client, userdata, msg):
    global temp, pressure, rpm, alarm_enabled, machine_status, sensor_status

    try:
        if msg.topic == TOPIC_CONTROLLER:
            control = msg.payload.decode().strip().upper()
            alarm_enabled = (control == "ON")
            print(f"{'Activated' if alarm_enabled else 'Deactivated'} by controller")
            return

        if msg.topic == TOPIC_COOLANT:
            temp = float(msg.payload.decode())
        elif msg.topic == TOPIC_PRESSURE:
            pressure = float(msg.payload.decode())
        elif msg.topic == TOPIC_RPM:
            rpm = float(msg.payload.decode())
        
        if msg.topic in SENSOR_TOPICS:
            sensor_name = msg.topic.split('/')[-1]  # coolant, pressure, rpm
            sensor_status[sensor_name] = msg.payload.decode().strip()

        if 'offline' in sensor_status.values():
            machine_status = 'offline'
        else:
            machine_status = 'online'

    except Exception as e:
        print(f"Message error: {e}")


# ========== MQTT Setup ========== #
client = mqtt_publish.Client(callback_api_version=mqtt_publish.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

# ========== Main Loop ========== #


try:
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    while not mqtt_connected:
        print("Waiting for MQTT connection...")
        time.sleep(2.5)

    while True:

        led_green.off()
        led_yellow.off()
        led_red.off()
        buzzer.off()

        if not alarm_enabled:
            print("The Alarm is offline")
            time.sleep(5)
            continue

        # If the machine is offline, trigger disconnection mode with blinking
        if machine_status == "offline":
            print("Machine is offline, entering disconnection mode...")
            buzzer.on()
            led_red.blink(on_time=0.5, off_time=0.5, n=3)
            continue

        print(f"Temp: {temp} °C | Pressure: {pressure} bar | RPM: {rpm}")

        # ---------- Status Evaluation ---------- #

        problem = (temp < 90 or temp > 105) or (pressure < 1 or pressure > 5)
        danger = (temp < 90 or temp > 105) and (pressure < 1 or pressure > 5)
        rpm_state = (rpm > 2500)

        # ---------- Output Control ---------- #

        if (danger or problem) and rpm_state:
            if danger:
                print("The Sensors are in Danger and RPM mode")
                led_red.on()
                buzzer.on()
            else:
                print("The Sensors are in Problem and RPM mode")
                led_yellow.on()
                buzzer.on()

        elif danger:
            print("The Sensors are in Danger mode")
            led_red.on()

        elif problem:
            print("The Sensors are in Problem mode")
            led_yellow.on()

        elif rpm_state:
            print("The Sensors are in RPM mode")
            buzzer.on()

        else:
            print("The Sensors are healthy")
            led_green.on()
        
        wait(2)


except KeyboardInterrupt:
    print("Exiting alarm console...")

except Exception as e:
    print(f"Error: {e}")

finally:
    led_green.off()
    led_yellow.off()
    led_red.off()
    buzzer.off()
    client.disconnect()
    print("Cleaned up GPIO and disconnected from MQTT broker.")
