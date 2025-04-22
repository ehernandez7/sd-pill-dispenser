import pygame
import time

pygame.mixer.init()
pygame.mixer.music.load("Python Test/Good place.mp3")
pygame.mixer.music.play()

time.sleep(10)
pygame.mixer.music.pause()
print("Paused")

time.sleep(3)

pygame.mixer.music.unpause()
print("Resumed")

while pygame.mixer.music.get_busy():
    time.sleep(1)