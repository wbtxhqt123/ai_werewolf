from __future__ import annotations
import random
import os
import datetime
import json
from typing import Callable, Any, Optional
from config import ROLE_CONFIG, HISTORY_DIR
from .player import Player, Villager, Werewolf, Witch, Seer, Guard, Hunter, BlackWerewolfKing
from .states.state_machine import StateMachine
from .log import LogEntry, LogType
from .controllers import Controller, HumanController
from .event_bus import EventBus
from .events.game_flow import GameStarted, PhaseChanged, GameOver
from .events.day_events import PlayerDied, PlayerVoted, ExecutionComplete


class Game:
    """
    Manages the game state, players, and game flow.
    """

    def __init__(
        self,
        players_with_controllers: dict[str, "Controller"],
        player_role: str | None = None,
        language: str = "zh",
    ):
        """
        Initializes the game with players and their controllers.

        Args:
            players_with_controllers: A dictionary mapping player names to their Controller instances.
            player_role: The role selected by the human player, if any.
            language: Game language ('zh' or 'en').
        """
        self.language = language
        self.event_bus = EventBus()
        self.round = 0
        self.day = 1
        self.players = self._create_players(players_with_controllers)
        self.state = None
        self.night_kill_target = None
        self.saved_this_night = None
        self.protected_this_night = None
        self.protected_by_guard = None
        self.night_poison_target = None
        self.poisoned_by_witch = None
        self.killed_this_night: set[Player] = set()
        self.player_to_execute = None
        self.shoot_triggers = []
        self.sheriff = None
        self.speech_sequence = []  # List of players in order of speech
        self.election_players = []
        self.tied_players = []
        self.tie_context = None
        self.player_role = player_role
        self.winner = None
        self.game_log: list[LogEntry] = []
        self.log_listeners: list[Callable[[LogEntry], None]] = []
        self.log_entry_counter = 0
        self.death = []
        self.vote_history = []
        self.running = True
        self._assign_roles()

        # Set the game instance for each controller
        for player in self.players:
            player.controller.game = self

    def add_log_listener(self, listener: Callable[[LogEntry], None]):
        """Adds a listener that will be called whenever a log entry is added."""
        self.log_listeners.append(listener)
        # Replay any prior logs (such as game setup logs from __init__) to the new listener
        for entry in self.game_log:
            listener(entry)

    def _create_players(
        self, players_with_controllers: dict[str, "Controller"]
    ) -> list[Player]:
        """Creates Player objects with their assigned controllers."""
        return [
            Player(name, controller)
            for name, controller in players_with_controllers.items()
        ]

    def _get_role_config(self, num_players: int) -> dict[str, int]:
        """Returns the role configuration based on the number of players."""
        if num_players in ROLE_CONFIG:
            return ROLE_CONFIG[num_players]
        else:
            # Fallback for other numbers (though UI restricts to 6, 9, 12)
            # Simple logic: ~1/3 wolves, rest villagers + some specials
            num_wolves = max(1, num_players // 3)
            return {
                "Werewolf": num_wolves,
                "Villager": max(0, num_players - num_wolves),
            }

    def _assign_roles(self):
        """Assigns roles to players, considering the human player's choice."""
        num_players = len(self.players)
        config = self._get_role_config(num_players)

        roles = []
        for role_name, count in config.items():
            if role_name == "Werewolf":
                roles.extend([Werewolf() for _ in range(count)])
            elif role_name == "Black Werewolf King":
                roles.extend([BlackWerewolfKing() for _ in range(count)])
            elif role_name == "Villager":
                roles.extend([Villager() for _ in range(count)])
            elif role_name == "Seer":
                roles.extend([Seer() for _ in range(count)])
            elif role_name == "Witch":
                roles.extend([Witch() for _ in range(count)])
            elif role_name == "Guard":
                roles.extend([Guard() for _ in range(count)])
            elif role_name == "Hunter":
                roles.extend([Hunter() for _ in range(count)])

        # Fill remaining spots with Villagers if config is incomplete
        while len(roles) < num_players:
            roles.append(Villager())

        # Truncate if config has too many roles
        roles = roles[:num_players]

        # Find the player controlled by the user (WebController or HumanController)
        human_player = next((p for p in self.players if p.controller.is_human), None)

        print(
            f"DEBUG: Assigning roles. Human player: {human_player}, Requested role: {self.player_role}"
        )

        if human_player and self.player_role:
            roles_map = {
                "Villager": Villager,
                "Werewolf": Werewolf,
                "Witch": Witch,
                "Seer": Seer,
                "Guard": Guard,
                "Hunter": Hunter,
                "Black Werewolf King": BlackWerewolfKing,
            }

            chosen_role_class = roles_map.get(self.player_role)
            if chosen_role_class:
                # Find an instance of the chosen role in the pool
                found = False
                for i, role in enumerate(roles):
                    # Use `type()` for an exact match to prevent assigning a subclass
                    # when a specific base class is requested (e.g., Werewolf vs. BlackWerewolfKing).
                    if type(role) is chosen_role_class:
                        # Assign the role to the human player and remove it from the pool
                        human_player.role = roles.pop(i)
                        found = True
                        break

                # Fallback to `isinstance` if an exact type match isn't found.
                # This is less ideal but provides a fallback.
                if not found:
                    for i, role in enumerate(roles):
                        if isinstance(role, chosen_role_class):
                            human_player.role = roles.pop(i)
                            found = True
                            break

                # If the chosen role is not in the initial role list (due to game configuration),
                # this block attempts to dynamically adjust the roles.
                if not found:
                    # Create an instance of the player's chosen role
                    new_role = chosen_role_class()
                    if roles:
                        # Try to replace a Villager with the chosen role to maintain game balance.
                        villager_index = -1
                        for i, r in enumerate(roles):
                            if isinstance(r, Villager):
                                villager_index = i
                                break

                        # If a Villager is found, remove them to make space for the new role.
                        if villager_index != -1:
                            roles.pop(villager_index)
                        else:
                            # If no Villager is available, remove a random role as a last resort.
                            roles.pop()

                        # Assign the chosen role to the human player.
                        human_player.role = new_role

        players_to_assign = [p for p in self.players if p.role is None]
        random.shuffle(roles)

        for player, role in zip(players_to_assign, roles):
            player.role = role

        # Log role counts
        role_counts = {}
        for role in roles:
            role_counts[role.name] = role_counts.get(role.name, 0) + 1
        if human_player and human_player.role:
            role_counts[human_player.role.name] = (
                role_counts.get(human_player.role.name, 0) + 1
            )

        setup_msg_en = (
            "Game setup: "
            + ", ".join([f"{count} {name}" for name, count in role_counts.items()])
        )
        setup_msg_zh = (
            "游戏设置: "
            + ", ".join([f"{count} {name}" for name, count in role_counts.items()])
        )
        self.log(
            LogEntry(
                log_type=LogType.SYSTEM,
                message={"en": setup_msg_en, "zh": setup_msg_zh},
                camps=["All"],
            )
        )

        # Explicitly tell the human player their role
        if human_player and human_player.role:
            self.log(
                LogEntry(
                    log_type=LogType.SYSTEM,
                    message={
                        "en": f"You have been assigned the role: {human_player.role.name}. {human_player.role.description}",
                        "zh": f"你被分配的角色是: {human_player.role.name}。{human_player.role.description}",  # We might need localized descriptions later
                    },
                    visible_to_players=[human_player],
                )
            )

        # Log player roles for history file, not for players
        player_roles_message = ", ".join(
            [f"{p.name}: {p.role.name}" for p in self.players]
        )
        self.log(
            LogEntry(
                log_type=LogType.SYSTEM,
                message={
                    "en": f"Player roles: {player_roles_message}",
                    "zh": f"玩家角色: {player_roles_message}",
                },
            )
        )

    def record_death(
        self, player: Player, reason: str, phase: str = "day", update_status: bool = True, **kwargs
    ):
        """
        Records a player's death with detailed information and emits a PlayerDied event.
        """
        # Deduplicate death records to avoid repeated recordings
        existing = next((d for d in self.death if d["player"] == player.name), None)
        if existing:
            if update_status:
                player.is_alive = False
            player.death_reason = reason
            return

        death_info = {
            "player": player.name,
            "day": self.day,
            "phase": phase,
            "reason": reason,
            "time": datetime.datetime.now().isoformat(),
            **kwargs,
        }
        self.death.append(death_info)

        if update_status:
            player.is_alive = False

        player.death_reason = reason
        self.event_bus.publish(PlayerDied(player=player, reason=reason))

    def record_vote(self, phase: str, votes: dict, result: str):
        """
        Records a voting session and emits PlayerVoted events.
        """
        # Convert Player objects to names in the votes dict
        votes_by_name = {}
        for voter, target in votes.items():
            voter_name = voter.name if isinstance(voter, Player) else str(voter)
            target_name = target.name if isinstance(target, Player) else str(target)
            votes_by_name[voter_name] = target_name
            self.event_bus.publish(PlayerVoted(voter=voter, target=target))

        vote_info = {
            "day": self.day,
            "phase": phase,
            "votes": votes_by_name,
            "result": result,
            "sheriff": self.sheriff.name if self.sheriff else None,
            "time": datetime.datetime.now().isoformat(),
        }
        self.vote_history.append(vote_info)

    def set_state(self, state_name: str, **kwargs):
        """Sets the current game state using a state identifier and emits PhaseChanged event."""
        self.state = StateMachine.create_state(state_name, self, **kwargs)
        self.event_bus.publish(PhaseChanged(phase_name=state_name, day=self.day))

    def check_win_condition(self) -> str | None:
        """
        Checks if a win condition has been met.
        Returns the winning team ('Villagers' or 'Werewolves') or None.
        """
        living_players = [p for p in self.players if p.is_alive]
        living_werewolves = [
            p for p in living_players if isinstance(p.role, Werewolf)
        ]

        num_living_players = len(living_players)
        num_living_werewolves = len(living_werewolves)
        num_living_villagers = num_living_players - num_living_werewolves

        if num_living_werewolves == 0:
            return "Villagers"

        if num_living_werewolves >= num_living_villagers:
            return "Werewolves"

        return None

    def start(self):
        """
        Starts the main game loop and continues until a win condition is met or the game is stopped.
        """
        self.event_bus.publish(GameStarted(game=self))
        self.log(
            LogEntry(
                log_type=LogType.GAME_START,
                message={
                    "en": "--- The game has started! ---",
                    "zh": "--- 游戏开始了！ ---",
                },
            )
        )
        self.set_state("night_begin", day=self.day)
        while self.state and self.running:
            self.state.handle()
            next_state_name, next_state_kwargs = self.state.transition()
            if next_state_name:
                self.set_state(next_state_name, **next_state_kwargs)
            else:
                self.state = None
        if self.winner:
            self.event_bus.publish(GameOver(winner=self.winner))
        self._write_log_to_file()

    def stop(self):
        """
        Stops the game loop gracefully.
        """
        self.running = False

    def _write_log_to_file(self):
        """Writes the game log to a file in the history directory in JSONL format."""
        if not os.path.exists(HISTORY_DIR):
            os.makedirs(HISTORY_DIR)
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(HISTORY_DIR, f"game_log_{now}.jsonl")
        with open(filename, "w", encoding="utf-8") as f:
            for entry in self.game_log:
                log_dict = {
                    "id": entry.id,
                    "log_type": entry.log_type.name,
                    "message": entry.message,
                    "source": entry.source.name if entry.source else None,
                    "target": entry.target.name if entry.target else None,
                    "data": entry.data,
                    "visible_to_roles": entry.visible_to_roles,
                    "camps": entry.camps,
                    "visible_to_players": [
                        p.name for p in entry.visible_to_players
                    ]
                    if entry.visible_to_players
                    else [],
                    "timestamp": entry.timestamp.isoformat(),
                    "day": entry.day,
                    "state": entry.state,
                }
                f.write(json.dumps(log_dict, ensure_ascii=False) + "\n")

    def _is_visible(self, entry: LogEntry, player: Player) -> bool:
        """
        Checks if a log entry should be visible to a specific player based on the defined rules.
        A player can see a log if ANY of the following conditions are met:
        1. The log is public (camps contains "All").
        2. The player is explicitly named in `visible_to_players`.
        3. The player's role is named in `visible_to_roles`.
        """
        if not player.role:
            return False

        # AI Thought Privacy: Thoughts are private to the AI player and never visible to human players in-game
        if entry.log_type == LogType.THOUGHT:
            is_human = bool(player.controller and getattr(player.controller, "is_human", False))
            if is_human:
                return False
            return bool(entry.visible_to_players and player in entry.visible_to_players)

        # 1. Public Log Check
        if "All" in entry.camps:
            return True

        # 2. Player-Specific Visibility
        if entry.visible_to_players and player in entry.visible_to_players:
            return True

        # 3. Role-Specific Visibility
        if entry.visible_to_roles and player.role.name in entry.visible_to_roles:
            return True

        return False

    def log(self, entry: LogEntry):
        """
        Adds a log entry to the game log and distributes it to players and listeners.

        Args:
            entry: The LogEntry to be added.
        """
        entry.id = self.log_entry_counter
        self.log_entry_counter += 1
        entry.day = self.day
        entry.state = self.state.name if self.state else ""
        self.game_log.append(entry)
        for player in self.players:
            if self._is_visible(entry, player):
                player.logs.append(entry)

        # Notify listeners
        for listener in self.log_listeners:
            listener(entry)

    def get_player_by_name(self, name: str) -> Player | None:
        """
        Returns a player by their name.
        """
        for player in self.players:
            if player.name == name:
                return player
        return None

    def get_player_operations_history(self, player_name: str) -> dict[str, Any]:
        """
        Generates a history of operations for a specific player, tailored to their role.
        Role-specific secret operations are only revealed to their respective roles,
        while public death-triggered shots (Hunter, Black Werewolf King) are visible to all.
        """
        player = self.get_player_by_name(player_name)
        if not player or not player.role:
            return {}

        history: dict[str, Any] = {}
        history["role"] = player.role.name
        role_name = player.role.name

        if role_name in ["Werewolf", "Black Werewolf King"]:
            teammates = [
                p.name
                for p in self.players
                if isinstance(p.role, Werewolf) and p.name != player.name
            ]
            king = [p.name for p in self.players if isinstance(p.role, BlackWerewolfKing)]
            history["teammates"] = teammates
            history["king"] = king[0] if king else None

            # Track werewolf kills round by round
            kills = []
            for log in self.game_log:
                if log.log_type == LogType.WEREWOLF_TARGET:
                    kills.append({
                        "night": log.day or 1,
                        "target": log.target.name if log.target else None,
                    })
            history["kills"] = kills

        if role_name == "Witch":
            saved = []
            poisoned = []
            saved_details = []
            poisoned_details = []
            for log in self.game_log:
                if log.log_type == LogType.WITCH_ACTION and log.source == player:
                    target_name = log.target.name if log.target else "no one"
                    night_num = log.day or 1
                    if log.data.get("action") == "save":
                        saved.append(target_name)
                        saved_details.append({"night": night_num, "target": target_name})
                    elif log.data.get("action") == "poison":
                        poisoned.append(target_name)
                        poisoned_details.append({"night": night_num, "target": target_name})
            history["saved"] = saved
            history["poisoned"] = poisoned
            history["saved_details"] = saved_details
            history["poisoned_details"] = poisoned_details

        if role_name == "Seer":
            checked = []
            for log in self.game_log:
                if log.log_type == LogType.SEER_CHECK and log.source == player:
                    if log.target:
                        checked.append(
                            {
                                "night": log.day or 1,
                                "player": log.target.name,
                                "camp": (
                                    "Werewolves"
                                    if isinstance(log.target.role, Werewolf)
                                    else "Villagers"
                                ),
                            }
                        )
            history["checked"] = checked

        if role_name == "Guard":
            protected = []
            protected_details = []
            for log in self.game_log:
                if log.log_type == LogType.GUARD_PROTECT and log.source == player:
                    if log.target:
                        protected.append(log.target.name)
                        protected_details.append({
                            "night": log.day or 1,
                            "target": log.target.name,
                        })
            history["protected"] = protected
            history["protected_details"] = protected_details

        if role_name in ["Black Werewolf King", "Hunter"]:
            shot = []
            shot_details = []
            if role_name == "Hunter":
                for log in self.game_log:
                    if (
                        log.log_type == LogType.HUNTER_SHOOT
                        and log.source == player
                    ):
                        if log.target:
                            shot.append(log.target.name)
                            shot_details.append({"day": log.day or 1, "target": log.target.name})
            if role_name == "Black Werewolf King":
                for log in self.game_log:
                    if (
                        log.log_type == LogType.BLACKWEREWOLFKING_SHOOT
                        and log.source == player
                    ):
                        if log.target:
                            shot.append(log.target.name)
                            shot_details.append({"day": log.day or 1, "target": log.target.name})
            history["shot"] = shot
            history["shot_details"] = shot_details

        # Public Shots: Hunter and Black Werewolf King shots are public daytime events
        public_shots = []
        for log in self.game_log:
            if log.log_type in [LogType.HUNTER_SHOOT, LogType.BLACKWEREWOLFKING_SHOOT]:
                public_shots.append({
                    "day": log.day or 1,
                    "shooter": log.source.name if log.source else "Unknown",
                    "role": "Hunter" if log.log_type == LogType.HUNTER_SHOOT else "Black Werewolf King",
                    "target": log.target.name if log.target else "no one",
                })
        history["public_shots"] = public_shots

        return history
