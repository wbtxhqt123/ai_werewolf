import threading
import time
import uvicorn
import random
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import asyncio
from pydantic import BaseModel
from typing import Any, List, Optional, Dict
import shutil
import os
import json
import tempfile

from game.game import Game
from game.controllers import RandomController
from llm_player.controller import LLMController, LLMClient
from llm_player.evaluator import GameEvaluator, PostGameDebateRoom
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
        self.game_evaluator: Optional[GameEvaluator] = None
        self.debate_room: Optional[PostGameDebateRoom] = None
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

    def get_game(self, game_id: str) -> Optional[GameSession]:
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
    user_seat: Optional[Any] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = None
    player_configs: Optional[dict] = None
    language: str = "zh"
    turn_timeout: Optional[float] = None

class SpectateRequest(BaseModel):
    """Defines the structure for enabling dead-player spectator (God View) mode."""
    game_id: str

class LLMTestRequest(BaseModel):
    """Defines the structure for testing an LLM provider connection before starting a game."""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = None
    language: str = "zh"

class UpdateSettingsRequest(BaseModel):
    """Defines the structure for updating runtime game settings."""
    game_id: str
    turn_timeout: Optional[float] = None
    language: Optional[str] = None

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

class ArgueRequest(BaseModel):
    """Defines the structure for a post-game multi-AI argument request."""
    game_id: str
    selected_players: List[str]
    message: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = None
    language: str = "zh"

class GameStateResponse(BaseModel):
    """Defines the structure of the game state response sent to the client."""
    logs: List[dict]
    input_required: Optional[dict]
    game_active: bool
    players: List[dict] = []
    game_id: Optional[str] = None
    winner: Optional[str] = None
    human_player: str = "Player 1"
    spectator_mode: bool = False


def _get_human_player(game_instance: Optional[Game]):
    """Finds the human-controlled player in the game (defaults to Player 1 if none is marked is_human)."""
    if not game_instance or not getattr(game_instance, "players", None):
        return None
    for p in game_instance.players:
        if getattr(p.controller, "is_human", False):
            return p
    return game_instance.get_player_by_name("Player 1") or game_instance.players[0]


def _get_human_player_name(game_instance: Optional[Game]) -> str:
    hp = _get_human_player(game_instance)
    return hp.name if hp else "Player 1"

def run_game_thread(game_instance: Game):
    """The target function for the game thread. Starts the game loop and persists history on completion."""
    game_instance.start()
    save_game_history_for_instance(game_instance)

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
    timeout = float(request.turn_timeout) if request.turn_timeout and request.turn_timeout > 0 else None
    web_controller = WebController(timeout=timeout)

    # Resolve human player's seat number (1..num_players). Defaults to 1 if omitted for backwards compatibility.
    total_seats = max(2, int(request.num_players))
    chosen_seat = 1
    if request.user_seat is not None:
        if isinstance(request.user_seat, str) and request.user_seat.strip().lower() == "random":
            chosen_seat = random.randint(1, total_seats)
        else:
            try:
                seat_int = int(request.user_seat)
                if seat_int == 0:
                    chosen_seat = random.randint(1, total_seats)
                elif 1 <= seat_int <= total_seats:
                    chosen_seat = seat_int
            except (ValueError, TypeError):
                chosen_seat = 1

    human_player_name = f"Player {chosen_seat}"
    players_with_controllers: Dict[str, Any] = {}
    
    default_llm_client = None
    if request.api_key:
        default_llm_client = LLMClient(
            api_key=request.api_key,
            base_url=request.base_url,
            model=request.model_name,
            provider=request.provider
        )

    personalities = [
        "cautious",
        "aggressive",
        "analytical",
        "emotional",
        "diplomat",
        "follower",
        "manipulative",
        "paranoid",
        "silent",
    ]
    random.shuffle(personalities)
    ai_idx = 0
    for seat_num in range(1, total_seats + 1):
        player_name = f"Player {seat_num}"
        if seat_num == chosen_seat:
            players_with_controllers[player_name] = web_controller
            continue

        player_config = None
        if request.player_configs and player_name in request.player_configs:
            player_config = request.player_configs[player_name]
        
        if player_config and "api_key" not in player_config and request.api_key:
            player_config["api_key"] = request.api_key

        if player_config and player_config.get("api_key"):
            personality = personalities[ai_idx % len(personalities)]
            players_with_controllers[player_name] = LLMController(
                personality=personality,
                llm_config=player_config,
                language=request.language
            )
        elif default_llm_client:
            personality = personalities[ai_idx % len(personalities)]
            players_with_controllers[player_name] = LLMController(
                personality=personality,
                llm_client=default_llm_client,
                language=request.language
            )
        else:
            players_with_controllers[player_name] = RandomController(language=request.language)
        ai_idx += 1

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

    return {"message": "Game started", "game_id": game_id, "human_player": human_player_name}

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
    winner_val = None
    human_name = _get_human_player_name(game_instance)
    is_spectator = bool(getattr(web_controller, "spectator_mode", False))
    if game_instance:
        winner_val = game_instance.winner
        reveal_all_roles = (not is_active) or bool(game_instance.winner) or is_spectator
        for p in game_instance.players:
            visible_role = (p.role.name if p.role else "Unknown") if (reveal_all_roles or p.name == human_name) else "Unknown"
            personality_val = getattr(p.controller, "personality", None) if reveal_all_roles else None
            players_data.append({
                "name": p.name,
                "role": visible_role,
                "personality": personality_val,
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
        game_id=game_id,
        winner=winner_val,
        human_player=human_name,
        spectator_mode=is_spectator,
    )

_history_save_lock = threading.Lock()

def save_game_history_for_instance(game_instance: Optional[Game]):
    """Saves a completed Game instance's outcome, players, logs, votes, and deaths to GameHistory."""
    global game_history
    if not game_instance or not game_instance.winner:
        return
    with _history_save_lock:
        if getattr(game_instance, "history_saved", False):
            return
        players_info = []
        for p in game_instance.players:
            players_info.append({
                "name": p.name,
                "role": p.role.name if p.role else "Unknown",
                "is_alive": p.is_alive,
                "is_sheriff": bool(p.is_sheriff),
                "is_human": bool(getattr(p.controller, "is_human", False)),
                "personality": getattr(p.controller, "personality", None),
            })

        logs_data = []
        for entry in game_instance.game_log:
            logs_data.append({
                "id": entry.id,
                "type": entry.log_type.name,
                "message": entry.message,
                "source": entry.source.name if entry.source else None,
                "target": entry.target.name if entry.target else None,
                "data": entry.data,
                "camps": entry.camps,
                "visible_to_roles": list(entry.visible_to_roles) if entry.visible_to_roles else [],
                "visible_to_players": [vp.name for vp in entry.visible_to_players] if entry.visible_to_players else [],
                "day": entry.day,
                "round": entry.day,
                "state": entry.state,
            })

        game_history.add_game(
            winner=game_instance.winner,
            players=players_info,
            logs=logs_data,
            votes=list(game_instance.vote_history),
            deaths=list(game_instance.death),
            rounds=game_instance.day,
        )
        setattr(game_instance, "history_saved", True)

def save_game_history_if_ended(session: GameSession):
    """Saves the game's outcome and logs to the historical record if the game has concluded."""
    if session and session.game_instance:
        save_game_history_for_instance(session.game_instance)

def _resolve_historical_game_id(game_id: str) -> Optional[int]:
    """Extracts a numeric historical game ID from 'history_<id>' or plain numeric '<id>'."""
    if not game_id:
        return None
    if game_id.startswith("history_"):
        raw = game_id[len("history_"):]
        if raw.isdigit():
            return int(raw)
    elif game_id.isdigit():
        return int(game_id)
    return None

def _get_or_rehydrate_session(game_id: str) -> Optional[GameSession]:
    """Retrieves an active GameSession or rehydrates a finished historical game on demand."""
    session = game_manager.get_game(game_id)
    if session:
        return session

    hist_id = _resolve_historical_game_id(game_id)
    if hist_id is None:
        return None

    detail = game_history.get_game_details(hist_id)
    if not detail:
        return None

    from game.player import Player, Villager, Werewolf, Witch, Seer, Guard, Hunter, BlackWerewolfKing
    from game.log import LogType
    from game.states.special_states import GameOverState

    role_classes = {
        "Villager": Villager,
        "Werewolf": Werewolf,
        "Witch": Witch,
        "Seer": Seer,
        "Guard": Guard,
        "Hunter": Hunter,
        "Black Werewolf King": BlackWerewolfKing,
    }

    web_ctrl = WebController()
    controllers_map: Dict[str, Any] = {}
    rehydrated_players_list = detail.get("players", [])
    has_explicit_human = any(p_info.get("is_human") for p_info in rehydrated_players_list)
    for p_info in rehydrated_players_list:
        p_name = p_info.get("name", "Player 1")
        is_human_seat = bool(p_info.get("is_human")) if has_explicit_human else (p_name == "Player 1")
        if is_human_seat:
            controllers_map[p_name] = web_ctrl
        else:
            rc = RandomController()
            if p_info.get("personality"):
                setattr(rc, "personality", p_info["personality"])
            controllers_map[p_name] = rc

    if not controllers_map:
        return None

    rehydrated_game = Game(controllers_map)
    rehydrated_game.game_log.clear()
    rehydrated_game.winner = detail.get("winner")
    rehydrated_game.day = detail.get("rounds", 1)
    rehydrated_game.vote_history = list(detail.get("votes", []))
    rehydrated_game.death = list(detail.get("deaths", []))
    setattr(rehydrated_game, "history_saved", True)

    player_by_name: Dict[str, Player] = {}
    for p_obj, p_info in zip(rehydrated_game.players, detail.get("players", [])):
        r_name = p_info.get("role", "Villager")
        r_cls = role_classes.get(r_name, Villager)
        p_obj.role = r_cls()
        p_obj.is_alive = bool(p_info.get("is_alive", False))
        p_obj.is_sheriff = bool(p_info.get("is_sheriff", False))
        if p_obj.is_sheriff:
            setattr(rehydrated_game, "sheriff", p_obj)
        player_by_name[p_obj.name] = p_obj

    for idx, l_dict in enumerate(detail.get("logs", [])):
        l_type_str = l_dict.get("type") or l_dict.get("log_type") or "SYSTEM"
        l_type = getattr(LogType, l_type_str, LogType.SYSTEM)
        src_name = l_dict.get("source")
        tgt_name = l_dict.get("target")
        vis_players = [
            player_by_name[vn]
            for vn in (l_dict.get("visible_to_players") or [])
            if vn in player_by_name
        ]
        entry = LogEntry(
            id=l_dict.get("id", idx),
            log_type=l_type,
            message=l_dict.get("message", ""),
            source=player_by_name.get(src_name) if src_name else None,
            target=player_by_name.get(tgt_name) if tgt_name else None,
            data=l_dict.get("data") or {},
            visible_to_roles=l_dict.get("visible_to_roles") or [],
            camps=l_dict.get("camps") or [],
            visible_to_players=vis_players,
            day=l_dict.get("day") or l_dict.get("round") or 1,
            state=l_dict.get("state") or "",
        )
        rehydrated_game.game_log.append(entry)

    rehydrated_game.state = GameOverState(rehydrated_game, winner=str(rehydrated_game.winner or "Villagers"))
    dummy_thread = threading.Thread(target=lambda: None)
    session = GameSession(game_id, rehydrated_game, web_ctrl, dummy_thread)
    with game_manager.lock:
        game_manager.active_games[game_id] = session
    return session

@app.get("/api/game/{game_id}/full_logs")
async def get_full_logs(game_id: str):
    """Retrieves the complete, player-specific logs for a given game.

    This endpoint is used for features like the "Village Chronicles," where a user can
    review the entire history of the game from each player's perspective. It iterates
    through all game logs and filters them based on each player's visibility rules.
    """
    session = _get_or_rehydrate_session(game_id)
    
    if not session:
        return {"logs": []}
        
    game_instance = session.game_instance
    is_spectator = bool(session.web_controller and getattr(session.web_controller, "spectator_mode", False))
    is_game_over = session.is_finished() or bool(game_instance.winner) or is_spectator
    human_name = _get_human_player_name(game_instance)
    
    player_logs = {}
    target_players = game_instance.players if is_game_over else [p for p in game_instance.players if p.name == human_name]
    
    for p in target_players:
        player_logs[p.name] = {
            "role": p.role.name if p.role else "Unknown",
            "logs": []
        }
        
    # This approach reconstructs each player's view of the game log.
    from game.player import Werewolf
    from game.log import LogType
    for entry in game_instance.game_log:
        for p in target_players:
            if game_instance._is_visible(entry, p):
                log_type_name = entry.log_type.name
                if not is_game_over and entry.log_type in (LogType.HUNTER_SHOOT, LogType.BLACKWEREWOLFKING_SHOOT):
                    is_wolf = bool(p.role and isinstance(p.role, Werewolf))
                    is_self = (entry.source == p)
                    if not (is_wolf or is_self):
                        log_type_name = "PLAYER_SHOOT"
                player_logs[p.name]["logs"].append({
                    "type": log_type_name,
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
    session = _get_or_rehydrate_session(game_id)
    
    if not session:
        return {"votes": [], "deaths": []}
        
    game_instance = session.game_instance
    is_spectator = bool(session.web_controller and getattr(session.web_controller, "spectator_mode", False))
    is_game_over = session.is_finished() or bool(game_instance.winner) or is_spectator
    deaths = game_instance.death
    if not is_game_over:
        sanitized_deaths = []
        for d in deaths:
            d_copy = dict(d)
            if d_copy.get("phase") == "night":
                d_copy["reason"] = "night"
            elif d_copy.get("reason") in ("hunter_shot", "black_werewolf_king_shot"):
                d_copy["reason"] = "shot"
            sanitized_deaths.append(d_copy)
        deaths = sanitized_deaths
    return {
        "votes": game_instance.vote_history,
        "deaths": deaths
    }

@app.get("/api/game/{game_id}/player/{player_name}/operations")
async def get_player_operations(game_id: str, player_name: str):
    """
    Retrieves the operations history for a specific player in a game.
    """
    session = _get_or_rehydrate_session(game_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
        
    game_instance = session.game_instance
    is_spectator = bool(session.web_controller and getattr(session.web_controller, "spectator_mode", False))
    is_game_over = session.is_finished() or bool(game_instance.winner) or is_spectator
    human_name = _get_human_player_name(game_instance)
    if not is_game_over and player_name != human_name:
        raise HTTPException(status_code=403, detail="Cannot view other players' operations while the game is active")

    hist_id = _resolve_historical_game_id(game_id)
    if hist_id is not None and not game_manager.get_game(game_id):
        detail = game_history.get_game_details(hist_id)
        if detail:
            return game_history.reconstruct_player_operations(detail, player_name)

    history = game_instance.get_player_operations_history(player_name)
    # Fallback for legacy historical records where source was omitted on Witch/Seer/Guard logs
    if hist_id is not None and history.get("role") in ("Witch", "Seer", "Guard"):
        detail = game_history.get_game_details(hist_id)
        if detail:
            return game_history.reconstruct_player_operations(detail, player_name)
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

@app.post("/api/game/spectate")
async def enable_spectate_mode(request: SpectateRequest):
    """Enables God-View spectator mode once the human player has been eliminated and has no pending actions."""
    session = game_manager.get_game(request.game_id)
    if not session or not session.game_instance:
        raise HTTPException(status_code=404, detail="Game not found")

    human_player = _get_human_player(session.game_instance)
    if human_player and human_player.is_alive and not session.is_finished():
        raise HTTPException(status_code=403, detail="Cannot enable spectator mode while human player is still alive")

    if session.web_controller.pending_request is not None:
        raise HTTPException(status_code=409, detail="Please complete your final death/last-words action before spectating")

    if not session.web_controller.spectator_mode:
        session.web_controller.enable_spectator_mode()
        from game.log import LogType
        session.game_instance.log(
            LogEntry(
                log_type=LogType.SYSTEM,
                message={
                    "en": "👁️ Spectator God View enabled: all player roles, night actions, and AI thoughts are now visible.",
                    "zh": "👁️ 已开启亡灵上帝视角：全场真实身份、夜间行动与 AI 内心思考已全部揭晓。",
                },
                visible_to_players=[human_player] if human_player else [],
            )
        )

    return {"status": "ok", "spectator_mode": True}


@app.post("/api/llm/test")
async def test_llm_connection(request: LLMTestRequest):
    """Tests whether the provided (or environment-configured) LLM API key and endpoint are reachable."""
    is_zh = request.language == "zh"
    effective_key = (request.api_key or "").strip() or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
    if not effective_key:
        return {
            "ok": False,
            "mode": "random",
            "model": None,
            "provider": request.provider or "openai",
            "message": (
                "未配置 API Key，对局将使用内置随机机器人代打。"
                if is_zh
                else "No API Key configured. AI players will use the built-in random bot."
            ),
        }
    try:
        client = LLMClient(
            api_key=effective_key,
            base_url=request.base_url,
            model=request.model_name,
            provider=request.provider,
        )
    except Exception as e:
        return {
            "ok": False,
            "mode": "error",
            "model": request.model_name,
            "provider": request.provider or "openai",
            "message": f"初始化失败：{e}" if is_zh else f"Init failed: {e}",
        }

    raw = await asyncio.to_thread(
        client.get_completion,
        'Reply strictly with JSON: {"ok": true}',
        True,
    )
    if raw and '"Error calling LLM:' in raw:
        try:
            err_obj = json.loads(raw) if "json" in globals() else {}
            err_detail = err_obj.get("thought", raw)
        except Exception:
            err_detail = raw
        return {
            "ok": False,
            "mode": "error",
            "model": client.model,
            "provider": request.provider or "openai",
            "message": (
                f"连接失败 ({client.model})：{err_detail}"
                if is_zh
                else f"Connection failed ({client.model}): {err_detail}"
            ),
        }

    return {
        "ok": True,
        "mode": "llm",
        "model": client.model,
        "provider": request.provider or "openai",
        "message": (
            f"✅ 连接成功！当前模型：{client.model}"
            if is_zh
            else f"✅ Connected successfully! Active model: {client.model}"
        ),
    }


@app.post("/api/game/settings")
async def update_settings(request: UpdateSettingsRequest):
    """Updates runtime settings for an active game session."""
    session = game_manager.get_game(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    if request.turn_timeout is not None and request.turn_timeout > 0:
        session.web_controller.set_timeout(request.turn_timeout)
    if request.language in ("zh", "en") and session.game_instance:
        session.game_instance.language = request.language
        for p in session.game_instance.players:
            if hasattr(p.controller, "language"):
                p.controller.language = request.language
    return {
        "status": "ok",
        "turn_timeout": session.web_controller.timeout,
        "language": getattr(session.game_instance, "language", "zh") if session.game_instance else "zh",
    }

@app.post("/api/game/evaluate")
async def evaluate_game(request: EvaluationRequest):
    """Initiates a post-game evaluation of the human player's performance.

    This endpoint uses the `GameEvaluator` to analyze the game logs and provide
    feedback to the player based on their role, the game's outcome, and the chosen
    evaluation mode (e.g., 'mild', 'mean').
    """
    session = _get_or_rehydrate_session(request.game_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    game_instance = session.game_instance

    human_player = _get_human_player(game_instance)
    
    if not human_player:
        raise HTTPException(status_code=400, detail="Human player not found")

    api_key = request.api_key or session.llm_config.get("api_key")
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
    session = _get_or_rehydrate_session(request.game_id)
    
    if not session or not session.game_evaluator:
        raise HTTPException(status_code=400, detail="No active evaluation session")
        
    reply = session.game_evaluator.chat(request.message)
    return {"reply": reply}

@app.post("/api/game/argue")
async def argue_with_ai_players(request: ArgueRequest):
    """Allows the human player to pick one or more AI players after the game ends to argue/debrief."""
    session = _get_or_rehydrate_session(request.game_id)
    if not session or not session.game_instance:
        raise HTTPException(status_code=404, detail="Game not found")

    if not request.selected_players:
        raise HTTPException(status_code=400, detail="Please select at least one AI player to argue with")

    if session.debate_room is None:
        session.debate_room = PostGameDebateRoom(
            game=session.game_instance,
            default_llm_config=session.llm_config,
        )

    override_cfg = None
    if request.api_key or request.base_url or request.model_name or request.provider:
        override_cfg = {
            "api_key": request.api_key or session.llm_config.get("api_key"),
            "base_url": request.base_url or session.llm_config.get("base_url"),
            "model_name": request.model_name or session.llm_config.get("model_name"),
            "provider": request.provider or session.llm_config.get("provider"),
        }

    replies = await asyncio.to_thread(
        session.debate_room.argue,
        request.selected_players,
        request.message,
        request.language,
        override_cfg,
    )
    return {"replies": replies}

class PrepareModelRequest(BaseModel):
    """Defines the structure for pre-game voice model download and initialization."""
    backend: Optional[str] = None
    whisper_model: Optional[str] = None


@app.get("/api/transcribe/status")
async def transcribe_status(backend: Optional[str] = Query(None)):
    """Returns the configured speech-to-text backend, cache status, and real-time download progress."""
    from config import ASR_CONFIG
    from web.transcriber import _transcriber, get_download_status, is_model_cached

    progress = get_download_status()
    requested_backend = (backend or progress.get("backend") or ASR_CONFIG.get("backend", "paraformer")).strip().lower()
    cached = is_model_cached(
        backend=requested_backend,
        whisper_model=ASR_CONFIG.get("whisper_model", "large-v3-turbo"),
    )
    if _transcriber is not None and (not backend or _transcriber.backend_name == requested_backend):
        info = _transcriber.get_info()
        return {
            **progress,
            "ready": True,
            "status": "ready",
            "percent": 100.0,
            "cached": True,
            **info,
        }
    return {
        **progress,
        "backend": requested_backend,
        "ready": False,
        "status": progress.get("status") if progress.get("status") in ("downloading", "loading") else "not_downloaded",
        "cached": cached,
        "whisper_model": ASR_CONFIG.get("whisper_model", "large-v3-turbo"),
        "device": ASR_CONFIG.get("device", "auto"),
    }


@app.post("/api/transcribe/prepare")
async def prepare_transcribe_model(request: Optional[PrepareModelRequest] = None):
    """Starts downloading and loading the ASR model in the background before the game begins."""
    from web.transcriber import start_model_preparation

    backend = request.backend if request else None
    whisper_model = request.whisper_model if request else None
    status = start_model_preparation(backend=backend, whisper_model=whisper_model)
    return status


@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    backend: Optional[str] = Form(None),
    whisper_model: Optional[str] = Form(None),
    lang_query: Optional[str] = Query(None, alias="language"),
):
    """Transcribes an uploaded audio file (16kHz WAV, WebM, MP4, etc.) using the pre-loaded ASR model."""
    temp_filename = None
    effective_language = language or lang_query
    try:
        from web.transcriber import get_transcriber
        transcriber = await asyncio.to_thread(
            get_transcriber,
            backend=backend,
            whisper_model=whisper_model,
            require_ready=True,
        )
    except (RuntimeError, ImportError) as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        raw_ext = os.path.splitext(file.filename or "")[1].lower()
        safe_ext = (
            raw_ext
            if raw_ext and (raw_ext.isalnum() or (raw_ext.startswith(".") and raw_ext[1:].isalnum()))
            else ".wav"
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=safe_ext) as tmp:
            temp_filename = tmp.name
            shutil.copyfileobj(file.file, tmp)

        text = await asyncio.to_thread(transcriber.transcribe, temp_filename, language=effective_language)

        os.remove(temp_filename)
        temp_filename = None

        info = transcriber.get_info() if hasattr(transcriber, "get_info") else {}
        return {"text": text, **info}
    except Exception as e:
        if temp_filename and os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
