#!/usr/bin/python3
# -- coding: UTF-8 --

import os
import sys
import time
from datetime import datetime

# -------------------
# CONFIGURATION
# -------------------
payloadLength = 100            # Max LoRa payload size
busId = 0
csId = 0
resetPin = 18
busyPin = 20
irqPin = -1
txenPin = 6
rxenPin = -1

SEND_INTERVAL = 1.0            # 1 second between LoRa transmissions

# Add LoRa library path
currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(currentdir)))
from LoRaRF import SX126x

# -------------------
# Initialize LoRa
# -------------------
def init_lora():
    """Initialize LoRa module."""
    LoRa = SX126x()
    if not LoRa.begin(busId, csId, resetPin, busyPin, irqPin, txenPin, rxenPin):
        raise Exception("Failed to initialize LoRa module!")
    LoRa.setDio2RfSwitch()
    LoRa.setFrequency(868000000)  # Set frequency to 868 MHz
    LoRa.setTxPower(14, LoRa.TX_POWER_SX1262)
    LoRa.setLoRaModulation(sf=7, bw=125000, cr=5)
    LoRa.setLoRaPacket(LoRa.HEADER_EXPLICIT, 12, payloadLength, True)
    LoRa.setSyncWord(0x3444)
    print("[INFO] LoRa ready.\n")
    return LoRa

LoRa = init_lora()

# -------------------
# MAIN LOOP
# -------------------
print("[INFO] Starting LoRa text transmission...\n")
message_count = 0
last_send_time = 0

try:
    while True:
        # 1. Prepare text message
        now_time = time.strftime("%H:%M:%S")
        message_count += 1
        message = f"TEXT|Count:{message_count}|Time:{now_time}"

        # Ensure message fits in LoRa payload
        if len(message) > payloadLength:
            message = message[:payloadLength]

        # 2. Send via LoRa every 1 second
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
                try:
                    LoRa = init_lora()  # Attempt to reinitialize LoRa
                except Exception as e2:
                    print(f"[CRITICAL] Failed to restart LoRa: {e2}")
                    time.sleep(1)

        # Small delay to prevent CPU overload
        time.sleep(0.001)

except KeyboardInterrupt:
    print("\n[INFO] Transmission stopped by user.")
finally:
    LoRa.end()
    print("[INFO] LoRa closed safely.")
