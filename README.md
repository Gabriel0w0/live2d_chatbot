# Live2D Chatbot

A cute and interactive Live2D virtual character chatbot powered by:
- Live2D Cubism animation
- VOICEVOX for Japanese text-to-speech (offline TTS)
- Ollama / LangChain for local LLM-based interaction

## Features

- 💬 Live2D character with expressive emotional feedback
- 🗣️ VOICEVOX local speech synthesis with character-specific voices
- 🧠 Local LLM memory and response using Ollama + LangChain
- 🎀 Floating web UI with chat toggle and animated elements
- ⚡  Works fully offline (after setup)

## System Architecture
```bash
User ── Frontend (Live2D + UI) ── Flask Backend ── LangChain + Ollama
                                     │
                                     └─ VOICEVOX (TTS)
```
## Usage
### 1. Install Ollama (Required)
Download and install Ollama:  
-> [https://ollama.com/download/linux](https://ollama.com/download/linux)  

### 2. Backend Setup
```bash
# Install Python dependencies
pip install -r requirements.txt
```
### 3. VOICEVOX Setup
```bash
#for Linux,MacOS
docker run -d --name voicevox_engine -p 50021:50021 voicevox/voicevox_engine 
```
```bash
#for Windows
docker pull voicevox/voicevox_engine:nvidia-latest
docker run --rm --gpus all -p '127.0.0.1:50021:50021' voicevox/voicevox_engine:nvidia-latest 
```
### 4. Frontend
```bash
Frontend is built with HTML, CSS, and JavaScript (canvas-based layout).
Simply open index.html in your browser after starting the backend.
```
### 5. Start Flask backend
```bash
python run.py
```


## Requirements
*	Python 3.10+
*	Docker (for VOICEVOX)
*	VOICEVOX Engine (Japanese TTS)
*	Live2D Cubism SDK for Web
*	A local LLM model via Ollama

## Notes
*	The Live2D model is for non-commercial, internal display only.
*	VOICEVOX-generated audio must follow the voice library terms of use.

## Legal & Terms of Use
*	This project is for academic research and personal learning purposes only. Commercial use is prohibited.
*	VOICEVOX software terms: https://voicevox.hiroshiba.jp/
*	VOICEVOX allows both commercial and non-commercial usage, but redistribution of the software or reverse engineering is prohibited. Audio usage must credit VOICEVOX and follow the respective library’s rules.
*	Live2D sample models are © Live2D Inc. and used under their terms: https://www.live2d.com/eula/live2d-sample-model-terms_cn.html

## Emotion Tags

When replying, the chatbot may output one of the following emotion markers to drive Live2D expressions:
*	[emotion:joy] – happy
*	[emotion:sad] – sad
*	[emotion:angry] – angry
*	[emotion:neutral] – calm
*	[emotion:cute] – playful or sweet
*	[emotion:shy] – shy or bashful

## License
```
Source code: MIT
Voice and model assets: Follow respective licenses and terms as noted above.
```