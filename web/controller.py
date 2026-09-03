from __future__ import annotations
import threading
import time
from typing import Any, TYPE_CHECKING
from game.controllers import Controller
from game.player import Player
from game.log import LogEntry

if TYPE_CHECKING:
    from game.game import Game

class WebController(Controller):
    """Manages interaction between the game logic and a human player using a web interface.

    This controller acts as a bridge. When the game requires an action from the human
    player, the controller blocks the game thread and sets a pending request. The web
    server polls for this request and displays it to the user. Once the user provides
    input via the API, this controller receives it, unblocks the game thread, and
    returns the selected action.
    """
    is_human = True

    def __init__(self):
        """Initializes the WebController.

        Attributes:
            game: The main `Game` object.
            input_event: A `threading.Event` used to block and unblock the game thread.
            input_data: Stores the data received from the web client.
            pending_request: A dictionary representing the input required from the user.
            logs: A list of `LogEntry` objects visible to this player.
            log_lock: A lock to ensure thread-safe access to the logs.
        """
        self.game: Game | None = None
        self.input_event = threading.Event()
        self.input_data: Any | None = None
        self.pending_request: dict | None = None
        self.logs: list[LogEntry] = []
        self.visible_logs: list[dict] = []
        self.log_lock = threading.Lock()

    def add_log(self, entry: LogEntry):
        """Adds a log entry and filters it for the player in a thread-safe manner."""
        with self.log_lock:
            self.logs.append(entry)

            my_player = None
            if self.game:
                my_player = next((p for p in self.game.players if p.controller == self), None)

            is_visible = False
            if my_player and self.game:
                is_visible = self.game._is_visible(entry, my_player)
            else:
                if "All" in entry.camps:
                    is_visible = True

            if is_visible:
                self.visible_logs.append({
                    "id": entry.id,
                    "type": entry.log_type.name,
                    "message": entry.message,
                    "source": entry.source.name if entry.source else None,
                    "target": entry.target.name if entry.target else None,
                    "data": entry.data,
                    "camps": entry.camps
                })

    def get_logs(self, start_index: int = 0) -> list[dict]:
        """Retrieves logs for the web client, filtered by visibility.

        Args:
            start_index: The index from which to start retrieving logs.

        Returns:
            A list of serialized log dictionaries.
        """
        with self.log_lock:
            if start_index >= len(self.visible_logs):
                return []
            return list(self.visible_logs[start_index:])

    def _wait_for_input(self, request_type: str, prompt: str, options: list[str] | None = None) -> Any:
        """Blocks the game thread and waits for user input from the web interface.

        This is the core mechanism of the `WebController`. It creates a pending request,
        clears the input event, and then waits until the `set_input` method (called by
        the web server) sets the event.

        Args:
            request_type: The type of input being requested (e.g., 'speech', 'vote').
            prompt: The message to display to the user.
            options: A list of choices for the user, if applicable.

        Returns:
            The data provided by the user.
        """
        self.pending_request = {
            "type": request_type,
            "prompt": prompt,
            "options": options
        }
        self.input_event.clear()
        self.input_data = None
        
        self.input_event.wait()
        
        self.pending_request = None
        return self.input_data

    def set_input(self, data: Any):
        """Receives input from the web server and unblocks the game thread.

        This method is called by the `/api/game/action` endpoint. It stores the user's
        input and sets the `input_event`, which allows the `_wait_for_input` method
        to proceed.
        """
        self.input_data = data
        self.input_event.set()

    # --- Controller Implementation ---

    def get_speech(self, player: Player) -> str:
        return self._wait_for_input("speech", {"en": f"{player.name}, it's your turn to speak.", "zh": f"{player.name}，轮到你发言了。"})

    def get_vote(self, player: Player, potential_targets: list[Player]) -> Player | None:
        options = [p.name for p in potential_targets]
        choice_name = self._wait_for_input("vote", {"en": "Who do you vote to execute?", "zh": "你投票放逐谁？"}, options)
        if choice_name == "Abstain":
            return None
        return next((p for p in potential_targets if p.name == choice_name), None)

    def get_werewolf_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        options = [p.name for p in potential_targets]
        choice_name = self._wait_for_input("choice", {"en": "Choose a player to eliminate:", "zh": "选择要袭击的玩家："}, options)
        return next((p for p in potential_targets if p.name == choice_name), None)

    def get_witch_save_decision(self, player: Player, target: Player) -> bool:
        choice = self._wait_for_input("choice", {"en": f"Do you want to use your save potion on {target.name}?", "zh": f"你要使用解药救 {target.name} 吗？"}, ["Yes", "No"])
        return choice == "Yes"

    def get_witch_poison_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        use_poison = self._wait_for_input("choice", {"en": "Do you want to use your poison potion tonight?", "zh": "今晚要使用毒药吗？"}, ["Yes", "No"])
        if use_poison == "Yes":
            options = [p.name for p in potential_targets]
            choice_name = self._wait_for_input("choice", {"en": "Choose a player to poison:", "zh": "选择要毒杀的玩家："}, options)
            return next((p for p in potential_targets if p.name == choice_name), None)
        return None

    def get_vote_for_sheriff(self, player: Player, potential_targets: list[Player]) -> Player | None:
        options = [p.name for p in potential_targets]
        choice_name = self._wait_for_input("vote", {"en": "Who do you vote for to be sheriff?", "zh": "你投票选谁做警长？"}, options)
        if choice_name == "Abstain":
            return None
        return next((p for p in potential_targets if p.name == choice_name), None)

    def get_join_election_decision(self, player: Player) -> bool:
        choice = self._wait_for_input("choice", {"en": f"{player.name}, do you want to run for sheriff?", "zh": f"{player.name}，你要竞选警长吗？"}, ["Yes", "No"])
        return choice == "Yes"

    def get_seer_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        options = [p.name for p in potential_targets]
        choice_name = self._wait_for_input("choice", {"en": "Choose a player to check their identity:", "zh": "选择要查验身份的玩家："}, options)
        return next((p for p in potential_targets if p.name == choice_name), None)

    def get_guard_protect(self, player: Player, potential_targets: list[Player]) -> Player | None:
        options = [p.name for p in potential_targets]
        choice_name = self._wait_for_input("choice", {"en": "Choose a player to protect:", "zh": "选择要守护的玩家："}, options)
        return next((p for p in potential_targets if p.name == choice_name), None)

    def get_hunter_shoot_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        options = [p.name for p in potential_targets]
        choice_name = self._wait_for_input("choice", {"en": "You died! Choose a player to shoot:", "zh": "你挂了！选择开枪带走谁："}, options)
        return next((p for p in potential_targets if p.name == choice_name), None)

    def get_speech_order_decision(self, player: Player) -> str:
        choice = self._wait_for_input("choice", {"en": f"{player.name}, you are the Sheriff. Please decide the speech order.", "zh": f"{player.name}，你是警长。请决定发言顺序。"}, ["Clockwise", "Counter-clockwise"])
        if choice == "Clockwise":
            return "clockwise"
        return "counter_clockwise"

    def get_sheriff_death_decision(self, player: Player, potential_targets: list[Player]) -> Player | None:
        options = [p.name for p in potential_targets]
        choice_name = self._wait_for_input("choice", {"en": "You died! Choose a player to pass the badge to (or abstain to destroy it):", "zh": "你挂了！选择把警徽移交给谁（或弃票销毁）："}, options)
        return next((p for p in potential_targets if p.name == choice_name), None)
