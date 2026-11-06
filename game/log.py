from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional, Dict, Any, List

if TYPE_CHECKING:
    from .player import Player

class LogType(Enum):
    """
    Defines the different types of events that can be logged.
    """
    SYSTEM = auto()
    ACTION = auto()
    WHISPER = auto()
    THOUGHT = auto()
    VOTE = auto()
    VOTE_RESULT = auto()

    GAME_START = auto()
    NIGHT_FALLS = auto()
    DAY_BREAKS = auto()
    GAME_OVER = auto()
    
    PLAYER_ELIMINATED = auto()
    
    SHERIFF_ELECTION_START = auto()
    SHERIFF_CANDIDATE = auto()
    SHERIFF_WITHDRAW = auto()
    SHERIFF_VOTE = auto()
    SHERIFF_ELECTED = auto()

    SPEECH = auto()
    EXECUTION_VOTE = auto()
    
    WEREWOLF_NIGHT_START = auto()
    WEREWOLF_VOTE = auto()
    WEREWOLF_TARGET = auto()
    
    WITCH_NIGHT_START = auto()
    WITCH_ACTION = auto()
    
    SEER_NIGHT_START = auto()
    SEER_CHECK = auto()

    GUARD_NIGHT_START = auto()
    GUARD_PROTECT = auto()

    HUNTER_SHOOT = auto()
    BLACKWEREWOLFKING_SHOOT = auto()

    PLAYER_THINKING = auto()
    PLAYER_DONE_THINKING = auto()


@dataclass
class LogEntry:
    """Represents a single, structured event that occurs within the game.

    This dataclass is used to record all significant actions, decisions, and state
    changes. The visibility of each log entry can be controlled to ensure that
    information is only revealed to the appropriate players.

    Attributes:
        id: A unique, sequential identifier for the log entry.
        log_type: The category of the log event, defined by the `LogType` enum.
        message: The core message of the log entry. Can be a simple string or a
            dictionary for multilingual support (e.g., {"en": "...", "zh": "..."}).
        source: The player who initiated the action, if applicable.
        target: The player who was the target of the action, if applicable.
        data: A dictionary for storing any extra structured data related to the event.
        visible_to_roles: A list of role names that are allowed to see this log entry.
        camps: A list of camps (e.g., "Villagers", "Werewolves", "All") that are
            allowed to see this log entry.
        visible_to_players: A list of specific Player objects that are allowed to see
            this log entry, for cases where visibility is highly restricted.
        day: The day number of the game.
    """
    log_type: LogType
    message: str | dict[str, str]
    id: Optional[int] = None
    source: Optional[Player] = None
    target: Optional[Player] = None
    data: Dict[str, Any] = field(default_factory=dict)
    visible_to_roles: Optional[List[str]] = field(default_factory=list)
    camps: List[str] = field(default_factory=list)
    visible_to_players: Optional[List["Player"]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    day: Optional[int] = None
    state: Optional[str] = None

    def get_text(self, language: str = "zh") -> str:
        """Returns the localized string message for this log entry."""
        if isinstance(self.message, dict):
            # Prefer requested language, then fallback to Chinese, English, or first available string
            if language in self.message:
                return str(self.message[language])
            elif "zh" in self.message:
                return str(self.message["zh"])
            elif "en" in self.message:
                return str(self.message["en"])
            elif self.message:
                return str(next(iter(self.message.values())))
            return ""
        return str(self.message)