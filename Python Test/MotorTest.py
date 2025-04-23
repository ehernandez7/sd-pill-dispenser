import RPi.GPIO as GPIO
import time
DIR = 21
STEP = 20
STEPS_PER_REV = 200
delay = 0.002

GPIO.setmode(GPIO.BCM)
GPIO.setup(DIR, GPIO.OUT)
GPIO.setup(STEP, GPIO.OUT)

def move_motor(direction):
    GPIO.output(DIR, direction)
    for i in range(STEPS_PER_REV):
        GPIO.output(STEP, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(STEP, GPIO.LOW)
        time.sleep(delay)
    
try:
    move_motor(GPIO.HIGH)
    time.sleep(1)
    move_motor(GPIO.LOW)
finally:
    GPIO.cleanup()