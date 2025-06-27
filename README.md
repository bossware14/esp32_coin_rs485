# Micropython บน Esp32 ผ่าน Thony
    """
    สั่งจ่ายเหรียญผ่าน Modbus RTU
    สมมติว่าเครื่องจ่ายเงินมี Holding Register (FC3/FC16) หรือ Coil (FC1/FC5)
    สำหรับสั่งจ่ายเงิน
    
    คุณต้องตรวจสอบคู่มือของเครื่องจ่ายเงินว่าใช้ Function Code อะไร
    และ Register Address/Coil Address เบอร์อะไร สำหรับสั่งจ่าย
    
    ตัวอย่าง: สมมติว่า Holding Register Address 40001 (0x0000) ใช้สำหรับใส่จำนวนเหรียญที่ต้องการจ่าย
    """
# การต่อ ESP32 กับ เครื่องรับเหรียญ
    [เครื่องหยอดเหรียญ] กับ [ESP32]
       (Coin) --> (GPIO 4) [ESP32]
       (GND)  --> (GND) [ESP32]
              -->  (GND)(12V)
       (VCC) -->  (12V)
       
    [ESP32] ต่อ [เครื่องหยอดเหรียญ] ผ่าน ตัวต้านทาน (R10K)
       (3.3V) -->  R(10K) --> (GND) [ESP32]
                   R(10K) --> GPIO 4 [ESP32]
                   R(10K) --> (COIN) [เครื่องหยอดเหรียญ] 
                   
    [TM1637] ต่อ [ESP32]
       (CLK)  -->  GPIO 19
       (DIO)  -->  GPIO 22
       (VCC)  -->  3.3V
       (GND)  -->  GND
       
    [RS485 to TTL] ต่อ [ESP32]
       (RX)  --> GPIO 16
       (TX)  --> GPIO 17
       (VCC) --> 3.3V
       (GND) --> GND
       
# --- Configuration ---
    """
    RS485_UART_ID = 2  # UART2 บน ESP32
    RS485_TX_PIN = 17  # กำหนดขา TX ของ UART2 (GPIO17)
    RS485_RX_PIN = 16  # กำหนดขา RX ของ UART2 (GPIO16)

    #IMPORTANT: กำหนดขา DE/RE ของ RS485 Transceiver (เช่น MAX485, SP3485)
    #ถ้าบอร์ดของคุณไม่มีขา DE/RE ที่เชื่อมกับ ESP32 ให้ตั้งค่าเป็น None
    RS485_DE_RE_PIN = None # GPIO pin for DE/RE on your RS485 transceiver
    """
    
# --- Global for Debouncing ---
    last_coin_pulse_time = 0 # Store the timestamp of the last valid coin pulse
    DEBOUNCE_TIME_MS = 100 # Minimum time between two valid coin pulses (milliseconds)
                       # ปรับค่านี้ตามความเหมาะสม เช่น 50ms, 100ms หรือ 200ms
                       # ขึ้นอยู่กับลักษณะพัลส์ของตัวหยอดเหรียญคุณ
                       
# ESP32 , RS485 , COINS , TM1637 , R-10K
    RS485 to TTL (1)
    เครื่องหยอดเหรียญ 12V
    TM1637 quad 7-segment LED
    R10K (1)

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

