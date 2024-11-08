import pygame

class LoopingMP3Player:
    def __init__(self, file_path):
        self.name = file_path
        pygame.mixer.init()
        self.sound = pygame.mixer.Sound(file_path)
        self.channel = self.sound.play(loops=-1)  # -1 means loop indefinitely
        self.channel.pause()  # Start paused
        self.volume = 1.0  # 0.0 to 1.0

    def play(self):
        self.channel.unpause()
        print("playing" + self.name)

    def pause(self):
        self.channel.pause()

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))
        self.channel.set_volume(self.volume)
