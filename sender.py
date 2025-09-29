#!/usr/bin/python3
# -- coding: UTF-8 --

import os
import sys
import time
import serial
import pynmea2
from datetime import datetime

UART_PORT = "/dev/ttyAMA0"
BAUDRATE = 9600
payloadLength = 100

busId = 0
csId = 0
resetPin = 18
busyPin = 20
irqPin = -1
txenPin = 6
rxenPin = -1

SEND_INTERVAL = 0.2   # 200ms between LoRa transmissions

# Add LoRa library path
currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(currentdir)))
from LoRaRF import SX126x

# -------------------
# Initialize GPS
# -------------------
try:
    gps_serial = serial.Serial(UART_PORT, BAUDRATE, timeout=0.1)
    print(f"[INFO] Connected to GPS on {UART_PORT} at {BAUDRATE} baud.")
except serial.SerialException as e:
    print(f"[ERROR] Cannot open GPS port {UART_PORT}: {e}")
    sys.exit(1)

# -------------------
# Initialize LoRa
# -------------------
def init_lora():
    LoRa = SX126x()
    if not LoRa.begin(busId, csId, resetPin, busyPin, irqPin, txenPin, rxenPin):
        raise Exception("Failed to initialize LoRa module!")
    LoRa.setDio2RfSwitch()
    LoRa.setFrequency(868000000)
    LoRa.setTxPower(14, LoRa.TX_POWER_SX1262)
    LoRa.setLoRaModulation(sf=7, bw=125000, cr=5)
    LoRa.setLoRaPacket(LoRa.HEADER_EXPLICIT, 12, payloadLength, True)
    LoRa.setSyncWord(0x3444)
    print("[INFO] LoRa ready.\n")
    return LoRa

LoRa = init_lora()

# -------------------
# Parse GPS Data
# -------------------
def parse_gps_data(line):
    """Parses NMEA GPS RMC sentences."""
    try:
        msg = pynmea2.parse(line)
        if isinstance(msg, pynmea2.types.talker.RMC) and msg.status == "A":
            speed_kmh = (msg.spd_over_grnd or 0.0) * 1.852
            return {
                "latitude": msg.latitude,
                "longitude": msg.longitude,
                "speed_kmh": speed_kmh,
                "date": msg.datestamp.strftime("%d-%m-%Y") if msg.datestamp else "N/A",
                "time": msg.timestamp.strftime("%H:%M:%S") if msg.timestamp else "N/A"
            }
        return None
    except:
        return None

# -------------------
# MAIN LOOP
# -------------------
print("[INFO] Starting GPS + LoRa transmission...\n")
buffer = ""
last_gps_data = None
last_valid_time = 0          # Last time valid GPS data was received
gps_timeout = 5              # Seconds before declaring "GPS NOT FOUND"
last_send_time = 0           # Last LoRa transmission time

try:
    while True:
        # ========================
        # 1. Read GPS Continuously
        # ========================
        data = gps_serial.read(1024).decode('ascii', errors='replace')
        if data:
            buffer += data
            lines = buffer.split('\n')
            buffer = lines[-1]  # keep incomplete line
            for line in lines[:-1]:
                line = line.strip()
                if line.startswith('$'):
                    gps_data = parse_gps_data(line)
                    if gps_data:
                        last_gps_data = gps_data
                        last_valid_time = time.time()  # update valid GPS timestamp

        # ========================
        # 2. Prepare Message
        # ========================
        current_time = time.strftime("%H:%M:%S")
        gps_age = time.time() - last_valid_time

        if last_gps_data and gps_age <= gps_timeout:
            # Valid and recent GPS data
            message = (f"RMC|Date:{last_gps_data['date']}|Time:{last_gps_data['time']}|"
                       f"Lat:{last_gps_data['latitude']:.6f}|Lon:{last_gps_data['longitude']:.6f}|"
                       f"Speed:{last_gps_data['speed_kmh']:.2f}km/h")
        else:
            # No recent GPS data
            message = f"RMC|Time:{current_time}|GPS NOT FOUND"

        # Ensure message fits LoRa payload size
        if len(message) > payloadLength:
            message = message[:payloadLength]

        # ========================
        # 3. Send via LoRa every 200ms
        # ========================
        now = time.time()
        if (now - last_send_time >= SEND_INTERVAL):
            try:
                LoRa.beginPacket()
                LoRa.write(list(message.encode('utf-8')), len(message))
                LoRa.endPacket()  # Blocking until transmission completes
                last_send_time = now
                print(f"[SEND] {message}")
            except Exception as e:
                print(f"[ERROR] LoRa send failed: {e}")
                # Attempt to reinitialize LoRa
                try:
                    LoRa = init_lora()
                except Exception as e2:
                    print(f"[CRITICAL] Failed to restart LoRa: {e2}")
                    time.sleep(1)

        # Tiny sleep to prevent 100% CPU usage
        time.sleep(0.001)

except KeyboardInterrupt:
    print("\n[INFO] Transmission stopped by user.")
finally:
    gps_serial.close()
    LoRa.end()
    print("[INFO] Closed GPS and LoRa safely.")
