# Industrial Machinery Monitoring with IIoT

This project simulates an Industrial Internet of Things (IIoT) scenario where industrial machinery is monitored in real-time. The system collects sensor data (RPM, oil pressure, coolant temperature, battery potential, and fuel consumption) from different machine models, processes it via MQTT, stores it in an InfluxDB database, and visualizes it on a Grafana dashboard. The goal is to ensure efficient machine management by detecting anomalies, issuing control commands, and triggering alerts when critical conditions appear.

## Run Instructions

You must have python installed, as well as the following packages:

- **Json, Sys:** Utilized for reading and creating Json objects.
- **RPi.GPIO, Gpiozero:** Used for communications with Rasperry Pi Zero and sensors. 
- **Time, Datetime, Collections, Random:** Used for data manipulation. 
- **Pprint:** Used for printing the messages between system on Debugger system.
- **Threading:** Utilized on Alert Manager to deal with control messages from Machine Data Manager.
- **Socket, paho-mqtt:** Used for sending data between systems.
- **Influxdb_client_3:** Utilized for sending the data to an InfluxDB database for further analysis on Grafana.

To run this project you will need to generate your API key (token) on [InfluxDB](https://www.influxdata.com/) and place it on:

```bash
data_manager_agent.py
```

After all configuration being setted up, run by order:

```bash
machine.py
data_manager_agent.py
machine_data_manager.py
alert_machine.py
debugger.py
```

**Note** that you need to change the BROKER IP/PORT, UDP IP/PORT, InfluxDB configs and GROUP_ID (optional) in all files.

## Further Information

Check the final report file for more informations about what was done and explored in this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
