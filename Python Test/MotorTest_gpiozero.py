from gpiozero import DigitalOutputDevice
from time import sleep

DIR_PIN  = 21   # Direction
STEP_PIN = 20   # Step

dir_pin  = DigitalOutputDevice(DIR_PIN)
step_pin = DigitalOutputDevice(STEP_PIN)

STEPS = 200     
DELAY = 0.002  

def move(steps, forward=True):
    dir_pin.value = forward
    for _ in range(steps):
        step_pin.on()
        sleep(DELAY)
        step_pin.off()
        sleep(DELAY)

if __name__ == '__main__':
    while(1):
        # spin 360 forward
        move(STEPS, forward=True)
        sleep(1)
        # spin 360 backward
        move(STEPS, forward=False)
    # except KeyboardInterrupt:
    #     pass
