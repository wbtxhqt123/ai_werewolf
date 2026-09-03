from __future__ import annotations
from typing import TYPE_CHECKING
from .log import LogEntry, LogType
from functools import wraps

if TYPE_CHECKING:
    from player import Player
    from .game import Game
    from .states import GameState


STATE_TRANSLATIONS = {
    "NightBeginState": "入夜阶段",
    "GuardNightState": "守卫行动阶段",
    "WerewolfNightState": "狼人行动阶段",
    "WitchNightState": "女巫行动阶段",
    "SeerNightState": "预言家行动阶段",
    "NightEndState": "长夜结束阶段",
    "SheriffElectionState": "警长竞选阶段",
    "SheriffSpeechState": "竞选发言阶段",
    "SheriffVoteState": "警长投票阶段",
    "DayStartState": "天亮阶段",
    "DayEndState": "天黑阶段",
    "SheriffSpeechOrderState": "警长决定发言顺序阶段",
    "DayAnnouncementState": "公布昨夜情况阶段",
    "SpeechState": "自由发言阶段",
    "VoteState": "放逐投票阶段",
    "LastWordsState": "遗言阶段",
    "ExecutionState": "放逐阶段",
    "HunterShootState": "猎人开枪阶段",
    "BlackWerewolfKingShootState": "黑狼王开枪阶段",
    "SheriffDeathState": "移交警徽阶段",
    "TieSpeechState": "平票发言阶段",
    "TieVoteState": "平票投票阶段",
    "GameOverState": "游戏结束"
}

def state_handler(func):
    """A decorator that wraps a game state's `handle` method.

    This decorator automatically logs the start and end of a state, providing clear
    markers in the game log for debugging and review. It also handles the translation
    of state names for multilingual output.

    Args:
        func: The `handle` method of a `GameState` subclass.

    Returns:
        The wrapped function.
    """
    @wraps(func)
    def wrapper(self: GameState, *args, **kwargs):
        state_name = self.__class__.__name__
        zh_name = STATE_TRANSLATIONS.get(state_name, state_name)
        
        self.game.log(LogEntry(
            log_type=LogType.SYSTEM,
            message={
                "en": f"--- {state_name} Start ---",
                "zh": f"--- {zh_name} 开始 ---"
            },
            camps=["All"]
        ))
        
        result = func(self, *args, **kwargs)
        
        self.game.log(LogEntry(
            log_type=LogType.SYSTEM,
            message={
                "en": f"--- {state_name} End ---",
                "zh": f"--- {zh_name} 结束 ---"
            },
            camps=["All"]
        ))
        return result
    return wrapper

def get_text_input(prompt: str) -> str:
    """Displays a prompt and captures a line of text from the user.

    Args:
        prompt: The message to display to the user.

    Returns:
        The text entered by the user.
    """
    print(prompt)
    return input("> ")

def get_player_choice(prompt: str, players: list[Player], allow_abstain: bool = False) -> Player | None:
    """Prompts a user to select a player from a list.

    This function displays a numbered list of players and asks the user to make a
    selection. It handles input validation and allows for abstention if specified.

    Args:
        prompt: The message to display to the user.
        players: A list of `Player` objects to choose from.
        allow_abstain: If True, the user can press Enter to abstain from choosing,
            in which case the function returns None.

    Returns:
        The selected `Player` object, or None if the user abstains.
    """
    if not players:
        print("No players to choose from.")
        return None
        
    while True:
        print(prompt)
        for i, player in enumerate(players):
            print(f"{i + 1}: {player.name}")
        
        try:
            prompt_text = f"Enter the number (1-{len(players)})"
            if allow_abstain:
                prompt_text += " or press Enter to abstain"
            prompt_text += ": "
            choice = input(prompt_text)
            
            if not choice:
                if allow_abstain:
                    return None
                else:
                    print("Invalid input. You must enter a number.")
                    continue

            choice_index = int(choice) - 1
            if 0 <= choice_index < len(players):
                return players[choice_index]
            else:
                print("Invalid number. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def get_yes_no_choice(prompt: str) -> bool:
    """Prompts the user for a yes/no answer and returns a boolean.

    Args:
        prompt: The question to ask the user.

    Returns:
        True for a "yes" response, False for a "no" response.
    """
    while True:
        choice = input(f"{prompt} (y/n): ").lower()
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            return False
        else:
            print("Invalid input. Please enter 'y' or 'n'.")