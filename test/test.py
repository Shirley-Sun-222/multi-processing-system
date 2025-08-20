import serial
import threading

class pumpController:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        self.ser = serial.Serial(port, baudrate, timeout=1)
        self.lock = threading.Lock()
        self.current_speed = 0

class pump_thread(pumpcontrolle):
    def run(self):
        WHILE  TO READ 
        
        
    wrtie
    
        
thread1 = threading.Thread(target=pump_thread, args=(pumpController(),))
