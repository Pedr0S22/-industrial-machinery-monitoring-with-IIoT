import paho.mqtt.client as mqtt
import socket
import json
import threading
from influxdb_client_3 import InfluxDBClient3, Point
from datetime import datetime

class DataManagerAgent:
    def __init__(self, group_id):
        self.group_id = group_id
        self.mqtt_client = mqtt.Client()
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Initialize InfluxDB client
        self.influx_client = InfluxDBClient3(host=URL,token=TOKEN,database=BUCKET,org=ORG)
        
        # MQTT callbacks
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        
        # Internal communication topics
        self.internal_topic = f"{group_id}/internal/machine_data"
        self.control_topic = f"{group_id}/internal/control_commands"

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to machine data topics
        client.subscribe(f"v3/{self.group_id}@ttn/devices/+/up")
        # Subscribe to control commands from MachineDataManager
        client.subscribe(self.control_topic)
        print(f"Subscribed to topics:\n- v3/{self.group_id}@ttn/devices/+/up\n- {self.control_topic}")


    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"Received data:\n{payload}")
            
            # Route messages based on topic
            if msg.topic == self.control_topic:
                self._process_control_message(payload)
            else:
                self._process_machine_data(payload)
                
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    def _process_machine_data(self, payload):
        """Process incoming machine data"""
        machine_id = payload["end_device_ids"]["machine_id"]
        print(f"Received data from {machine_id}")
        
        # Extract and process sensor data
        sensor_data = payload["uplink_message"]["decoded_payload"]
        comm_data = payload["uplink_message"]["rx_metadata"][0]
        
        # Standardize units
        standardized_data = self._standardize_units(machine_id, sensor_data)
        
        # Store in InfluxDB
        self._store_in_influxdb(machine_id, standardized_data, comm_data)
        
        if sensor_data["rpm"] != 0 or sensor_data["battery_potential"] != 0 or sensor_data["consumption"] != 0:
            # Forward to Machine Data Manager
            self._forward_to_data_manager(machine_id, standardized_data)

    def _process_control_message(self, payload):
        """Process control messages without modification"""

        """RECEIVING DATA OF THIS TYPE"""
        # OBJ = {
        #        "machine_id":"M1",
        #        "modify_param":"RPM",
        #        "adjustment":"-100"
        #        "timestamp: ..."
        #        }

        machine_id = payload["machine_id"]
        param = payload["modify_param"] 
        adjustment = payload["adjustment"]

        # Store raw control message
        try:
            point = Point("machine_control") \
                .tag("machine_id", machine_id) \
                .field("modify_param", param) \
                .field("adjustment", float(adjustment)) \
                .time(datetime.now().isoformat())
            self.influx_client.write([point])
            print(f"Stored control message for {machine_id} in InfluxDB")
        except Exception as e:
            print(f"Failed to write to InfluxDB: {str(e)}")
        
        # Forward encoded command

        param_enc = PARAM_MAP[param][0]  # Always exists

        # Only retrieve units if there's a second item
        units = PARAM_MAP[param][1] if len(PARAM_MAP[param]) > 1 else None

        if units:
            # Destandardize the adjustment
            adjustment = self._destandardize_units(machine_id, adjustment, units)

            adjustment = int(round(adjustment))

        if adjustment < 0:
            hex_adj = hex(0x100 + adjustment)[2:].upper().zfill(2)
        else:
            hex_adj = hex(adjustment)[2:].upper().zfill(2)

        adjustment_enc = f"0x{hex_adj}"

        command = f"0x01 0x01 {param_enc} {adjustment_enc}"

        # send to TTN Server
        downlink = {
            "downlinks": [{
                "frm_payload": command,
                "f_port": 10,
                "priority": "NORMAL"
            }]
        }
        topic = f"v3/{self.group_id}@ttn/devices/{machine_id}/down/push_actuator"
        self.mqtt_client.publish(topic, json.dumps(downlink))

    def _destandardize_units(self, machine_id, value, unit_type):
       
        machine_spec = None
        for specs in MACHINE_SPECS.values():
            if specs["machine_id"] == machine_id:
                machine_spec = specs
                break
        
        if not machine_spec:
            raise ValueError(f"Unknown machine ID: {machine_id}")
        
        # Get the machine's specific unit for this type
        machine_unit = machine_spec[unit_type]
        
        # Conversion logic based on unit type
        if unit_type == "temp_unit":
            if machine_unit == "°F":
                # Convert from standardized °C to °F
                return (value * 9/5) + 32
        
        elif unit_type == "oil_unit":
            if machine_unit == "psi":
                # Convert from standardized bar to psi
                return value / 0.0689476
        
        elif unit_type == "batt_unit":
            if machine_unit == "mV":
                # Convert from standardized V to mV
                return value * 1000
        
        elif unit_type == "consumption_unit":
            if machine_unit == "gal/h":
                # Convert from standardized l/h to gal/h
                return value / 3.78541
        
        # Return original value if no conversion needed
        return value


    def _standardize_units(self, machine_id, sensor_data):
        """Convert all values to standardized units"""
        machine_code = sensor_data["machine_type"]
        standardized = {}
        standardized["machine_type"] = machine_code
        
        # RPM (no conversion needed)
        standardized["rpm"] = sensor_data["rpm"]
        
        # Temperature (convert °F to °C if needed)
        if MACHINE_SPECS[machine_code]["temp_unit"] == "°F":
            standardized["coolant_temp"] = round((sensor_data["coolant_temperature"] - 32) * 5/9,2)
        else:
            standardized["coolant_temp"] = sensor_data["coolant_temperature"]
        
        # Oil pressure (convert psi to bar if needed)
        if MACHINE_SPECS[machine_code]["oil_unit"] == "psi":
            standardized["oil_pressure"] = round(sensor_data["oil_pressure"] * 0.0689476,2)
        else:
            standardized["oil_pressure"] = sensor_data["oil_pressure"]
        
        # Battery (convert mV to V if needed)
        if MACHINE_SPECS[machine_code]["batt_unit"] == "mV":
            standardized["battery_potential"] = round(sensor_data["battery_potential"] / 1000,2)
        else:
            standardized["battery_potential"] = sensor_data["battery_potential"]
        
        # Consumption (convert gal/h to l/h if needed)
        if MACHINE_SPECS[machine_code]["consumption_unit"] == "gal/h":
            standardized["consumption"] = round(sensor_data["consumption"] * 3.78541,2)
        else:
            standardized["consumption"] = sensor_data["consumption"]
        
        return standardized

    def _store_in_influxdb(self, machine_id, standartize_data, comm_data):
        """Store all machine data in a single InfluxDB Point"""
        try:
            # Create a single Point with all data
            point = Point("machine_data") \
                .tag("machine_id", machine_id) \
                .tag("machine_type", standartize_data["machine_type"]) \
                .field("rpm", float(standartize_data["rpm"])) \
                .field("coolant_temp", float(standartize_data["coolant_temp"])) \
                .field("oil_pressure", float(standartize_data["oil_pressure"])) \
                .field("battery_potential", float(standartize_data["battery_potential"])) \
                .field("consumption", float(standartize_data["consumption"])) \
                .field("rssi", float(comm_data["rssi"])) \
                .field("snr", float(comm_data["snr"])) \
                .field("channel_rssi", float(comm_data.get("channel_rssi", comm_data["rssi"]))) \
                .time(datetime.now().isoformat())
            
            # Write the combined data point
            self.influx_client.write(point)
            
            print(f"Stored combined data for {machine_id} in InfluxDB")
        except Exception as e:
            print(f"Error storing in InfluxDB: {e}")

    def _forward_to_data_manager(self, machine_id, sensor_data):
        """Send standardized data to Machine Data Manager"""
        payload = {
            "machine_id": machine_id,
            "timestamp": datetime.now().isoformat(),
            "sensor_data": sensor_data
        }
        
        self.mqtt_client.publish(self.internal_topic, json.dumps(payload))
        print(f"Forwarded data for {machine_id} to Machine Data Manager")

    def _handle_udp_alerts(self):
        """Listen for UDP alerts with socket timeout"""
        self.udp_socket.settimeout(1.0)  # Prevents complete lock
        self.udp_socket.bind((UDP_IP, UDP_PORT))
        print(F"UDP listener started on port {UDP_PORT}")
        
        while True:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                try:
                    alert = json.loads(data.decode())
                    print(f"Alert UDP message: {alert}")
                    self._process_alert(alert)
                except Exception as e:
                    print(f"Error processing UDP alert: {e}")
            except socket.timeout:
                continue  # Normal timeout occurrence

    def _process_alert(self, alert):
        """Process alert messages without modification"""

        """RECEIVING DATA OF THIS TYPE"""
        # OBJ = {
        #        "machine_id":"M1",
        #        "reason":"high number of control alarms"
        #        "timestamp: ..."
        #        "level": "CRITICAL",
        #        }

        machine_id = alert["machine_id"]
        reason = alert["reason"]
        
        # Store raw alert message
        try:
            point = Point("machine_alerts") \
                .tag("machine_id", machine_id) \
                .field("reason", reason) \
                .time(datetime.now().isoformat())
            self.influx_client.write([point])
            print(f"Stored alert message for {machine_id} in InfluxDB")
        except Exception as e:
            print(f"Failed to write to InfluxDB: {str(e)}")
        
        # Forward encoded command

        reason_enc = REASON_MAP[reason]

        command = f"0x02 0x01 {reason_enc}"

        # send to TTN Server
        downlink = {
            "downlinks": [{
                "frm_payload": command,
                "f_port": 10,
                "priority": "NORMAL"
            }]
        }
        topic = f"v3/{self.group_id}@ttn/devices/{machine_id}/down/push_alert"
        self.mqtt_client.publish(topic, json.dumps(downlink))

    def run(self):
        """Start the agent"""
        # Connect to MQTT broker
        self.mqtt_client.connect(MQTT_BROKER_IP, MQTT_PORT)
        
        # Start UDP listener in a separate thread
        udp_thread = threading.Thread(target=self._handle_udp_alerts)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start MQTT loop
        self.mqtt_client.loop_forever()


if __name__ == "__main__":

    # ===== MACHINE CONFIGURATION =====
    machines_path = "config/all_machines.json"

    try:
        with open(machines_path, "r", encoding="utf-8") as f:
            MACHINE_SPECS =  json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
            print("File not found/invalid")
            MACHINE_SPECS = {}

    PARAM_MAP = {
        "rpm": ["0x01"],
        "consumption": ["0x02", "consumption_unit"],
        "coolant_temp": ["0x03", "temp_unit"],
        "oil_pressure": ["0x04", "oil_unit"],
        "battery_potential": ["0x05", "batt_unit"]
    }

    REASON_MAP={
        "high number of control alarms": "0x01",
    }

    # ===== MQTT CONFIG =====
    MQTT_BROKER_IP = "10.6.1.9"
    MQTT_PORT = 1883
    GROUP_ID = "19"

    # ==== UDP COMMUNICATIONS CONFIG ====
    UDP_PORT = 5005
    UDP_IP = "localhost"

    # ===== INFLUXDB CONFIG =====
    URL="https://eu-central-1-1.aws.cloud2.influxdata.com/"
    TOKEN="oJE-YkyhUl4GqsVuysuIQFApneCVJsNkQYNFDLuequfCw_i5_c_J5iFGTNKGVPgZSMCTDq7lM5ph7o-EjeO0tQ=="
    ORG="Coimbra lecd test"
    BUCKET="Project part2"

    agent = DataManagerAgent(GROUP_ID)
    agent.run()