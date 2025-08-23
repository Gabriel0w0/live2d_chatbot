import os
import logging
from config import AUDIO_DIR

logger = logging.getLogger("app")  

def clean_old_audio_files(max_files: int = 20) -> None:
    try:
        if not os.path.exists(AUDIO_DIR):
            return
        files = sorted(
            [f for f in os.listdir(AUDIO_DIR) if f.endswith(".wav")],
            key=lambda x: os.path.getmtime(os.path.join(AUDIO_DIR, x)),
        )
        for f in files[:-max_files]:
            os.remove(os.path.join(AUDIO_DIR, f))
        logger.info(f"只保留最新 {max_files} 個檔案")
    except Exception as e:
        logger.error(f"清理語音快取失敗：{e}")