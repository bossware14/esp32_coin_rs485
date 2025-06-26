import machine
import time
import json

# --- Configuration ---
RS485_UART_ID = 2  # UART2 บน ESP32
RS485_TX_PIN = 17  # กำหนดขา TX ของ UART2 (GPIO17)
RS485_RX_PIN = 16  # กำหนดขา RX ของ UART2 (GPIO16)
# IMPORTANT: กำหนดขา DE/RE ของ RS485 Transceiver (เช่น MAX485, SP3485)
# ถ้าบอร์ดของคุณไม่มีขา DE/RE ที่เชื่อมกับ ESP32 ให้ตั้งค่าเป็น None
RS485_DE_RE_PIN = None # GPIO pin for DE/RE on your RS485 transceiver
BAUD_RATE = 9600
led = machine.Pin(2, machine.Pin.OUT, value=0)

COIN_ACCEPTOR_PIN = 4 # GPIO pin for coin acceptor pulse input

WALLET_DATA_FILE = "wallet_data.json" # File to store wallet data for persistence
SAVE_INTERVAL_SECONDS = 60 # How often to save data to file (e.g., every 60 seconds)

# --- Global Variables for Wallet Data ---
coin_balance = 0
coin_acceptor_count = 0

# --- Global for timing file saves ---
last_save_time = time.time()

# --- Global for Debouncing ---
last_coin_pulse_time = 0 # Store the timestamp of the last valid coin pulse
DEBOUNCE_TIME_MS = 100 # Minimum time between two valid coin pulses (milliseconds)
                       # ปรับค่านี้ตามความเหมาะสม เช่น 50ms, 100ms หรือ 200ms
                       # ขึ้นอยู่กับลักษณะพัลส์ของตัวหยอดเหรียญคุณ

# --- Coin Acceptor ISR (Interrupt Service Routine) ---
def coin_pulse_handler(pin):
    global coin_acceptor_count, coin_balance, last_coin_pulse_time
    current_time_ms = time.ticks_ms() # Get current time in milliseconds

    # Check if enough time has passed since the last valid pulse (debouncing)
    if time.ticks_diff(current_time_ms, last_coin_pulse_time) > DEBOUNCE_TIME_MS:
        # Check pin value again to ensure it's still high (optional, but good for noisy lines)
        # If the pulse is very short, this might miss it, so test carefully.
        # For typical coin acceptors, a rising edge with pull-down is usually clean enough.
        # if pin.value() == 1: # Only count if the pin is still high after a tiny delay
        coin_acceptor_count += 1
        coin_balance += 1
        last_coin_pulse_time = current_time_ms # Update the last valid pulse time
        print(f"[{time.time():.0f}] Coin detected! Balance: {coin_balance}, Count: {coin_acceptor_count}")
    else:
        coin_acceptor_count = 0
        coin_balance = 0
        print(f"[{time.time():.0f}] Debounce ignored pulse. Diff: {time.ticks_diff(current_time_ms, last_coin_pulse_time)}")


# --- File Operations for Data Persistence ---
def save_wallet_data():
    """
    Saves the current state of wallet data to a JSON file.
    """
    global coin_balance, coin_acceptor_count
    try:
        data_to_save = {
            "coin_balance": coin_balance,
            "coin_acceptor_count": coin_acceptor_count
        }
        with open(WALLET_DATA_FILE, "w") as f:
            json.dump(data_to_save, f)
        print(f"[{time.time():.0f}] Wallet data saved to {WALLET_DATA_FILE}. Balance: {coin_balance}, Count: {coin_acceptor_count}")
    except Exception as e:
        print(f"[{time.time():.0f}] Error saving wallet data: {e}")

def load_wallet_data():
    """
    Loads wallet data from the JSON file.
    """
    global coin_balance, coin_acceptor_count
    try:
        with open(WALLET_DATA_FILE, "r") as f:
            loaded_data = json.load(f)
            if "coin_balance" in loaded_data:
                coin_balance = loaded_data["coin_balance"]
                coin_balance = 0
            if "coin_acceptor_count" in loaded_data:
                coin_acceptor_count = loaded_data["coin_acceptor_count"]
            print(f"[{time.time():.0f}] Wallet data loaded from {WALLET_DATA_FILE}. "
                  f"Initial Balance: {coin_balance}, Initial Count: {coin_acceptor_count}")
    except OSError:
        print(f"[{time.time():.0f}] No {WALLET_DATA_FILE} found, initializing with default values.")
        save_wallet_data() # Create file with current defaults
    except Exception as e:
        print(f"[{time.time():.0f}] Error loading wallet data: {e}. Resetting to defaults.")
        coin_balance = 0
        coin_acceptor_count = 0
        save_wallet_data() # Try saving defaults to fix the file

# --- Custom RS485 Communication Functions ---
def set_rs485_direction(direction):
    """
    Controls the DE/RE pin for the RS485 transceiver.
    'tx': Transmit mode (DE/RE HIGH)
    'rx': Receive mode (DE/RE LOW)
    """
    if RS485_DE_RE_PIN is None:
        # If no DE/RE pin is defined, assume auto-direction or shared bus where always listening
        return

    de_re_pin = machine.Pin(RS485_DE_RE_PIN, machine.Pin.OUT)
    if direction == 'tx':
        de_re_pin.value(1) # Set DE/RE HIGH for transmit
    else:
        de_re_pin.value(0) # Set DE/RE LOW for receive
    time.sleep_us(100) # Small delay for transceiver to switch modes (increased for robustness)

def send_message(uart, message_bytes):
    """
    Sends a message over RS485 using a simple custom protocol.
    Protocol: [START_BYTE] [LENGTH] [DATA...] [CHECKSUM]
    START_BYTE: 0x7E
    LENGTH: Length of DATA (1 byte)
    DATA: The actual message content
    CHECKSUM: Sum of LENGTH + DATA, then modulo 256
    """
    set_rs485_direction('tx')

    # Calculate checksum: sum of LENGTH byte + DATA bytes
    length_byte = bytes([len(message_bytes)])
    checksum_data_for_calc = length_byte + message_bytes # Combine length byte and data for checksum calculation
    checksum = sum(checksum_data_for_calc) % 256

    # Prepare the full packet
    packet = b'\x7E' + length_byte + message_bytes + bytes([checksum])

    uart.write(packet)
    time.sleep_ms(max(20, len(packet) * 2)) # Give more time for transmission based on packet length

    set_rs485_direction('rx') # Switch back to receive mode after sending

def read_message(uart, timeout_ms=500):
    start_time = time.ticks_ms()
    buffer = b''
    while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
        if uart.any():
            buffer += uart.read()

            # --- Protocol Parsing Logic ---
            while len(buffer) > 0:
                # Find the start byte (0x7E)
                start_index = buffer.find(b'\x7E') # <--- แก้ไขตรงนี้

                if start_index == -1:
                    # No start byte found, clear buffer and wait for new data
                    buffer = b''
                    break # Exit inner while loop

                # Discard any bytes before the start byte
                if start_index > 0:
                    buffer = buffer[start_index:]

                # Now buffer should start with 0x7E

                # Check if we have at least Start + Length + Checksum (minimum packet size 3 bytes for 0 length data)
                if len(buffer) < 3:
                    # Not enough bytes for header + checksum, wait for more
                    break # Exit inner while loop, wait for more data

                # Get length and potential end of packet
                data_length = buffer[1]
                expected_packet_length = 1 + 1 + data_length + 1 # Start + Length + Data + Checksum

                if len(buffer) >= expected_packet_length:
                    # We have a full potential packet
                    full_packet = buffer[0 : expected_packet_length]

                    received_checksum = full_packet[-1]

                    # Calculate checksum over LENGTH byte + DATA bytes
                    calculated_checksum_data = full_packet[1 : -1] # This is (LENGTH byte + DATA bytes)
                    calculated_checksum = sum(calculated_checksum_data) % 256

                    if received_checksum == calculated_checksum:
                        # Valid packet, extract data
                        data_part = full_packet[2 : 2 + data_length]
                        buffer = buffer[expected_packet_length:] # Remove processed packet from buffer
                        return data_part
                    else:
                        print(f"[{time.time():.0f}] Checksum mismatch: Expected {calculated_checksum}, Got {received_checksum}. Discarding packet.")
                        # Discard this bad packet by shifting the buffer past the current start byte
                        buffer = buffer[1:] # Shift to find next potential start byte
                else:
                    # Not enough bytes for the full packet yet, wait for more data
                    break # Exit inner while loop, wait for more data
        time.sleep_ms(5) # Small delay to avoid busy-waiting

    return None # Timeout or no complete valid message received

# --- RS485 Slave Mode ---
def main_slave_mode():
    """
    ESP32 acts as a Slave, waiting for commands from a Master.
    """
    global last_save_time, coin_balance, coin_acceptor_count
    print(f"[{time.time():.0f}] Initializing ESP32 Custom RS485 Slave Wallet...")
    load_wallet_data()
    uart = machine.UART(RS485_UART_ID, baudrate=BAUD_RATE,
                        tx=machine.Pin(RS485_TX_PIN),
                        rx=machine.Pin(RS485_RX_PIN))
    print(f"[{time.time():.0f}] UART{RS485_UART_ID} initialized on TX:{RS485_TX_PIN}, RX:{RS485_RX_PIN} at {BAUD_RATE} baud.")

    if RS485_DE_RE_PIN is not None:
        machine.Pin(RS485_DE_RE_PIN, machine.Pin.OUT).value(0) # Start in RX mode
        print(f"[{time.time():.0f}] DE/RE pin initialized on GPIO{RS485_DE_RE_PIN}.")

    # Initialize Coin Acceptor Pin with Interrupt
    coin_pin = machine.Pin(COIN_ACCEPTOR_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
    coin_pin.irq(trigger=machine.Pin.IRQ_RISING, handler=coin_pulse_handler)
    print(f"[{time.time():.0f}] Coin acceptor connected to GPIO{COIN_ACCEPTOR_PIN} with IRQ_RISING enabled.")
    import tm1637
    from machine import Pin
    tm = tm1637.TM1637(clk=Pin(19), dio=Pin(22))
    print(f"[{time.time():.0f}] Ready to receive custom RS485 commands and coin pulses (Slave Mode)...")
    while True:
        # Check for periodic data save
        current_time = time.time()
        if current_time - last_save_time >= SAVE_INTERVAL_SECONDS:
            save_wallet_data()
            last_save_time = current_time

        # Listen for incoming messages
        received_data = read_message(uart, timeout_ms=100) # Shorter timeout for quick loop
        if coin_balance == 0 :
           led.value(0)
        else:
           led.value(1)
        tm.number(coin_balance)

        if received_data:
            try:
                command = received_data.decode('utf-8').strip() # Assume commands are UTF-8 strings
                print(f"[{time.time():.0f}] Received command: '{command}'")
                response = b"OK"
                amount = 0
                data_changed = False
                res_status = "error"
                if command == "GET_BALANCE":
                    res_status = "success"
                    response = f"BALANCE={coin_balance}".encode('utf-8')
                elif command == "GET_STATUS":
                    res_status = "success"
                    response = "get_status" #f"COUNT={coin_acceptor_count}".encode('utf-8')
                elif command == "GET_COIN_COUNT":
                    res_status = "success"
                    response = f"COUNT={coin_acceptor_count}".encode('utf-8')
                elif command.startswith("ADD_BALANCE="):
                    try:
                        res_status = "success"
                        amount = int(command.split('=')[1])
                        coin_balance += amount
                        response = f"NEW_BALANCE={coin_balance}".encode('utf-8')
                        data_changed = True
                    except ValueError:
                        res_status = "success"
                        response = b"ERROR: Invalid amount"
                elif command == "RESET_BALANCE":
                    res_status = "success"
                    coin_balance = 0
                    data_changed = True
                    response = f"BALANCE={coin_balance}".encode('utf-8')
                elif command.startswith("SUB_BALANCE="):
                    try:
                        amount = int(command.split('=')[1])
                        if coin_balance >= amount :
                            res_status = "success"
                            coin_balance = max(0, coin_balance - amount) # Ensure not negative
                            response = f"BALANCE={coin_balance}".encode('utf-8')
                            data_changed = True
                        else :
                            res_status = "error"
                            response = "error_amount"
                    except ValueError:
                        res_status = "error"
                        response = b"ERROR: Invalid amount"
                elif command == "RESET_COUNT":
                    res_status = "success"
                    coin_acceptor_count = 0
                    response = "COUNT_RESET_OK"
                    data_changed = True
                else:
                    res_status = "error"
                    response = b"ERROR: Unknown command"

                #print(f"[{time.time():.0f}] Sending response: '{response.decode('utf-8')}'")
                data = {"status":res_status,"coin_balance":coin_balance,"coin_acceptor_count":coin_acceptor_count,"response":response,"data_changed":data_changed,"amount":amount} 
                send_message(uart, json.dumps(data).encode('utf-8'))
                print(data)
                if data_changed:
                    save_wallet_data()

            except Exception as e:
                print(f"[{time.time():.0f}] Error processing command: {e}")
                data = {"status":res_status,"coin_balance":coin_balance,"coin_acceptor_count":coin_acceptor_count,"response":response,"data_changed":data_changed}
                #send_message(uart, b"ERROR: Internal processing error")
                send_message(uart, json.dumps(data).encode('utf-8'))
        time.sleep_ms(10)


# --- RS485 Master Mode (Example - would run on another ESP32 or device) ---
def main_master_mode():
    print(f"[{time.time():.0f}] Initializing ESP32 Custom RS485 Master...")
    uart = machine.UART(RS485_UART_ID, baudrate=BAUD_RATE,
                        tx=machine.Pin(RS485_TX_PIN),
                        rx=machine.Pin(RS485_RX_PIN))

    print(f"[{time.time():.0f}] UART{RS485_UART_ID} initialized on TX:{RS485_TX_PIN}, RX:{RS485_RX_PIN} at {BAUD_RATE} baud.")

    if RS485_DE_RE_PIN is not None:
        machine.Pin(RS485_DE_RE_PIN, machine.Pin.OUT).value(0) # Start in RX mode
        print(f"[{time.time():.0f}] DE/RE pin initialized on GPIO{RS485_DE_RE_PIN}.")

    print(f"[{time.time():.0f}] Ready to send custom RS485 commands (Master Mode)...")

    commands_to_send = [
        "GET_STATUS",
        "GET_BALANCE",
        "ADD_BALANCE=1",
        "GET_BALANCE",
        "GET_COIN_COUNT",
        "SUB_BALANCE=1",
        "GET_BALANCE",
        "RESET_COUNT",
        "GET_COIN_COUNT",
        "RESET_BALANCE",
        "UNKNOWN_CMD" # Test an unknown command
    ]

    for cmd in commands_to_send:
        print(f"\n[{time.time():.0f}] Sending command to Slave: '{cmd}'")
        send_message(uart, cmd.encode('utf-8'))
        response = read_message(uart, timeout_ms=1000)
        if response:
            print(f"[{time.time():.0f}] Received response from Slave: '{response.decode('utf-8')}'")
        else:
            print(f"[{time.time():.0f}] No response from Slave or invalid response.")

        time.sleep(2) # Wait 2 seconds before sending next command


debounce_delay = 1000
timer_direction = 0
def button_pressed(pin):
    global timer_direction
    time.sleep_ms(debounce_delay)
    now = time.ticks_ms()
    print("button_pressed",pin.value(),timer_direction,now,debounce_delay)
    if pin.value() == 0:
            led.value(1)
            timer_direction += 1
    if pin.value() == 1:
            led.value(0)
            timer_direction = 0

    if timer_direction == 1 and pin.value() == 0 :
        uart = machine.UART(RS485_UART_ID, baudrate=BAUD_RATE,
                        tx=machine.Pin(RS485_TX_PIN),
                        rx=machine.Pin(RS485_RX_PIN))
        send_message(uart, 'SUB_BALANCE=1')
        response = json.loads(read_message(uart, timeout_ms=1000))
        print(response)


reset_button = machine.Pin(0, mode=machine.Pin.IN, pull=machine.Pin.PULL_UP)
reset_button.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_pressed)


# --- Main Execution ---
if __name__ == "__main__":
    # เลือกโหมดที่ต้องการรัน:
    main_slave_mode() # สำหรับ ESP32 ที่เป็นกระเป๋าเงินและรอรับคำสั่ง
    #main_master_mode() # สำหรับ ESP32 ที่จะสั่งงานกระเป๋าเงิน (ต้องรันบนอีกบอร์ดนึง)
