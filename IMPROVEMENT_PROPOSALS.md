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

## 2. LLM Controller Robustness & Context Formatting [COMPLETED]

### Current Issues
1. **Fragile JSON Extraction (`llm_player/controller.py`):**
   - Directly calls `json.loads(response_str)`.
   - When modern LLMs wrap output in markdown fences (````json ... ````) or include conversational preambles, parsing crashes.
   - The retry mechanism (3 attempts) blindly repeats the exact same prompt with no error feedback.
2. **Context Serialization Bug [RESOLVED]:**
   - In `_build_status_prompt()`:
     ```python
     visible_log = "\n".join([f"- {log_entry.message}" for log_entry in player.logs])
     ```
   - Since `LogEntry.message` is stored as a dictionary `{"en": "...", "zh": "..."}`, LLMs received raw Python dictionary string representations (`"- {'en': '...', 'zh': '...'}"`) instead of clean localized text.
   - **Fixed:** Added `LogEntry.get_text(language)` and updated prompt builders to deliver clean language-matched strings.
3. **Hardcoded Fallbacks [RESOLVED]:**
   - `RandomController.get_speech()` always output Chinese (`"我是AI玩家。我在努力寻找狼人。"`) regardless of the game language configuration.

### Proposed Improvements
- [x] Implement markdown fence stripping, regex JSON extraction, and balanced brace scanner (`extract_json()`).
- [x] Provide corrective error feedback to the LLM upon decode failure in subsequent retry attempts.
- [x] Extract localized text matching `controller.language` when building prompt contexts (`LogEntry.get_text()`).
- [x] Localize fallback speeches in `RandomController` according to controller or game language.

---

## 3. Log System, Memory Synchronization & Information Privacy [COMPLETED]

### Issues Resolved
1. **Dusk Reflection Race Condition (Night Amnesia):**
   - Previously, `DayEndState` cleared `player.logs` immediately and launched background summarization without waiting. AI players acting on Night 2 had empty logs and stale memories.
   - **Fixed (Option B):** Implemented synchronized parallel summarization with a bounded barrier (`concurrent.futures.wait`). Day logs are only purged after successful summarization, with graceful fallback to retain raw logs if LLM calls timeout.
2. **AI Thought Privacy in Live Play:**
   - Enforced privacy in `_is_visible()` so `LogType.THOUGHT` is never leaked to human players during matches, while preserving all thoughts in `game_log` and JSONL archives for post-game debriefing and evaluation.
   - Added `PLAYER_THINKING` and `PLAYER_DONE_THINKING` events to power card animation indicators without revealing thought text.
3. **Web Controller Log Delivery & Slicing:**
   - Connected `game_instance.add_log_listener(web_controller.add_log)` so web players reliably receive initial and live logs.
   - Replaced raw log slicing with a synchronized `visible_logs` queue to prevent duplicate or skipped entries during long-polling.
4. **Single Source of Truth for Deaths and Votes:**
   - Added deduplication to `record_death()` and unified domain event dispatches (`PlayerDied`, `PlayerVoted`).
   - Covered all behaviors in `test_logging_system.py`.

---

## 4. Dependency Decoupling & Server Startup Performance [COMPLETED]

### Current Issues
- `requirements.txt` only declared:
  ```txt
  fastapi
  uvicorn
  openai
  ```
- **Missing packages:**
  - `web/transcriber.py` and `web/server.py` require `torch`, `transformers`, `numpy`, and `python-multipart`.
  - `simulation/simulation.py` requires `tqdm`.
- **Heavy Cold Starts:**
  - Importing `web/transcriber.py` at `web/server.py` top-level attempted to download/initialize the Whisper model and PyTorch at server start, which caused slow boot times and crashed environments without GPU/PyTorch packages.

### Proposed Improvements
- [x] Split dependencies into core and optional:
  - `requirements.txt`: `fastapi`, `uvicorn`, `pydantic`, `openai`, `python-dotenv`
  - `requirements-dev.txt`: `pytest`, `tqdm`
  - `requirements-audio.txt`: `torch`, `transformers`, `numpy`, `python-multipart`
- [x] **Lazy loading:** Moved `AudioTranscriber` import and initialization inside `/api/transcribe` and `/ws/transcribe` routes so the web server starts instantly without requiring PyTorch.

---

## 5. Web Concurrency & Session Management [COMPLETED]

### Current Issues
1. **Unbounded Blocking [RESOLVED]:**
   - In `web/controller.py`, `WebController._wait_for_input()` invoked `self.input_event.wait()` with no timeout. If a user closed the browser or disconnected, the game thread hung indefinitely.
   - **Fixed:** Added configurable timeout (default 60s) and automatic default fallback actions with system event notifications.
2. **Memory Leaks [RESOLVED]:**
   - `GameManager.active_games` stored sessions permanently in memory with no expiration or cleanup mechanism.
   - **Fixed:** Added `last_accessed_at` timestamps, `touch()`, and TTL eviction via `cleanup_expired_games()`.
3. **Dead Protocol Boilerplate [RESOLVED]:**
   - `web/server.py` WebSocket endpoints now safely coexist with HTTP polling; `UIEventHandler` broadcasts cleanly, while transcription routes handle missing ML dependencies gracefully.

### Proposed Improvements
- [x] Add timeouts (e.g., 60 seconds) to `_wait_for_input()`. On timeout, choose a sensible default action (e.g., abstain or random choice) to keep the game alive.
- [x] Add a session TTL / eviction policy in `GameManager` to prune finished or abandoned games.
- [x] Harmonize real-time WebSocket contracts with HTTP polling mechanisms and test concurrency.

---

## 6. Game Logic Consistency & Automated Testing [COMPLETED]

### Current Issues & Progress
1. **Subclass Polymorphism Discrepancy [FIXED]:**
   - In `game/states/*`: checks `isinstance(p.role, Werewolf)` (correctly includes `BlackWerewolfKing`).
   - In `game/handlers/night_handlers.py`: updated from `p.role.name == "Werewolf"` to `isinstance(p.role, Werewolf)`.
2. **Broken Test Script [FIXED]:**
   - [x] Fixed `reproduce_issue.py` missing positional argument `game` in `SheriffVoteState` and `TieVoteState`. Both tie vote tests pass.
3. **Automated Verification [COMPLETED]:**
   - [x] Added `test_hybrid_architecture.py` verifying end-to-end event bus publication from State Machine.
   - [x] Established a full `tests/` directory covering:
     - Win condition triggers (equal living werewolves vs villagers; all werewolves dead).
     - Witch antidote vs Guard protection conflicts.
     - Hunter and Black Werewolf King death trigger resolution and chained shootings.
     - Sheriff election tie-breakers and badge inheritance upon death.
     - WebController timeouts, fallbacks, and GameManager session TTL evictions.
