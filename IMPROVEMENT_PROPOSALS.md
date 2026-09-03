# Werewolf Game Engine: Improvement Proposals & Architectural Roadmap

This document outlines key technical debts, functional bugs, architectural inconsistencies, and recommended improvements identified across the codebase.

---

## 1. Architecture: Reconciling State Machine & Event-Driven Systems [COMPLETED]

### Current Issue
The codebase was split between two competing paradigms:
- **Active State Machine (`game/states/*`):** Directly controls turns, prompts players, manages phase progression, and checks win conditions.
- **Partial Event-Driven Architecture (`game/events/*`, `game/handlers/*`, `game/event_bus.py`):** An unfinished migration inspired by `architecture_proposal.md` and `refactoring_plan.md`.

### Critical Bugs Resolved
- [x] **Import Crash in `main.py`:** Fixed entry point mapping (`from game.main import main`).
- [x] **Double-execution bug in CLI (`game/main.py`):** Removed duplicate `event_bus.publish(GameStarted())` before `game.start()`.
- [x] **Competing Handlers in `game/game.py`:** Removed legacy flow-driving handlers from `_register_handlers()`.
- [x] **Hybrid Architecture Implemented:**
  - State Machine has exclusive authority over game progression, phases, and rules.
  - State Machine emits notification domain events to `EventBus` (`GameStarted`, `PhaseChanged`, `PlayerDied`, `PlayerVoted`, `ExecutionComplete`, `GuardProtect`, `WerewolfTargetSelected`, `WitchSave`, `WitchPoison`, `SeerCheckResult`, `GameOver`).

---

## 2. LLM Controller Robustness & Context Formatting [PENDING]

### Current Issues
1. **Fragile JSON Extraction (`llm_player/controller.py`):**
   - Directly calls `json.loads(response_str)`.
   - When modern LLMs wrap output in markdown fences (````json ... ````) or include conversational preambles, parsing crashes.
   - The retry mechanism (3 attempts) blindly repeats the exact same prompt with no error feedback.
2. **Context Serialization Bug:**
   - In `_build_status_prompt()`:
     ```python
     visible_log = "\n".join([f"- {log_entry.message}" for log_entry in player.logs])
     ```
   - Since `LogEntry.message` is stored as a dictionary `{"en": "...", "zh": "..."}`, LLMs receive raw Python dictionary string representations (`"- {'en': '...', 'zh': '...'}"`) instead of clean localized text.
3. **Hardcoded Fallbacks:**
   - `RandomController.get_speech()` always outputs Chinese (`"我是AI玩家。我在努力寻找狼人。"`) regardless of the game language configuration.

### Proposed Improvements
- [ ] Implement markdown fence stripping and regex JSON extraction (`re.search(r"\{[\s\S]*\}", text)`).
- [ ] Provide feedback to the LLM upon decode failure (e.g., "Your previous output was not valid JSON. Please return strictly valid JSON.").
- [ ] Extract localized text matching `controller.language` when building prompt contexts.
- [ ] Localize fallback speeches in `RandomController`.

---

## 3. Dependency Decoupling & Server Startup Performance [PENDING]

### Current Issues
- `requirements.txt` only declares:
  ```txt
  fastapi
  uvicorn
  openai
  ```
- **Missing packages:**
  - `web/transcriber.py` and `web/server.py` require `torch`, `transformers`, `numpy`, and `python-multipart`.
  - `simulation/simulation.py` requires `tqdm`.
- **Heavy Cold Starts:**
  - Importing `web/transcriber.py` at `web/server.py` top-level attempts to download/initialize the Whisper model and PyTorch at server start, which causes slow boot times and crashes environments without GPU/PyTorch packages.

### Proposed Improvements
- [ ] Split dependencies into core and optional:
  - `requirements.txt`: `fastapi`, `uvicorn`, `pydantic`, `openai`, `python-dotenv`
  - `requirements-dev.txt`: `pytest`, `tqdm`
  - `requirements-audio.txt`: `torch`, `transformers`, `numpy`, `python-multipart`
- [ ] **Lazy loading:** Move the `AudioTranscriber` import and initialization inside the `/api/transcribe` route so the web UI starts instantly without requiring PyTorch.

---

## 4. Web Concurrency & Session Management [PENDING]

### Current Issues
1. **Unbounded Blocking:**
   - In `web/controller.py`, `WebController._wait_for_input()` invokes `self.input_event.wait()` with no timeout. If a user closes the browser or disconnects, the game thread hangs indefinitely.
2. **Memory Leaks:**
   - `GameManager.active_games` stores sessions permanently in memory with no expiration or cleanup mechanism.
3. **Dead Protocol Boilerplate:**
   - `web/server.py` includes WebSocket endpoint code, but the frontend (`web/static/js/app.js`) exclusively uses HTTP polling (`/api/game/{game_id}/state`).

### Proposed Improvements
- [ ] Add timeouts (e.g., 60 seconds) to `_wait_for_input()`. On timeout, choose a sensible default action (e.g., abstain or random choice) to keep the game alive.
- [ ] Add a session TTL / eviction policy in `GameManager` to prune finished or abandoned games.
- [ ] Either adopt WebSockets end-to-end to replace heavy HTTP polling, or remove the unused WebSocket boilerplates.

---

## 5. Game Logic Consistency & Automated Testing [IN PROGRESS]

### Current Issues & Progress
1. **Subclass Polymorphism Discrepancy:**
   - In `game/states/*`: checks `isinstance(p.role, Werewolf)` (correctly includes `BlackWerewolfKing`).
   - In `game/handlers/night_handlers.py`: checks `p.role.name == "Werewolf"`, which accidentally excludes `BlackWerewolfKing`.
2. **Broken Test Script [FIXED]:**
   - [x] Fixed `reproduce_issue.py` missing positional argument `game` in `SheriffVoteState` and `TieVoteState`. Both tie vote tests pass.
3. **Automated Verification [IN PROGRESS]:**
   - [x] Added `test_hybrid_architecture.py` verifying end-to-end event bus publication from State Machine.
   - [ ] Establish a full `tests/` directory with `pytest` covering:
     - Win condition triggers (equal living werewolves vs villagers; all werewolves dead).
     - Witch antidote vs Guard protection conflicts.
     - Hunter and Black Werewolf King death trigger resolution.
     - Sheriff election tie-breakers and badge inheritance.
