import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PIAPI_API_KEY = os.getenv("PIAPI_API_KEY", "")
FISH_AUDIO_API_KEY = os.getenv("FISH_AUDIO_API_KEY", "")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

DEFAULT_DURATION_SEC = 45

# Fish Audio ボイス選択肢
VOICES = [
    {"id": "9c51d76d1bfa4a3a864bee5c56c4e096", "label": "ボイス1"},
    {"id": "71bf4cb71cd44df6aa603d51db8f92ff", "label": "ななみん"},
]
SCENE_COUNT_MIN = 3
SCENE_COUNT_MAX = 6

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

FISH_AUDIO_VOICE_ID = "9c51d76d1bfa4a3a864bee5c56c4e096"
