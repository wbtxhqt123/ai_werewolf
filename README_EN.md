# 🐺 AI Werewolf (Werewolf Social Deduction Game)

<p align="center">
  <a href="./README.md">简体中文</a> | <b>English</b>
</p>

An interactive web-based **Werewolf (Mafia)** game where you play alongside **multi-personality LLM AI agents**.
Play anytime in your browser with **English & Chinese bilingual UI**, **offline Chinese/English voice transcription (Mac & PC)**, and a **Post-Game AI Review & Debate Hub**.

---

## ✨ Key Highlights

1. **🎭 Distinct AI Personalities**
   * Every AI player is assigned a hidden persona (**Cautious, Aggressive, Analytical, Emotional, Diplomat, Follower, Manipulative, Paranoid, Silent**).
   * AI players bluff as the Seer, coordinate night kills in werewolf chat, analyze voting patterns, and adapt to the table.
2. **🎙️ Fast Local Bilingual Voice Input (Chinese + English)**
   * Click the **🎤 Microphone button** next to the speech input or post-game chat to speak naturally in English, Chinese, or mixed speech.
   * Powered by **Alibaba SenseVoiceSmall (`int8` ONNX via `sherpa-onnx`, ~230 MB)** by default for sub-100ms CPU inference on Mac and PC, with **Faster-Whisper (`large-v3-turbo` / `small`)** also built in.
3. **🏆 Post-Game Review & AI Debate Room**
   * **🤖 AI Evaluator**: Choose between **😊 Mild**, **😐 Neutral**, or **😈 Mean (Roast)** modes after a match to get a personalized breakdown of your plays and chat with the judge.
   * **🗣️ Argue with AI Players**: Select any AI players after the game ends to question their secret night moves or daytime votes—they will reveal their true roles and debate you!
4. **📖 Full Timeline & Immersive Day/Night UI**
   * Smooth celestial sun/moon transitions, background music, live speech bubbles, and clickable seat badges (`@Player 3`) to filter any player's speeches.

---

## 🃏 Game Setups

Choose from **6-Player**, **9-Player**, or **12-Player** boards and pick any role (or Random):

| Players | 🐺 Werewolf Team | 🧑‍🌾 Good Team (Gods + Villagers) |
| :---: | :--- | :--- |
| **6 Players** | Werewolf × 2 | Seer × 1, Witch × 1, Villager × 2 |
| **9 Players** | Black Werewolf King × 1, Werewolf × 2 | Seer × 1, Witch × 1, Hunter × 1, Villager × 3 |
| **12 Players** | Black Werewolf King × 1, Werewolf × 3 | Seer × 1, Witch × 1, Hunter × 1, Guard × 1, Villager × 4 |

---

## 🚀 Quick Start (Mac / Windows / Linux)

### 1. Install Base Dependencies
Make sure you have **Python 3.9+** installed:

```bash
pip install -r requirements.txt
```

### 2. (Optional, Recommended) Enable 🎤 Voice Input
To use local speech-to-text in the game:

```bash
pip install -r requirements-audio.txt
```
> 💡 **Note**: No PyTorch or system `ffmpeg` installation is required. Before starting a game, open **⚙️ Advanced Settings**, click **⬇️ Download Model** (or **⚡ Activate Model** if cached) in the **🎙️ Voice Model** card, and watch the real-time progress bar reach `100% (✅ Ready)`. Once ready, the in-game `🎤` button will unlock.

### 3. Launch the Web Game

```bash
python main_web.py
```

Open your browser and visit:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## ⚙️ Configuring AI Models & Speech Recognition

### Option A: In the Web UI (Easiest)
1. Open `http://127.0.0.1:8000`.
2. Click **⚙️ Advanced Settings**.
3. Pick your LLM provider (**OpenAI, Doubao, Gemini, Qwen, DeepSeek, or Custom OpenAI-compatible URL**) and enter your API Key.

### Option B: Via `.env` File
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

```env
# Optional LLM API Key
OPENAI_API_KEY=sk-xxxx

# Optional Speech-to-Text (ASR) Settings
ASR_BACKEND=sensevoice           # "sensevoice" (default, ~230MB int8 ONNX) or "faster-whisper"
ASR_WHISPER_MODEL=large-v3-turbo # Used when ASR_BACKEND=faster-whisper
ASR_DEVICE=auto                  # "auto", "cpu", "cuda", or "coreml"
```

---

## 📄 License

Licensed under the [MIT License](LICENSE).
