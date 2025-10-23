import RPi.GPIO as GPIO
import time
 
 
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