# Subsystems Guide: AI, Backend, and Web Frontend

This guide covers the three main application tiers that build on top of the core Werewolf engine: LLM AI Agents, FastAPI Backend, and the Web Interface.

---

## 1. AI Player Architecture (`llm_player/`)

AI players are driven by `LLMController` instances communicating with OpenAI-compatible or Groq endpoints.

### 1.1 Core Responsibilities
- **Context Construction:** Gathers private and public game history tailored to the player's role, language (`en` or `zh`), and active personality.
- **Robust JSON Extraction:** Strips Markdown code fences, conversational preambles, and extracts structured actions using robust regex and balanced-brace parsers.
- **Error Feedback Loop:** If an LLM response fails validation, retry attempts inject explicit corrective prompts back into the dialogue context.
- **Memory & Dusk Reflection:** At the end of each day (`DayEndState`), LLM players compress raw conversation logs into persistent memory summaries (`llm_player/prompts/{lang}/memory/summarize_day.txt`).

### 1.2 Personality & Prompt System
Prompts are organized under `llm_player/prompts/{lang}/`:
- **`characteristic/`**: Personalities such as `analytical`, `aggressive`, `cautious`, `diplomat`, `emotional`, `manipulative`, `paranoid`, `random`, and `silent`.
- **`action/`**: Prompts for night skills (Guard, Werewolf, Witch, Seer), day speeches, sheriff voting, and last words.
- **`evaluation/`**: Post-game critique personas (`mild`, `neutral`, `mean`) and interactive debate (`chat`).

---

## 2. Web Backend (`web/`)

The web tier exposes REST and WebSocket APIs using **FastAPI** and **Uvicorn**, bridging human users with the asynchronous game engine.

### 2.1 Key Components
- **`web/server.py`:** FastAPI application managing session lifecycle, REST endpoints, and static file serving.
- **`web/controller.py`:** `WebController` implements the engine's `Controller` interface. It translates engine turn requests into pending frontend actions, pushes logs to the player's queue, and holds an event latch with timeout fallback.
- **`GameManager`:** In-memory registry for active games. Tracks session activity timestamps and evicts expired or abandoned games via TTL policies.

### 2.2 Primary API Endpoints
- `POST /api/game/start`: Creates and initializes a new game with human role preferences, seat selection (`user_seat`: `1..N` or `"random"`), and player count.
- `GET /api/game/{game_id}/state`: Polls the current phase, player status, living count, human seat identifier (`human_player`), spectator status (`spectator_mode`), and pending input prompt.
- `POST /api/game/action`: Submits human actions (votes, speeches, Sheriff withdrawal, night skill targets).
- `POST /api/game/spectate`: Enables God-View spectator mode for an eliminated human player once they have no pending actions.
- `POST /api/llm/test`: Validates the configured LLM provider, model, and API key before starting a game.
- `GET /api/game/{game_id}/player/{player_name}/operations`: Returns chronological role-specific operation history and public shot logs.
- `POST /api/game/evaluate`: Triggers post-game LLM critique using the chosen tone persona.
- `POST /api/game/evaluation/chat`: Allows the player to argue and debate their game decisions with the evaluator.
- `POST /api/game/argue`: Post-game multi-AI debate room where selected AI players defend their in-game actions in character.

---

## 3. Web Frontend (`web/static/`)

The frontend is a zero-dependency, single-page application built with vanilla HTML, modern CSS, and JavaScript.

### 3.1 Design System: "Playful Suspense"
- **Dynamic Day/Night Theme:** Background gradients and lighting dynamically transition between daytime sky tones and nighttime mystery palettes based on `gameState.phase`.
- **Radial Player Layout:** Players are arranged in a responsive circle with visual cues for living status, sheriff badge, current speaker, and target selection affordances.
- **Real-Time Turn Countdown:** 2-minute circular countdown timer with animated progress indicators and urgency pulse states.
- **Modals & Chronicle:** Dedicated views for game setup, detailed voting matrices, death obituaries, chronological operation timelines, and AI performance evaluation.
