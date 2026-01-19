#!/usr/bin/env python3
"""
Farm Sensor Simulator
Simulates weather stations and soil sensors
"""

import json
import time
import random
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

# MQTT Configuration
MQTT_BROKER = "10.116.227.185"
MQTT_PORT = 1883

# File to store cumulative rain
RAIN_FILE = "rain_cumulative.json"

# Weather station configurations
WEATHER_STATIONS = [
    {"station_id": "WS_MASTER_01", "station_type": "master"},
    {"station_id": "WS_SAT_01", "station_type": "satellite"},
    {"station_id": "WS_SAT_02", "station_type": "satellite"},
    {"station_id": "WS_SAT_03", "station_type": "satellite"},
    {"station_id": "WS_SAT_04", "station_type": "satellite"},
    {"station_id": "WS_SAT_05", "station_type": "satellite"},
]

# Soil sensor configurations (5 sensors, all same type)
SOIL_SENSORS = [
    {"station_id": "SS_01", "station_type": "soil"},
    {"station_id": "SS_02", "station_type": "soil"},
    {"station_id": "SS_03", "station_type": "soil"},
    {"station_id": "SS_04", "station_type": "soil"},
    {"station_id": "SS_05", "station_type": "soil"},
]

# Helpers to save/load cumulative rain
def load_rain_cumulative():
    try:
        with open(RAIN_FILE, "r") as f:
            data = json.load(f)
            return float(data.get("rain_cumulative", 0.0))
    except FileNotFoundError:
        return 0.0
    except Exception as e:
        print(f"Error loading rain cumulative: {e}")
        return 0.0

def save_rain_cumulative(value):
    try:
        with open(RAIN_FILE, "w") as f:
            json.dump({"rain_cumulative": round(value, 2)}, f)
    except Exception as e:
        print(f"Error saving rain cumulative: {e}")

# Base values for WS_MASTER_01
MASTER_BASE = {
    "air_temp": 20.0,          # °C
    "rh": 55.0,                # %
    "pressure": 1013.0,        # hPa
    "wind_speed": 3.0,         # m/s
    "wind_direction": 180,     # degrees
    "precipitation": 0.0,      # current rain intensity (mm/hr)
    "rain_cumulative": load_rain_cumulative(),  # cumulative rain
    "solar_radiation": 500.0,  # W/m²
    "par": 500.0,              # µmol/m²/s
    "co2": 400.0,              # ppm
    "pm": 10.0,                # µg/m³
    "soil_temp_10": 18.0,      # °C
    "soil_temp_20": 17.5,      # °C
    "soil_temp_30": 17.0,      # °C
    "soil_surface_temp": 19.0  # °C
}

# Maximum step change per iteration
MAX_STEP = {
    "air_temp": 0.3,
    "rh": 2.0,
    "pressure": 0.5,
    "wind_speed": 0.5,
    "wind_direction": 15,
    "precipitation": 2.0,  # mm/hr
    "solar_radiation": 50,
    "par": 50,
    "co2": 5,
    "pm": 2,
    "soil_temp_10": 0.2,
    "soil_temp_20": 0.2,
    "soil_temp_30": 0.2,
    "soil_surface_temp": 0.3
}

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✓ Connected to MQTT broker")
    else:
        print(f"✗ Failed to connect, return code {rc}")

def random_walk(value, step):
    """Random walk: current value +/- step"""
    delta = random.uniform(-step, step)
    return round(value + delta, 2)

def wrap_360(value):
    """Wrap any angle to 0-360° circularly"""
    return value % 360

def publish_master_station(client, dt):
    """Publish realistic data for WS_MASTER_01"""
    global MASTER_BASE
    
    # Update values with a random walk (skip rain_cumulative)
    for key in MASTER_BASE:
        if key != "rain_cumulative":
            MASTER_BASE[key] = random_walk(MASTER_BASE[key], MAX_STEP.get(key, 0.1))
    
    # Clamp values
    MASTER_BASE["wind_speed"] = max(MASTER_BASE["wind_speed"], 0.0)
    MASTER_BASE["precipitation"] = max(0.0, MASTER_BASE["precipitation"])
    MASTER_BASE["rh"] = max(0.0, min(100.0, MASTER_BASE["rh"]))
    MASTER_BASE["wind_direction"] = wrap_360(MASTER_BASE["wind_direction"])
    
    # Soil temps slightly follow air temp
    MASTER_BASE["soil_temp_10"] += (MASTER_BASE["air_temp"] - MASTER_BASE["soil_temp_10"]) * 0.05
    MASTER_BASE["soil_temp_20"] += (MASTER_BASE["air_temp"] - MASTER_BASE["soil_temp_20"]) * 0.03
    MASTER_BASE["soil_temp_30"] += (MASTER_BASE["air_temp"] - MASTER_BASE["soil_temp_30"]) * 0.02
    MASTER_BASE["soil_surface_temp"] += (MASTER_BASE["air_temp"] - MASTER_BASE["soil_surface_temp"]) * 0.07

    # Update cumulative rain based on dt (seconds)
    MASTER_BASE["rain_cumulative"] += MASTER_BASE["precipitation"] * (dt / 3600.0)  # mm/hr -> mm for dt seconds
    MASTER_BASE["rain_cumulative"] = max(0.0, MASTER_BASE["rain_cumulative"])
    save_rain_cumulative(MASTER_BASE["rain_cumulative"])

    data = {
        "measurement": "weather",
        "station_id": "WS_MASTER_01",
        "station_type": "master",
        "air_temp": round(MASTER_BASE["air_temp"],2),
        "rh": round(MASTER_BASE["rh"],2),
        "pressure": round(MASTER_BASE["pressure"],2),
        "wind_speed": round(MASTER_BASE["wind_speed"],2),
        "wind_direction": int(MASTER_BASE["wind_direction"]),
        "rain_intensity": round(MASTER_BASE["precipitation"],2),
        "rain_cumulative": round(MASTER_BASE["rain_cumulative"],2),
        "solar_radiation": round(MASTER_BASE["solar_radiation"],2),
        "par": round(MASTER_BASE["par"],2),
        "co2": round(MASTER_BASE["co2"],2),
        "pm": round(MASTER_BASE["pm"],2),
        "soil_temp_10": round(MASTER_BASE["soil_temp_10"],2),
        "soil_temp_20": round(MASTER_BASE["soil_temp_20"],2),
        "soil_temp_30": round(MASTER_BASE["soil_temp_30"],2),
        "soil_surface_temp": round(MASTER_BASE["soil_surface_temp"],2),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    topic = f"test/weather/{data['station_id']}/data"
    client.publish(topic, json.dumps(data))
    print(f"  Master WS: T={data['air_temp']}°C, RH={data['rh']}%, Rain Intensity={data['rain_intensity']}mm/hr, Rain Cum={data['rain_cumulative']}mm")

def publish_weather(client, station_id, station_type):
    """Publish satellite weather station data"""
    data = {
        "measurement": "weather",
        "station_id": station_id,
        "station_type": station_type,
        "temperature": round(random.uniform(15, 25), 2),
        "humidity": round(random.uniform(40, 70), 2),
        "pressure": round(random.uniform(1000, 1020), 2),
        "wind_speed": round(random.uniform(0, 10), 2),
        "wind_direction": random.randint(0, 360),
        "rainfall": round(random.uniform(0, 5), 2),
        "solar_radiation": round(random.uniform(0, 1000), 2),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    topic = f"test/weather/{station_id}/data"
    client.publish(topic, json.dumps(data))
    print(f"  Weather {station_id}: T={data['temperature']}°C, RH={data['humidity']}%")

def publish_soil(client, station_id, station_type):
    """Publish soil sensor data"""
    data = {
        "measurement": "soil",
        "station_id": station_id,
        "station_type": station_type,
        "ph": round(random.uniform(5.5, 7.5), 2),
        "temperature": round(random.uniform(10, 25), 2),
        "moisture": round(random.uniform(30, 70), 2),
        "ec": round(random.uniform(0.5, 2.5), 2),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    topic = f"test/soil/{station_id}/data"
    client.publish(topic, json.dumps(data))
    print(f"  Soil {station_id}: pH={data['ph']}, Temp={data['temperature']}°C, Moisture={data['moisture']}%")

def main():
    print("=" * 70)
    print("Farm Sensor Simulator")
    print("=" * 70)
    print(f"MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"\nSimulating:")
    print(f"  - {len(WEATHER_STATIONS)} weather stations")
    print(f"  - {len(SOIL_SENSORS)} soil sensors")
    print("\nPress Ctrl+C to stop\n")
    
    client = mqtt.Client()
    client.on_connect = on_connect
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        time.sleep(2)
        
        iteration = 0
        last_time = time.time()
        while True:
            iteration += 1
            now = time.time()
            dt = now - last_time
            last_time = now
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Iteration {iteration}")
            
            # Publish weather station data
            for station in WEATHER_STATIONS:
                if station["station_id"] == "WS_MASTER_01":
                    publish_master_station(client, dt)
                else:
                    publish_weather(client, station["station_id"], station["station_type"])
            
            # Publish soil sensor data
            for sensor in SOIL_SENSORS:
                publish_soil(client, sensor["station_id"], sensor["station_type"])
            
            print()
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n\nStopping simulator...")
        client.loop_stop()
        client.disconnect()
        print("Disconnected from MQTT broker")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
