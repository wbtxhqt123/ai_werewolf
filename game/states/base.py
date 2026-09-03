from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..game import Game


class GameState(ABC):
    """Represents a state in the game's state machine.

    Each state is responsible for a specific part of the game flow, such as a night action,
    a day discussion, or a voting phase. It defines the actions to be taken and the
    transition to the next state.
    """

    def __init__(self, game: Game, **kwargs):
        self.game = game

    @property
    def name(self):
        return self.__class__.__name__

    @abstractmethod
    def handle(self):
        """Executes the primary logic for this state.

        This method contains the core behavior of the state, such as prompting players for
        actions, processing results, and logging events.
        """
        pass

    @abstractmethod
    def transition(self):
        """Determines and sets the next state in the game.

        After the `handle` method is executed, this method is called to move the game
        to the subsequent state, effectively driving the game forward.
        """
        pass
