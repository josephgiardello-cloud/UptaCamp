from __future__ import annotations

import math
from array import array

import pygame


class AudioManager:
    def __init__(self, volume: float = 0.6):
        self.available = False
        self.volume = max(0.0, min(1.0, float(volume)))
        self.sounds: dict[str, pygame.mixer.Sound] = {}

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1)
            self.available = True
            self.sounds = {
                "card": self._make_tone(660, 0.045, fade=True),
                "score": self._make_chime((880, 1174), 0.11),
                "win": self._make_chime((523, 659, 784, 1046), 0.42),
            }
            self.set_volume(self.volume)
        except pygame.error:
            self.available = False

    def _make_tone(self, frequency: float, duration_s: float, fade: bool = False) -> pygame.mixer.Sound:
        sample_rate = 22050
        total_samples = max(1, int(sample_rate * duration_s))
        buf = array("h")
        amplitude = 12000
        for i in range(total_samples):
            t = i / sample_rate
            env = 1.0
            if fade:
                env = max(0.0, 1.0 - (i / total_samples))
            sample = int(amplitude * env * math.sin(2.0 * math.pi * frequency * t))
            buf.append(sample)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _make_chime(self, notes: tuple[float, ...], duration_s: float) -> pygame.mixer.Sound:
        sample_rate = 22050
        total_samples = max(1, int(sample_rate * duration_s))
        buf = array("h")
        amplitude = 8000
        note_window = max(1, total_samples // max(1, len(notes)))

        for i in range(total_samples):
            note_idx = min(len(notes) - 1, i // note_window)
            freq = notes[note_idx]
            t = i / sample_rate
            env = max(0.0, 1.0 - (i / total_samples))
            sample = int(amplitude * env * math.sin(2.0 * math.pi * freq * t))
            buf.append(sample)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))
        if not self.available:
            return
        for sound in self.sounds.values():
            sound.set_volume(self.volume)

    def play(self, name: str) -> None:
        if not self.available or self.volume <= 0.0:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()
