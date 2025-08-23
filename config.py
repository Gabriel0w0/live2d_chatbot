import os

DB_FILE = "memory.db"
AUDIO_DIR = "static/audio"
MAX_MEMORY = 8
MAX_FACTS_PER_USER = 20
DEFAULT_INTIMACY = 50
MAX_INTIMACY = 100
MIN_INTIMACY = 0
ALPHA = 0.3
TRANSLATE = True
os.makedirs(AUDIO_DIR, exist_ok=True)