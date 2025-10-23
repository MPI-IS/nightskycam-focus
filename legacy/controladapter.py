import spidev
import time
import RPi.GPIO as GPIO
 
 
def crc8_custom(data):
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
 
    

def send_command(comm_char,value1,value2):
    
    SS_PIN = 5 
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SS_PIN, GPIO.OUT)
     
    GPIO.output(SS_PIN, GPIO.HIGH)
     
    spi = spidev.SpiDev()
    spi.open(0,0) # bus 0, dispositivo 0
    spi.max_speed_hz = 1000000
     
    #print('Dati ricevuti')
     
    if comm_char == 'O' or comm_char == 'I' or comm_char == 'F' or comm_char == 'A':
        command = ord(comm_char)
    else:
        print('unknown control command (not F,A,I,O)')
        return

    
    data_to_send1 = [command,value1,value2]
    crc1 = crc8_custom(data_to_send1)
    data_to_send1.append(crc1)
    print(data_to_send1)
     
     
    try:
        GPIO.output(SS_PIN, GPIO.LOW)
        print('Dati inviati richiesta: {}'.format(data_to_send1))
        resp = spi.xfer3(data_to_send1)
        
        
        if comm_char == 'F' or comm_char == 'A':
            command_r = 0x00
            value1_r = 0x00
            value2_r = 0x00
            time.sleep(1)
     
            data_to_send2 = [command_r,value1_r,value2_r]
            crc2 = crc8_custom(data_to_send2)
            data_to_send2.append(crc2)
            print(data_to_send2)
            resp = spi.xfer3(data_to_send2)
            print('Dati ricevuti slave  risposta comando: {}'.format(resp))
     
        if comm_char =='O' :
            print('waiting 5 seconds for init')
            time.sleep(5)
            
        GPIO.output(SS_PIN, GPIO.HIGH)    
        spi.close()
        GPIO.cleanup()
     
    except KeyboardInterrupt:
        spi.close()
        GPIO.cleanup()
    
def control_lens(command_char = 'O',inputval = 0):
    value1,value2 = divmod(inputval,256)
    send_command(command_char,value1,value2)
    
def reset_adapter():
     
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(6, GPIO.OUT)
    #time.sleep(5)
     
    try:
        GPIO.output(6, GPIO.LOW)
        time.sleep(0.1)
        #GPIO.output(26, GPIO.HIGH)
         
    except KeyboardInterrupt:
        GPIO.cleanup()
         
    finally:
        GPIO.cleanup()
    time.sleep(1)
        
    
    
    
if __name__ == "__main__":
    import sys
    command_char = sys.argv[1]
    if len(sys.argv) == 3:
        inputval = int(sys.argv[2])
    else:
        inputval = 0
    
    control_lens(command_char,inputval)
    
    
