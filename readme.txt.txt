This script, "simulator.py", simulates multiple different devices by publishing directly to the MQTT server on the topic "test/#".

There is also a copy of this script running on an RPI5 to generate data for a test dashboard in Grafana.

The simulator on the RPI5 can be turned off by running the command
sudo systemctl disable --now simulator.service,
followed by sudo reboot in an SSH terminal.