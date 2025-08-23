import requests
import json
import uuid
import os

class TTS:
    def __init__(self, speaker_id=58):  # 猫使ビィ・人見知り
        self.speaker_id = speaker_id
        self.audio_dir = "static/audio"
        os.makedirs(self.audio_dir, exist_ok=True)

    def synthesize_to_file(self, text):
        # Step 1: audio_query
        resp = requests.post(
            "http://localhost:50021/audio_query",
            params={"text": text, "speaker": self.speaker_id}
        )
        if resp.status_code != 200:
            raise RuntimeError(f"audio_query failed: {resp.text}")
        query = resp.json()

        # Step 2: synthesis
        synth_resp = requests.post(
            "http://localhost:50021/synthesis",
            params={"speaker": self.speaker_id},
            headers={"Content-Type": "application/json"},
            data=json.dumps(query)
        )
        if synth_resp.status_code != 200:
            raise RuntimeError(f"synthesis failed: {synth_resp.text}")

        # Step 3: 存成 wav 檔
        filename = f"{uuid.uuid4().hex}.wav"
        filepath = os.path.join(self.audio_dir, filename)
        with open(filepath, "wb") as f:
            f.write(synth_resp.content)

        return f"/static/audio/{filename}"