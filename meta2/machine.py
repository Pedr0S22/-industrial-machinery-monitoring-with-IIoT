import paho.mqtt.client as mqtt
import json
import time
import random
import sys
from datetime import datetime

class Machine:

    def __init__(self, machine_code, update_time):
        self.machine_code = machine_code
        self.update_time = update_time
        self.specs = MACHINE_SPECS[machine_code]
        self.machine_id = MACHINE_SPECS[machine_code]["machine_id"]
        
        # Initial sensor values (within normal ranges)
        self.rpm = 1100
        self.coolant_temp = 90.0 if self.specs["temp_unit"] == "°C" else 194.0
        self.oil_pressure = 3.0 if self.specs["oil_unit"] == "bar" else 43.5
        self.battery_potential = 13.0  if self.specs["batt_unit"] == "V" else 13000.0
        self.consumption = 25.0  if self.specs["consumption_unit"] == "l/h" else 6.6
        
        self.is_operational = True
        self.is_shutting_down = False
        self.waiting_for_adjustment = False

        self.rssi = -85
        self.snr = -15.0
        self.rssi_channel = -85

    def _clamp_value(self, value, min_val, max_val):
        return max(min_val, min(value, max_val))

    def update_sensors(self):
        """Update sensor values according to project specifications"""
        if self.is_shutting_down:
            print("Restarting Machine...")
            # Gradually reduce all values to 0 for shutdown sequence
            self.rpm = 0
            self.coolant_temp = max(0.0, self.coolant_temp * 0.4)
            self.oil_pressure = max(0, self.oil_pressure  - (2.0 if self.specs["oil_unit"] == "bar" else 29.0))
            self.consumption = 0
            self.battery_potential = 0
            
            # Check restart conditions
            if self.rpm == 0 and self.oil_pressure == 0 and self.consumption == 0:
                if ((self.specs["temp_unit"] == "°C" and self.coolant_temp < 20) or 
                    (self.specs["temp_unit"] == "°F" and self.coolant_temp < 68)):
                    self._restart_machine()
                    self.waiting_for_adjustment = False
            return

        # Normal operation updates

        # RPM
        self.rpm = self._clamp_value(
            self.rpm + random.uniform(-50, 200),800, 3000)
        
        # TEMPERATURE
        if self.specs["temp_unit"] == "°C":
            self.coolant_temp = self._clamp_value(self.coolant_temp + random.uniform(-0.3, 1.0),70.0, 130.0)
        else:
            self.coolant_temp = self._clamp_value(self.coolant_temp + random.uniform(-0.54, 1.8),158.0, 266.0 )
        
        # OIL
        if self.specs["oil_unit"] == "bar":
            self.oil_pressure = self._clamp_value(self.oil_pressure + random.uniform(-0.1, 0.5),1.5, 8.0)
        else: 
            self.oil_pressure = self._clamp_value(self.oil_pressure + random.uniform(-1.45, 7.25),21.75, 116.0)
            
        # BATTERY
        if self.specs["batt_unit"] == "V":
            self.battery_potential = self._clamp_value(self.battery_potential + random.uniform(-0.1, 0.2),10.0, 14.0)
        else:
            self.battery_potential = self._clamp_value(self.battery_potential + random.uniform(-100,200),10000.0,14000.0)
        
        # CONSUMPTION
        if self.specs["consumption_unit"] == "l/h":
            self.consumption = self._clamp_value(self.consumption + random.uniform(-1, 1),1.0, 50.0)
        else:
            self.consumption = self._clamp_value(self.consumption + random.uniform(-0.26, 0.26), 0.26, 13.21)

        # COMMUNICATIONS

        self.rssi = self._clamp_value(self.rssi + random.uniform(-3,3),-120,-50)

        self.snr = self._clamp_value(self.snr + random.uniform(-0.5,0.5),-20,10)

        self.rssi_channel = self._clamp_value(self.rssi_channel + random.uniform(-3,3),-120,-50)

    def _restart_machine(self):
        """Reset machine to normal operation"""
        self.rpm = 1100
        self.coolant_temp = 90.0 if self.specs["temp_unit"] == "°C" else 194.0
        self.oil_pressure = 3.0 if self.specs["oil_unit"] == "bar" else 43.5
        self.battery_potential = 13.0  if self.specs["batt_unit"] == "V" else 13000.0
        self.consumption = 25.0  if self.specs["consumption_unit"] == "l/h" else 6.6

        self.rssi = -85
        self.snr = -15.0
        self.rssi_channel = -85

        self.is_operational = True
        self.is_shutting_down = False
        print(f"[{datetime.now()}] Machine {self.machine_code} ({self.machine_id}) restarted")

    def process_control_command(self, command):
        """Process incoming MQTT control commands"""

        # Example command: "0x01 0x01 0x01 0xFA" (reduce RPM by 6)
        parts = command.split()

        if len(parts) != 4:
            print("[ERROR] process_control_command: !=4 ")
            return
        
        # Byte 1: Message Type (0x01 = Control)        
        msg_type = parts[0]

        # Byte 2: Action Type (0x01 = Modify Parameter)
        msg_mod = parts[1]

        # Byte 3: Parameter to modify
        param = parts[2]

        # Byte 4: Adjustment value (signed byte)
        adjustment = int(parts[3], 16)
        if adjustment > 127:  # Handle negative values
                adjustment -= 256

        if msg_type != "0x01":
            print("[ERROR] process_control_command: No 0x01 = Control")
            return
            
        if msg_mod != "0x01":
            print("[ERROR] process_control_command: No 0x01 = modification")
            return
                
        if param == "0x01":  # RPM
            self.rpm = self.rpm + adjustment
            print(f"[{datetime.now()}] Adjusted RPM by {adjustment} (New: {self.rpm})")
        
        elif param == "0x02": # Fuel
            self.consumption = self.consumption + adjustment
            print(f"[{datetime.now()}] Adjusted consumption by {adjustment} (New: {self.consumption})")

        elif param == "0x03": # Temperature
            self.coolant_temp = self.coolant_temp + adjustment
            print(f"[{datetime.now()}] Adjusted coolant_temp by {adjustment} (New: {self.coolant_temp})")

        elif param == "0x04": # Oil
            self.oil_pressure = self.oil_pressure + adjustment
            print(f"[{datetime.now()}] Adjusted oil_pressure by {adjustment} (New: {self.oil_pressure})")

        elif param == "0x05": # battery
            self.battery_potential = self.battery_potential + adjustment
            print(f"[{datetime.now()}] Adjusted battery_potential by {adjustment} (New: {self.battery_potential})")

        else:
            print(f"[ERROR] bad request adjustment: No such param")
                
    def process_alert_command(self, command):
        """Process incoming MQTT alert commands"""
        # Example command: "0x02 0x01 0x01" (critical alert - shutdown)
        parts = command.split()
        if len(parts) != 3:
            print("[ERROR] process_alert_command ")
            return
            
        if parts[0] == "0x02" and parts[1] == "0x01":
            print(f"[{datetime.now()}] CRITICAL ALERT: Shutting down machine!")
            self.is_shutting_down = True
            self.waiting_for_adjustment = True

    def generate_payload(self):
        """Generate TTN-compatible JSON payload"""
        return {
            "end_device_ids": {
                "machine_id": self.machine_id,
                "application_id": "SRSA2025:industrial-monitoring",
                "dev_eui": "".join(random.choices("0123456789ABCDEF", k=16)),
                "join_eui": "0000000000000000",
                "dev_addr": "".join(random.choices("0123456789ABCDEF", k=8))
            },
            "received_at": datetime.now().isoformat(),
            "uplink_message": {
                "f_port": 1,
                "f_cnt": 1234,
                "frm_payload": "BASE64_SIMULATED_PAYLOAD",
                "decoded_payload": {
                    "rpm": round(self.rpm,2),
                    "coolant_temperature": round(self.coolant_temp,2),
                    "oil_pressure": round(self.oil_pressure,2),
                    "battery_potential": round(self.battery_potential,2),
                    "consumption": round(self.consumption,2),
                    "machine_type": self.machine_code
                },
                "rx_metadata": [{
                    "gateway_id": "dei-gateway-1",
                    "rssi": round(self.rssi,2),
                    "snr": round(self.snr,2),
                    "channel_rssi": round(self.rssi_channel,2),
                    "uplink_token": "SIMULATED_TOKEN"
                }],
                "settings": {
                    "data_rate": {
                        "modulation": "LORA",
                        "bandwidth": 125000,
                        "spreading_factor": 7
                    },
                    "frequency": "868300000",
                    "timestamp": int(time.time())
                },
                "consumed_airtime": f"{random.uniform(0.05, 0.07):.6f}s"
            }
        }

# ===== MQTT CALLBACKS =====
def on_connect(client, userdata, flags, rc):
    print(f"[{datetime.now()}] Connected to MQTT Broker (rc={rc})")
    # Subscribe to control topics
    control_topic = f"v3/{group_id}@ttn/devices/{machine_id}/down/push_actuator"
    alert_topic = f"v3/{group_id}@ttn/devices/{machine_id}/down/push_alert"
    client.subscribe(control_topic)
    client.subscribe(alert_topic)
    print(f"[{datetime.now()}] Subscribed to: {control_topic}")
    print(f"[{datetime.now()}] Subscribed to: {alert_topic}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        if "downlinks" in payload and len(payload["downlinks"]) > 0:
            command = payload["downlinks"][0]["frm_payload"]
            
            if "push_alert" in msg.topic:
                machine.process_alert_command(command)
            elif "push_actuator" in msg.topic:
                machine.process_control_command(command)
    except Exception as e:
        print(f"[{datetime.now()}] Error processing message: {e}")

# ===== MAIN EXECUTION =====
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 machine.py <GroupID> <UPDATE_TIME_SECONDS> <MACHINE_CODE>")
        print("Example: python3 machine.py 19 5 A23X")
        sys.exit(1)

    group_id = sys.argv[1]
    update_time = int(sys.argv[2])
    machine_code = sys.argv[3]

    # ===== MQTT CONFIG =====
    MQTT_BROKER_IP = "10.6.1.9"
    MQTT_PORT = 1883

    # ===== MACHINE CONFIGURATION =====
    machine_path = "config/all_machines.json"

    try:
        with open(machine_path, "r", encoding="utf-8") as f:
            MACHINE_SPECS =  json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
            print("File not found/invalid")
            MACHINE_SPECS = {}

    if machine_code not in MACHINE_SPECS.keys():
        print(f"Invalid machine code. Choose from: {list(MACHINE_SPECS.keys())}")
        sys.exit(1)

    machine_id = MACHINE_SPECS[machine_code]["machine_id"]

    machine = Machine(machine_code, update_time)

    # MQTT Client Setup
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER_IP, MQTT_PORT, 60)
        client.loop_start()

        print(f"[{datetime.now()}] Started {machine_code} ({machine_id}) simulator (Update every {update_time}s)")
        while True:
            if machine.is_operational:
                machine.update_sensors()
                payload = machine.generate_payload()
                    
                # Publish to MQTT
                topic = f"v3/{group_id}@ttn/devices/{machine_id}/up"
                client.publish(topic, json.dumps(payload))
                print(f"[{datetime.now()}] Published update to {topic}")
                
            time.sleep(update_time)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        client.disconnect()