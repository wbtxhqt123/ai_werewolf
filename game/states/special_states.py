from __future__ import annotations
from typing import TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..log import LogEntry, LogType
from ..player import Hunter, BlackWerewolfKing
from .base import GameState
from ..utils import state_handler

if TYPE_CHECKING:
    from ..game import Game
    from ..player import Player


class GameOverState(GameState):
    """State for when the game has ended."""
    def __init__(self, game: Game, winner: str):
        super().__init__(game)
        self.winner = winner

    @state_handler
    def handle(self):
        self.game.winner = self.winner
        winner_zh = "村民" if self.winner == "Villagers" else "狼人"
        self.game.log(LogEntry(log_type=LogType.GAME_OVER, message={"en": f"The {self.winner} have won!", "zh": f"{winner_zh}阵营胜利！"}, camps=["All"]))

    def transition(self):
        # Stop the game loop by returning None
        return None, {}


class LastWordsState(GameState):
    """State for a player to speak their last words."""
    def __init__(self, game: Game, player: Player, next_state_name: str, next_state_kwargs: dict):
        super().__init__(game)
        self.player = player
        self.next_state_name = next_state_name
        self.next_state_kwargs = next_state_kwargs

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{self.player.name}, please leave your last words.", "zh": f"{self.player.name}，请留遗言。"}, camps=["All"]))
        last_words = self.player.controller.get_speech(self.player)
        self.game.log(LogEntry(log_type=LogType.SPEECH, message={"en": f"({self.player.name}'s last words): {last_words}", "zh": f"({self.player.name} 的遗言): {last_words}"}, source=self.player, camps=["All"]))

    def transition(self):
        return self.next_state_name, self.next_state_kwargs


class ShootState(GameState):
    """State for a player with a shooting ability to use it upon death."""
    def __init__(self, game: Game, shooter: Player, next_state_name: str, next_state_kwargs: dict):
        super().__init__(game)
        self.shooter = shooter
        self.next_state_name = next_state_name
        self.next_state_kwargs = next_state_kwargs
        self.target = None

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{self.shooter.name} can shoot someone!", "zh": f"{self.shooter.name} 可以开枪带人！"}, source=self.shooter, camps=["All"]))
        
        potential_targets = [p for p in self.game.players if p.is_alive]
        target = self.shooter.controller.get_hunter_shoot_target(self.shooter, potential_targets)
        
        if target:
            self.target = target
            log_type = LogType.HUNTER_SHOOT if isinstance(self.shooter.role, Hunter) else LogType.BLACKWEREWOLFKING_SHOOT
            self.game.log(LogEntry(log_type=log_type, message={"en": f"{self.shooter.name} shoots {target.name}!", "zh": f"{self.shooter.name} 开枪带走了 {target.name}！"}, source=self.shooter, target=target, camps=["All"]))
            self.game.record_death(target, "hunter_shot", phase="day")
            self.game.log(LogEntry(log_type=LogType.PLAYER_ELIMINATED, message={"en": f"{target.name} has been eliminated.", "zh": f"{target.name} 死亡。"}, target=target, camps=["All"]))
            
            # Check if the target is also a shooter (Hunter/King)
            if isinstance(target.role, (Hunter, BlackWerewolfKing)):
                self.game.shoot_triggers.append(target)
        else:
            self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": f"{self.shooter.name} decided not to shoot anyone.", "zh": f"{self.shooter.name} 决定不开枪。"}, source=self.shooter, camps=["All"]))

    def transition(self):
        winner = self.game.check_win_condition()
        if winner:
            return "game_over", {"winner": winner}

        next_state_name = self.next_state_name
        next_state_kwargs = self.next_state_kwargs
        
        # Handle chained shootings
        if self.game.shoot_triggers:
            next_shooter = self.game.shoot_triggers.pop(0)
            next_state_name, next_state_kwargs = "shoot", {"shooter": next_shooter, "next_state_name": next_state_name, "next_state_kwargs": next_state_kwargs}
        
        # The shot target gets to leave last words under specific conditions.
        if self.target:
            if self.shooter.death_reason == "execution" or self.game.day == 1:
                next_state_name, next_state_kwargs = "last_words", {"player": self.target, "next_state_name": next_state_name, "next_state_kwargs": next_state_kwargs}
        
        # If the shot target was the Sheriff, trigger the badge-passing state.
        if self.target and self.target.is_sheriff:
             next_state_name, next_state_kwargs = "sheriff_death", {"sheriff": self.target, "next_state_name": next_state_name, "next_state_kwargs": next_state_kwargs}

        return next_state_name, next_state_kwargs
