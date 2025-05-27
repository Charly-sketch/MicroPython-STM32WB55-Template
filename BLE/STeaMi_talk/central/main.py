from micropython import const
import asyncio
import aioble
import bluetooth
import struct

from pins import *

# BLE UUIDs
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
_ENV_SENSE_TEMP_UUID = bluetooth.UUID(0x2A6E)

# Identité unique du périphérique
ble = bluetooth.BLE()
ble.active(True)
mac_bytes = ble.config('mac')[1]
mac_suffix = ''.join(f'{b:02X}' for b in mac_bytes[-2:])
device_name = f"STeaMi-{mac_suffix}"
print("Device name:", device_name)

# Variables globales
discovered_devices = []         # Liste de ScanResult
selected_index = 0              # Index de sélection dans le menu
scan_active = True              # Scan actif ou non
active_connection = None        # Connexion BLE actuelle

# Tâche d'affichage principal
async def display_task():
    global selected_index, discovered_devices
    while True:
        if scan_active:
            display.fill(0)
            display.text(device_name, text_x_center_position(device_name), 20, 255)
            display_menu(discovered_devices, selected_index)
            display.show()
        await asyncio.sleep(0.1)

# Tâche de gestion des boutons
async def button_task():
    global selected_index, discovered_devices, scan_active, active_connection
    while True:
        button = await wait_for_button()
        if button == "A" and discovered_devices:
            selected_index = (selected_index + 1) % len(discovered_devices)
        elif button == "B" and discovered_devices:
            selected_index = (selected_index - 1) % len(discovered_devices)
        elif button == "MENU":
            if scan_active:
                if not discovered_devices:
                    print("No devices found to connect.")
                    continue
                # Passage en mode connecté
                scan_active = False
                selected = discovered_devices[selected_index]
                print(f"Trying to connect to {selected.name()} @ {selected.device.addr_hex()}")
                asyncio.create_task(connect_to_device(selected.device, selected.name()))
            else:
                # Repassage en mode scan + déconnexion
                if active_connection:
                    print("Disconnecting...")
                    await active_connection.disconnect()
                    active_connection = None
                scan_active = True
        await asyncio.sleep(0.1)

# Connexion à un périphérique BLE
async def connect_to_device(device, name):
    global active_connection, scan_active

    try:
        print("Connecting...")
        connection = await device.connect(timeout_ms=5000)
        active_connection = connection
    except asyncio.TimeoutError:
        print("Connection timeout")
        scan_active = True
        return

    async with connection:
        try:
            service = await connection.service(_ENV_SENSE_UUID)
            characteristic = await service.characteristic(_ENV_SENSE_TEMP_UUID)
        except Exception as e:
            print("Service discovery failed:", e)
            scan_active = True
            return

        while connection.is_connected() and not scan_active:
            try:
                raw = await characteristic.read()
                distance_mm = struct.unpack("<h", raw)[0]
                print("Distance:", distance_mm)

                display.fill(0)
                display.text(name, text_x_center_position(name), 20, 255) 
                display.text(f"{distance_mm} mm", text_x_center_position(f"{distance_mm} mm"), 60, 255)
                display.show()
            except Exception as e:
                print("Read error:", e)
                break

            await asyncio.sleep(1)

        print("Disconnected from device")
        active_connection = None
        scan_active = True

# Scan BLE pour les périphériques STeaMi
async def scan_task():
    global discovered_devices
    while True:
        if scan_active:
            print("--- Starting Scan ---")
            # discovered_devices.clear()
            devices = []
            async with aioble.scan(1000, interval_us=30000, window_us=30000, active=True) as scanner:
                async for result in scanner:
                    name = result.name()
                    if name and name.startswith("STeaMi"):
                        if result.device not in [d.device for d in devices]:
                            print(f"Found: {name}")
                            devices.append(result)
            discovered_devices = devices
        await asyncio.sleep(0.)

# Démarrage des tâches principales
async def main():
    await asyncio.gather(
        scan_task(),
        display_task(),
        button_task()
    )

asyncio.run(main())