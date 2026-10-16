import threading
import time
import uvicorn
import random
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import asyncio
from pydantic import BaseModel
from typing import Any, List, Optional, Dict
import shutil
import os
import tempfile

from game.game import Game
from game.controllers import RandomController
from llm_player.controller import LLMController, LLMClient
from llm_player.evaluator import GameEvaluator
from game.log import LogEntry
from game.history import GameHistory
from web.controller import WebController
from game.handlers.ui_handler import UIEventHandler
from game.events.day_events import PlayerDied
from game.events.night_events import SeerCheckResult

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Global state
class GameSession:
    """Represents an active game session.

    This class encapsulates all the objects associated with a single game instance,
    including the game logic, the web controller for the human player, the game
    thread, and an optional evaluator. Tracks creation and access timestamps for TTL.
    """
    def __init__(self, game_id: str, game_instance: Game, web_controller: WebController, game_thread: threading.Thread, llm_config: Optional[dict] = None):
        self.game_id = game_id
        self.game_instance = game_instance
        self.web_controller = web_controller
        self.game_thread = game_thread
        self.game_evaluator: GameEvaluator | None = None
        self.llm_config = llm_config or {}
        self.created_at = time.time()
        self.last_accessed_at = time.time()

    def touch(self):
        """Updates last accessed timestamp."""
        self.last_accessed_at = time.time()

    def is_finished(self) -> bool:
        """Determines if the game is over or the thread has terminated."""
        if self.game_instance and getattr(self.game_instance, "state", None):
            from game.states.special_states import GameOverState
            if isinstance(self.game_instance.state, GameOverState):
                return True
        return not self.game_thread.is_alive()

class GameManager:
    """Manages all active game sessions on the server with TTL eviction.

    This thread-safe class is responsible for creating, retrieving, and removing
    game sessions. It tracks session activity and prunes abandoned or finished games.
    """
    def __init__(self):
        self.active_games: Dict[str, GameSession] = {}
        self.lock = threading.Lock()

    def create_game(self, game_instance: Game, web_controller: WebController, game_thread: threading.Thread, llm_config: Optional[dict] = None) -> str:
        """Creates a new game session and returns its ID, pruning expired sessions first."""
        self.cleanup_expired_games()
        game_id = str(uuid.uuid4())
        session = GameSession(game_id, game_instance, web_controller, game_thread, llm_config=llm_config)
        with self.lock:
            self.active_games[game_id] = session
        return game_id

    def get_game(self, game_id: str) -> GameSession | None:
        """Retrieves a game session by its ID and refreshes its last access time."""
        with self.lock:
            session = self.active_games.get(game_id)
            if session:
                session.touch()
            return session

    def remove_game(self, game_id: str):
        """Removes a game session from the manager."""
        with self.lock:
            if game_id in self.active_games:
                del self.active_games[game_id]

    def cleanup_expired_games(self, active_ttl_seconds: float = 7200.0, finished_ttl_seconds: float = 600.0) -> list[str]:
        """Prunes finished or abandoned game sessions to prevent memory leaks.

        Args:
            active_ttl_seconds: Max idle duration for active games (default 2 hours).
            finished_ttl_seconds: Max retention for completed games (default 10 minutes).

        Returns:
            List of pruned game_ids.
        """
        now = time.time()
        expired_ids = []
        with self.lock:
            for game_id, session in list(self.active_games.items()):
                idle_time = now - session.last_accessed_at
                is_done = session.is_finished()
                if (is_done and idle_time > finished_ttl_seconds) or (idle_time > active_ttl_seconds):
                    expired_ids.append(game_id)
                    del self.active_games[game_id]
        return expired_ids

game_manager = GameManager()
game_history = GameHistory()

class ActionRequest(BaseModel):
    """Defines the structure for a player action request."""
    game_id: str
    action: Any

class StartGameRequest(BaseModel):
    """Defines the structure for a request to start a new game."""
    num_players: int
    user_role: str
    user_avatar: Optional[str] = "👤"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = None
    player_configs: Optional[dict] = None
    language: str = "zh"
    turn_timeout: Optional[float] = 120.0

class UpdateSettingsRequest(BaseModel):
    """Defines the structure for updating runtime game settings."""
    game_id: str
    turn_timeout: Optional[float] = None

class EvaluationRequest(BaseModel):
    """Defines the structure for a request to evaluate a completed game."""
    game_id: str
    mode: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = None
    language: str = "zh"

class ChatRequest(BaseModel):
    """Defines the structure for a chat message within an evaluation session."""
    game_id: str
    message: str

class GameStateResponse(BaseModel):
    """Defines the structure of the game state response sent to the client."""
    logs: List[dict]
    input_required: Optional[dict]
    game_active: bool
    players: List[dict] = []
    game_id: Optional[str] = None

def run_game_thread(game_instance: Game):
    """The target function for the game thread. Simply starts the game loop."""
    game_instance.start()

@app.get("/favicon.ico")
async def favicon():
    return Response(content="", media_type="image/x-icon")

@app.get("/lobby")
async def get_lobby():
    return FileResponse("web/static/index.html")

@app.get("/")
async def read_root():
    return FileResponse("web/static/index.html")

@app.get("/game")
async def read_game():
    return FileResponse("web/static/index.html")

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, websocket: WebSocket):
        self.loop = asyncio.get_running_loop()
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

websocket_manager = WebSocketManager()

@app.websocket("/ws/{game_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_name: str):
    await websocket_manager.connect(websocket)
    session = game_manager.get_game(game_id)
    if session:
        player = session.game_instance.get_player_by_name(player_name)
        if player and isinstance(player.controller, WebController):
            player.controller.websocket = websocket

    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)


@app.post("/api/game/start")
async def start_game(request: StartGameRequest):
    """Creates and starts a new game based on the provided configuration.

    This endpoint sets up the human player with a `WebController` and populates the
    rest of the game with AI players. It supports both a global LLM configuration
    and per-player configurations.
    """
    timeout = float(request.turn_timeout) if request.turn_timeout and request.turn_timeout > 0 else 120.0
    web_controller = WebController(timeout=timeout)
    
    players_with_controllers = {
        "Player 1": web_controller,
    }
    
    default_llm_client = None
    if request.api_key:
        default_llm_client = LLMClient(
            api_key=request.api_key,
            base_url=request.base_url,
            model=request.model_name,
            provider=request.provider
        )

    personalities = ["cautious", "aggressive", "analytical", "emotional", "random"]
    for i in range(request.num_players - 1):
        player_name = f"Player {i+2}"
        
        player_config = None
        if request.player_configs and player_name in request.player_configs:
            player_config = request.player_configs[player_name]
        
        if player_config and "api_key" not in player_config and request.api_key:
            player_config["api_key"] = request.api_key

        if player_config and player_config.get("api_key"):
            personality = personalities[i % len(personalities)]
            players_with_controllers[player_name] = LLMController(
                personality=personality,
                llm_config=player_config,
                language=request.language
            )
        elif default_llm_client:
            personality = personalities[i % len(personalities)]
            players_with_controllers[player_name] = LLMController(
                personality=personality,
                llm_client=default_llm_client,
                language=request.language
            )
        else:
            players_with_controllers[player_name] = RandomController(language=request.language)

    role_to_assign = request.user_role
    if role_to_assign == "Random":
        role_to_assign = None

    game_instance = Game(players_with_controllers, player_role=role_to_assign, language=request.language)
    game_instance.add_log_listener(web_controller.add_log)
    
    try:
        websocket_manager.loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    ui_event_handler = UIEventHandler(game_instance, websocket_manager)
    game_instance.event_bus.subscribe(PlayerDied, ui_event_handler.handle_event)
    game_instance.event_bus.subscribe(SeerCheckResult, ui_event_handler.handle_event)

    game_thread = threading.Thread(target=run_game_thread, args=(game_instance,))
    game_thread.start()

    session_llm_config = {
        "api_key": request.api_key,
        "base_url": request.base_url,
        "model_name": request.model_name,
        "provider": request.provider,
    }
    game_id = game_manager.create_game(game_instance, web_controller, game_thread, llm_config=session_llm_config)

    return {"message": "Game started", "game_id": game_id}

@app.get("/api/game/{game_id}/state")
async def get_game_state(game_id: str, last_log_index: int = 0):
    """Provides the current state of a game to the client.

    This endpoint is used for long-polling by the frontend. It returns new logs since
    the last request, information about whether player input is currently required,
    and the overall status of the game and its players.
    """
    session = game_manager.get_game(game_id)

    if not session:
        return GameStateResponse(logs=[], input_required=None, game_active=False, players=[], game_id=None)

    web_controller = session.web_controller
    game_thread = session.game_thread
    game_instance = session.game_instance

    logs = web_controller.get_logs(last_log_index)
    input_req = web_controller.pending_request
    is_active = game_thread.is_alive() if game_thread else False

    players_data = []
    if game_instance:
        reveal_all_roles = (not is_active) or bool(game_instance.winner)
        for p in game_instance.players:
            visible_role = (p.role.name if p.role else "Unknown") if (reveal_all_roles or p.name == "Player 1") else "Unknown"
            players_data.append({
                "name": p.name,
                "role": visible_role,
                "is_alive": p.is_alive,
                "is_sheriff": p.is_sheriff,
                "is_sheriff_candidate": getattr(p, 'is_sheriff_candidate', False),
                "is_tie": getattr(p, 'is_tie', False)
            })
        
        if not is_active and game_instance.winner:
            save_game_history_if_ended(session)

    return GameStateResponse(
        logs=logs,
        input_required=input_req,
        game_active=is_active,
        players=players_data,
        game_id=game_id
    )

def save_game_history_if_ended(session: GameSession):
    """Saves the game's outcome and logs to the historical record.

    This function is called when a game has concluded. It extracts the necessary
    information from the `Game` object and uses the `GameHistory` manager to persist it.
    """
    global game_history
    game_instance = session.game_instance
    if game_instance and game_instance.winner and not getattr(game_instance, "history_saved", False):
        players_info = []
        for p in game_instance.players:
            players_info.append({
                "name": p.name,
                "role": p.role.name if p.role else "Unknown",
                "is_alive": p.is_alive
            })
        
        logs_data = []
        for entry in game_instance.game_log:
            logs_data.append({
                "type": entry.log_type.name,
                "message": entry.message,
                "source": entry.source.name if entry.source else None,
                "target": entry.target.name if entry.target else None,
                "data": entry.data,
                "camps": entry.camps,
                "round": entry.day,
                "state": entry.state
            })

        game_history.add_game(
            winner=game_instance.winner,
            players=players_info,
            logs=logs_data
        )
        game_instance.history_saved = True

@app.get("/api/game/{game_id}/full_logs")
async def get_full_logs(game_id: str):
    """Retrieves the complete, player-specific logs for a given game.

    This endpoint is used for features like the "Village Chronicles," where a user can
    review the entire history of the game from each player's perspective. It iterates
    through all game logs and filters them based on each player's visibility rules.
    """
    session = game_manager.get_game(game_id)
    
    if not session:
        return {"logs": []}
        
    game_instance = session.game_instance
    is_game_over = session.is_finished() or bool(game_instance.winner)
    
    player_logs = {}
    target_players = game_instance.players if is_game_over else [p for p in game_instance.players if p.name == "Player 1"]
    
    for p in target_players:
        player_logs[p.name] = {
            "role": p.role.name if p.role else "Unknown",
            "logs": []
        }
        
    # This approach reconstructs each player's view of the game log.
    for entry in game_instance.game_log:
        for p in target_players:
            if game_instance._is_visible(entry, p):
                player_logs[p.name]["logs"].append({
                    "type": entry.log_type.name,
                    "message": entry.message,
                    "source": entry.source.name if entry.source else None,
                    "target": entry.target.name if entry.target else None,
                    "data": entry.data,
                    "camps": entry.camps,
                    "round": entry.day,
                    "state": entry.state
                })
                
    return player_logs

@app.get("/api/game/history")
async def get_game_history():
    """Returns a summary of all completed games."""
    global game_history
    return {"history": game_history.get_history_summary()}

@app.get("/api/game/history/{game_id}")
async def get_game_history_detail(game_id: int):
    """Returns the detailed logs and outcome of a specific historical game."""
    global game_history
    detail = game_history.get_game_details(game_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Game not found")
    return detail

@app.get("/api/game/{game_id}/records")
async def get_game_records(game_id: str):
    """Retrieves the vote and death records for a specific game.

    This data is used to populate the "Game Records" tab in the UI, providing a
    structured overview of key events.
    """
    session = game_manager.get_game(game_id)
    
    if not session:
        return {"votes": [], "deaths": []}
        
    game_instance = session.game_instance
    return {
        "votes": game_instance.vote_history,
        "deaths": game_instance.death
    }

@app.get("/api/game/{game_id}/player/{player_name}/operations")
async def get_player_operations(game_id: str, player_name: str):
    """
    Retrieves the operations history for a specific player in a game.
    """
    session = game_manager.get_game(game_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
        
    game_instance = session.game_instance
    is_game_over = session.is_finished() or bool(game_instance.winner)
    if not is_game_over and player_name != "Player 1":
        raise HTTPException(status_code=403, detail="Cannot view other players' operations while the game is active")

    history = game_instance.get_player_operations_history(player_name)
    return history

@app.post("/api/game/action")
async def post_action(request: ActionRequest):
    """Receives and processes an action from the human player.

    When the frontend requires input from the user (e.g., a vote or a role action),
    it sends the choice to this endpoint. The action is then passed to the
    `WebController`, which unblocks the waiting game thread.
    """
    session = game_manager.get_game(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    
    web_controller = session.web_controller
    web_controller.set_input(request.action)
    return {"status": "ok"}

@app.post("/api/game/settings")
async def update_settings(request: UpdateSettingsRequest):
    """Updates runtime settings for an active game session."""
    session = game_manager.get_game(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    if request.turn_timeout is not None and request.turn_timeout > 0:
        session.web_controller.set_timeout(request.turn_timeout)
    return {"status": "ok", "turn_timeout": session.web_controller.timeout}

@app.post("/api/game/evaluate")
async def evaluate_game(request: EvaluationRequest):
    """Initiates a post-game evaluation of the human player's performance.

    This endpoint uses the `GameEvaluator` to analyze the game logs and provide
    feedback to the player based on their role, the game's outcome, and the chosen
    evaluation mode (e.g., 'mild', 'mean').
    """
    session = game_manager.get_game(request.game_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    game_instance = session.game_instance

    human_player = None
    for p in game_instance.players:
        if p.name == "Player 1":
            human_player = p
            break
    
    if not human_player:
        raise HTTPException(status_code=400, detail="Human player not found")

    api_key = request.api_key or session.llm_config.get("api_key")
    if not api_key:
         raise HTTPException(status_code=400, detail="API Key required for evaluation")

    base_url = request.base_url or session.llm_config.get("base_url")
    model_name = request.model_name or session.llm_config.get("model_name")
    provider = request.provider or session.llm_config.get("provider")

    session.game_evaluator = GameEvaluator(
        api_key=api_key,
        language=request.language,
        base_url=base_url,
        model=model_name,
        provider=provider,
    )
    
    game_result = "Game Over"
    if game_instance.winner:
        game_result = f"Winner: {game_instance.winner}"

    logs = []
    for entry in game_instance.game_log:
        logs.append({
            "message": entry.message,
            "type": entry.log_type.name
        })

    evaluation = session.game_evaluator.evaluate(
        game_logs=logs,
        player_name=human_player.name,
        player_role=human_player.role.name if human_player.role else "Unknown",
        game_result=game_result,
        mode=request.mode
    )

    return {"evaluation": evaluation}

@app.post("/api/game/evaluation/chat")
async def evaluation_chat(request: ChatRequest):
    """Handles follow-up chat messages within an evaluation session."""
    session = game_manager.get_game(request.game_id)
    
    if not session or not session.game_evaluator:
        raise HTTPException(status_code=400, detail="No active evaluation session")
        
    reply = session.game_evaluator.chat(request.message)
    return {"reply": reply}

@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...), language: Optional[str] = None):
    """Transcribes a complete audio file uploaded by the user.

    This endpoint saves the uploaded audio file to a temporary location, uses the
    `Transcriber` to convert the speech to text, and then deletes the temporary file.
    """
    temp_filename = None
    try:
        from web.transcriber import get_transcriber
        transcriber = get_transcriber()
    except (RuntimeError, ImportError) as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        raw_ext = os.path.splitext(file.filename or "")[1]
        safe_ext = raw_ext if raw_ext and raw_ext.isalnum() or (raw_ext.startswith(".") and raw_ext[1:].isalnum()) else ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=safe_ext) as tmp:
            temp_filename = tmp.name
            shutil.copyfileobj(file.file, tmp)
        
        text = await asyncio.to_thread(transcriber.transcribe, temp_filename, language=language)
        
        os.remove(temp_filename)
        temp_filename = None
        
        return {"text": text}
    except Exception as e:
        if temp_filename and os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """Handles real-time audio transcription over a WebSocket connection.

    This endpoint receives audio chunks from the client, appends them to a temporary
    file, and transcribes the audio upon receiving a 'process' or 'stop' command.
    This allows for a more interactive speech-to-text experience.
    """
    await websocket.accept()
    try:
        from web.transcriber import get_transcriber
        transcriber = get_transcriber()
    except (RuntimeError, ImportError) as e:
        await websocket.close(code=1011, reason=str(e))
        return
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        temp_filename = tmp.name
    language = None
    
    try:
        while True:
            message = await websocket.receive()
            
            if "bytes" in message:
                data = message["bytes"]
                with open(temp_filename, "ab") as f:
                    f.write(data)
                
            elif "text" in message:
                text = message["text"]
                if text.startswith("language:"):
                    language = text.split(":")[1]
                elif text == "process":
                    if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
                        result = await asyncio.to_thread(transcriber.transcribe, temp_filename, language=language)
                        await websocket.send_json({"text": result, "is_final": False})
                elif text == "stop":
                    if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
                        result = await asyncio.to_thread(transcriber.transcribe, temp_filename, language=language)
                        await websocket.send_json({"text": result, "is_final": True})
                    break
                    
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
