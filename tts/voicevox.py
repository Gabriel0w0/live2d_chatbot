import re, asyncio, logging
from typing import Optional
from tts_voicevox import TTS
from utils.file_cleanup import clean_old_audio_files
from tts.translation import translate_to_japanese
from config import TRANSLATE

logger = logging.getLogger("app")
tts = TTS(speaker_id=58)

async def synthesize_with_translation(text: str) -> Optional[str]:
    # 去掉 emotion tag
    clean_text = re.sub(r"\[emotion:\w+\]", "", text).strip()
    if not clean_text:
        logger.warning("TTS文字為空，略過生成")
        return None
    logger.info(f"TTS 文字: {clean_text}")
    if TRANSLATE:
        clean_text = await translate_to_japanese(clean_text, "可愛、撒嬌語氣")
        logger.info(f"翻譯後文字: {clean_text}")

    # 呼叫同步 TTS 放到 thread pool
    def _synth():
        return tts.synthesize_to_file(clean_text)
    
    url = await asyncio.to_thread(_synth)
    asyncio.create_task(asyncio.to_thread(clean_old_audio_files, max_files=20)) # 背景清理舊語音檔

    return url