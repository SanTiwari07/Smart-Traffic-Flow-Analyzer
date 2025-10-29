import socket
import time
import re

# Test TCP sender for ESP32 seven-seg display
# IMPORTANT: Change this to the IP address of your ESP32
# You can find this in the Arduino Serial Monitor when the ESP32 connects to Wi-Fi.
ESP32_IP = "192.168.85.1"  # <-- CHANGE THIS
PORT = 80

def send_command_to_esp32(command):
    """
    Connects to the ESP32, sends a single command, and closes the connection.
    Returns True on success, False on failure.
    """
    message = command + "\n"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((ESP32_IP, PORT))
            s.sendall(message.encode('utf-8'))
            return True
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"Error: Could not connect to ESP32 at {ESP32_IP}. Check IP and Wi-Fi. ({e})")
        return False
    except Exception as e:
        print(f"An unknown error occurred: {e}")
        return False

if __name__ == "__main__":
    print("--- ESP32 TCP Test Sender ---")
    print("The signal should be YELLOW by default.")
    while True:
        start_command = ""
        while True:
            prompt = "\nEnter the starting command (e.g., A55 or C30) or type 'exit' to quit: "
            start_command = input(prompt).strip().upper()
            if start_command == 'EXIT':
                print("Exiting program.")
                exit()
            if re.match(r'^[AC]\d+$', start_command):
                break
            else:
                print("Invalid format. Please use 'A' or 'C' followed by a number (e.g., A55).")

        color_char = start_command[0]
        try:
            start_number = int(start_command[1:])
        except ValueError:
            print("Invalid number in command. Please try again.")
            continue

        color_name = "RED" if color_char == 'A' else "GREEN"
        print(f"\nStarting {color_name} signal countdown from {start_number}...")
        for i in range(start_number, -1, -1):
            command = f"{color_char}{i}"
            print(f"Sending command: {command}")
            if not send_command_to_esp32(command):
                print("Stopping cycle due to connection failure.")
                break
            time.sleep(1)

        print("\nMain countdown finished.")

        print("Switching to YELLOW for 5 seconds...")
        for i in range(5, 0, -1):
            command = f"B{i}"
            print(f"Sending command: {command}")
            if not send_command_to_esp32(command):
                print("Stopping cycle due to connection failure.")
                break
            time.sleep(1)

        print("\nCycle complete. Setting signal to idle (YELLOW).")
        send_command_to_esp32("B")
        print("-------------------------------------------------")


