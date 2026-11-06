# 🐺 AI Werewolf (Werewolf Social Deduction Game)

<p align="center">
  <a href="./README.md">简体中文</a> | <b>English</b>
</p>

An interactive web-based **Werewolf (Mafia)** game where you play alongside **multi-personality LLM AI agents**.
Play anytime in your browser with **English & Chinese bilingual UI**, **offline Chinese/English voice transcription (Mac & PC)**, and a **Post-Game AI Review & Debate Hub**.

---

## ✨ Key Highlights

1. **🎭 Distinct AI Personalities & Authentic Werewolf Mechanics**
   * Every AI player is assigned a hidden persona (**Cautious, Aggressive, Analytical, Emotional, Diplomat, Follower, Manipulative, Paranoid, Silent**).
   * AI players bluff as the Seer, **withdraw from the Sheriff race (`退水` / Candidate Withdrawal)** when appropriate, coordinate night kills in werewolf chat (with human wolves retaining final kill-target priority), analyze voting patterns, and adapt to the table.
2. **🎙️ Fast Local Bilingual Voice Input (Chinese + English)**
   * Click the **🎤 Microphone button** next to the speech input or post-game chat to speak naturally in English, Chinese, or mixed speech.
   * Powered by **Alibaba FunASR Paraformer-Large (`int8` ONNX via `sherpa-onnx`, ~220 MB)** by default for sub-100ms inference with Werewolf jargon correction, with **Faster-Whisper (`large-v3-turbo` via MLX Metal / CTranslate2)** and **SenseVoiceSmall** also built in.
3. **🏆 Post-Game Review & AI Debate Room**
   * **🤖 AI Evaluator**: Choose between **😊 Mild**, **😐 Neutral**, or **😈 Mean (Roast)** modes after a match to get a personalized breakdown of your plays and chat with the judge.
   * **🗣️ Argue with AI Players**: Select any AI players after the game ends to question their secret night moves or daytime votes—they will reveal their true roles and debate you!
4. **📖 Full Timeline, Quick Suspect Tags & Dead-Player Spectator Mode**
   * **🏷️ Quick Suspect / Role Notepad**: Click the `🏷️` tag on any AI player's card to cycle through identity guesses (`🐺 Wolf?`, `🔮 Seer?`, `💧 Good`, `🛡️ God?`).
   * **👻 Spectator God View & Fast-Forward**: If you are eliminated early, click **👁️ God View** to reveal all player roles, night actions, and live AI inner thoughts, or click **⚡ Fast-Forward** to watch the rest of the match at max speed.
   * **🎲 Seat Selection / Random Seat**: Choose Seat 1..N or a Random Seat before starting, and test your LLM API connection directly in **⚙️ Advanced Settings**.

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

## 📅 Development Timeline (Changelog)

* **2026-11** — Sheriff withdrawal, spectator god view, human-werewolf kill priority, free/random seat picking, suspect tag pad, in-game match history reader, structured Chain-of-Thought with werewolf meta-gaming, and a new **Paraformer-Large** ASR engine (GPU/CoreML accelerated).
* **2026-10-26** — README update with in-game screenshots.
* **2026-10-23** — Dual offline ASR engines (**SenseVoiceSmall & Faster-Whisper**) with download/activation progress in Advanced Settings; persisted settings; post-game review hub (multi-turn evaluator chat + multi-AI debate room); Black Werewolf King revealed to the pack.
* **2026-10-16 ~ 21** — Full EN/CN localization of UI, logs and AI prompts; gunshot/night-death privacy and spotlight chat cards; vote-weighted win conditions, chained shot/last-words order fixes, RuleOracle simulator.
* **2026-09-07** — Secret voting, blind sheriff election, sheriff visual glow.
* **2026-09-04 ~ 06** — Day/night BGM and celestial transition animations, cartoon pop modals, configurable speech countdown, unified operation/vote timeline log, repo structure & docs cleanup.

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
ASR_BACKEND=paraformer           # "paraformer" (default, ~220MB int8 ONNX), "faster-whisper", or "sensevoice"
ASR_WHISPER_MODEL=large-v3-turbo # Used when ASR_BACKEND=faster-whisper
ASR_DEVICE=auto                  # "auto", "cpu", "cuda", or "coreml"
```

---

## 📄 License

Licensed under the [MIT License](LICENSE).
