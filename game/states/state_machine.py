from __future__ import annotations
from typing import TYPE_CHECKING

from .base import GameState
from .day_states import (
    DayAnnouncementState,
    DayEndState,
    DayStartState,
    ExecutionState,
    SpeechState,
    VoteState,
    TieSpeechState,
    TieVoteState,
)
from .night_states import (
    NightBeginState,
    GuardNightState,
    SeerNightState,
    WitchNightState,
    WerewolfNightState,
    NightEndState,
)
from .sheriff_states import (
    SheriffElectionState,
    SheriffSpeechState,
    SheriffWithdrawState,
    SheriffVoteState,
    SheriffSpeechOrderState,
    SheriffDeathState,
)
from .special_states import (
    GameOverState,
    LastWordsState,
    ShootState,
)

if TYPE_CHECKING:
    from ..game import Game


class StateMachine:
    STATE_MAP = {
        "night_begin": NightBeginState,
        "guard_protect": GuardNightState,
        "seer_check": SeerNightState,
        "witch_action": WitchNightState,
        "werewolf_kill": WerewolfNightState,
        "night_end": NightEndState,
        "day_start": DayStartState,
        "sheriff_election": SheriffElectionState,
        "day_announcement": DayAnnouncementState,
        "sheriff_speech_order": SheriffSpeechOrderState,
        "speech": SpeechState,
        "vote": VoteState,
        "execution": ExecutionState,
        "day_end": DayEndState,
        "sheriff_speech": SheriffSpeechState,
        "sheriff_withdraw": SheriffWithdrawState,
        "sheriff_vote": SheriffVoteState,
        "tie_speech": TieSpeechState,
        "tie_vote": TieVoteState,
        "game_over": GameOverState,
        "last_words": LastWordsState,
        "shoot": ShootState,
        "sheriff_death": SheriffDeathState,
    }

    @staticmethod
    def create_state(state_name: str, game: Game, **kwargs) -> GameState | None:
        state_class = StateMachine.STATE_MAP.get(state_name)
        if state_class:
            state = state_class(game=game, **kwargs)
            return state
        return None
