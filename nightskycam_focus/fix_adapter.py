import spidev
import time
import RPi.GPIO as GPIO
from contextlib import contextmanager
from enum import Enum

SS_PIN = 5
RESET_PIN = 6
MAX_SPEED_HZ = 1000000
SLEEP = 0.1
MIDDLE_SLEEP = 2.0
LONG_SLEEP = 5.0

class _CommandType(Enum):
    OPEN = "O"
    FOCUS = "F"
    APERTURE = "A"


def _crc8_custom(data):
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1)^0x05) & 0xFF
            else:
                crc <<=1
            crc&=0xFF
             
    return crc

@contextmanager
def _closing(spi: spidev.SpiDev):
    try:
        yield
    finally:
        spi.close()
        GPIO.cleanup()

def _send_command(command_type: _CommandType, value: int):

    value1, value2 = divmod(value ,256)
    
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SS_PIN, GPIO.OUT)
    GPIO.output(SS_PIN, GPIO.HIGH)
     
    spi = spidev.SpiDev()
    spi.open(0,0)
    spi.max_speed_hz = MAX_SPEED_HZ
    command = ord(command_type.value)
    data_to_send1 = [command,value1,value2]
    crc1 = _crc8_custom(data_to_send1)
    data_to_send1.append(crc1)

    with _closing(spi):
    
        GPIO.output(SS_PIN, GPIO.LOW)
        resp = spi.xfer3(data_to_send1)

        if command_type in (_CommandType.FOCUS, _CommandType.APERTURE):
            command_r = 0x00
            value1_r = 0x00
            value2_r = 0x00
            time.sleep(1)
            data_to_send2 = [command_r,value1_r,value2_r]
            crc2 = _crc8_custom(data_to_send2)
            data_to_send2.append(crc2)
            resp = spi.xfer3(data_to_send2)
     
        if command_type == _CommandType.OPEN :
            time.sleep(LONG_SLEEP)
            
        GPIO.output(SS_PIN, GPIO.HIGH)    

def _reset():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RESET_PIN, GPIO.OUT)
    try:
        GPIO.output(RESET_PIN, GPIO.LOW)
        time.sleep(SLEEP)
    finally:
        GPIO.cleanup()


def set_focus(value):
    _reset()
    time.sleep(MIDDLE_SLEEP)
    _send_command(_CommandType.OPEN, 0)
    time.sleep(MIDDLE_SLEEP)
    _send_command(_CommandType.FOCUS, value)
    time.sleep(MIDDLE_SLEEP)
    _reset()
    
if __name__ == "__main__":
    import sys
    inputval = int(sys.argv[1])
    set_focus(inputval)
