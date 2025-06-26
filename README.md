# Micropython บน Esp32 ผ่าน Thony
# --- Configuration ---
RS485_UART_ID = 2  # UART2 บน ESP32

RS485_TX_PIN = 17  # กำหนดขา TX ของ UART2 (GPIO17)

RS485_RX_PIN = 16  # กำหนดขา RX ของ UART2 (GPIO16)

#IMPORTANT: กำหนดขา DE/RE ของ RS485 Transceiver (เช่น MAX485, SP3485)

#ถ้าบอร์ดของคุณไม่มีขา DE/RE ที่เชื่อมกับ ESP32 ให้ตั้งค่าเป็น None

RS485_DE_RE_PIN = None # GPIO pin for DE/RE on your RS485 transceiver

# ESP32 , RS485 , COINS , TM1637 , R-10K

# Modbus RTU  9600 Master & Slave
BAUD_RATE = 9600
"GET_STATUS"

"GET_BALANCE"

"ADD_BALANCE=1"

"GET_COIN_COUNT"

"SUB_BALANCE=1"

"RESET_COUNT"

"RESET_BALANCE"

"UNKNOWN_CMD"![1000017838](https://github.com/user-attachments/assets/10f41497-3a49-4716-b408-10b37d2d699a)

