from enum import Enum


class MoodEnum(str, Enum):
    happy = "happy"
    sad = "sad"
    calm = "calm"
    energetic = "energetic"
    romantic = "romantic"


class GenreEnum(str, Enum):
    pop = "pop"
    rock = "rock"
    jazz = "jazz"
    classical = "classical"
    hiphop = "hiphop"
    electronic = "electronic"
    lofi = "lofi"
    metal = "metal"
    rnb = "rnb"
