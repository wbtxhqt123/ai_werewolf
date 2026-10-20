from __future__ import annotations
from typing import TYPE_CHECKING
import random

from ..log import LogEntry, LogType
from ..player import Witch, Seer, Guard, Werewolf, BlackWerewolfKing
from ..utils import state_handler
from .base import GameState
from ..events.game_flow import NightPhaseStarted, NightEnd
from ..events.night_events import (
    GuardProtect,
    WerewolfTargetSelected,
    WitchSave,
    WitchPoison,
    SeerCheckResult,
)
from config import GAME_RULES

if TYPE_CHECKING:
    from ..game import Game


class NightBeginState(GameState):
    """Marks the beginning of the night phase.

    This state increments the game round, logs the start of the night, and prepares
    for the sequence of nightly actions.
    """
    def __init__(self, game, day: int):
        self.game = game
        self.day = day

    @state_handler
    def handle(self):
        self.game.day = self.day
        self.game.event_bus.publish(NightPhaseStarted(night_number=self.day))
        self.game.log(LogEntry(log_type=LogType.NIGHT_FALLS, message={"en": f"--- Night {self.game.day} ---", "zh": f"--- 第 {self.game.day} 夜 ---"}, camps=["All"]))
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "The sun sets, and a new night begins...", "zh": "太阳落山了，一个新的夜晚开始了..."}, camps=["All"]))

    def transition(self):
        return "guard_protect", {}


class GuardNightState(GameState):
    """Handles the Guard's nightly action.

    If a Guard is in the game, they are prompted to choose a player to protect.
    The chosen player will be immune to the Werewolves' attack for the night, unless
    a special condition (like a Witch's save) creates a conflict.
    """

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        guard_player = next((p for p in self.game.players if p.is_alive and isinstance(p.role, Guard)), None)
        if not guard_player:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "There is no guard.", "zh": "场上没有守卫。"}, visible_to_roles=["Guard"], camps=["Villagers"]))
            return

        self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": f"{guard_player.name} (Guard), open your eyes.", "zh": f"{guard_player.name} (守卫)，请睁眼。"}, visible_to_roles=["Guard"], camps=["Villagers"]))
        
        guard_role: Guard = guard_player.role
        potential_targets = [p for p in self.game.players if p.is_alive]
        
        # The Guard cannot protect the same player on two consecutive nights.
        if guard_role.last_protected and guard_role.last_protected in potential_targets:
            potential_targets.remove(guard_role.last_protected)
            
        target = guard_player.controller.get_guard_protect(guard_player, potential_targets)
        
        if target:
            self.game.protected_this_night = target
            guard_role.last_protected = target
            self.game.event_bus.publish(GuardProtect(player=guard_player, target=target))
            self.game.log(LogEntry(
                log_type=LogType.GUARD_PROTECT,
                message={"en": f"You have protected {target.name}.", "zh": f"你守护了 {target.name}。"},
                source=guard_player,
                target=target,
                visible_to_roles=["Guard"],
                camps=["Villagers"]
            ))
        else:
            self.game.protected_this_night = None
            guard_role.last_protected = None
            self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": "You decided not to protect anyone.", "zh": "你决定不守护任何人。"}, visible_to_roles=["Guard"], camps=["Villagers"]))

        self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": f"{guard_player.name}, close your eyes.", "zh": f"{guard_player.name}，请闭眼。"}, visible_to_roles=["Guard"], camps=["Villagers"]))

    def transition(self):
        return "werewolf_kill", {}


class WerewolfNightState(GameState):
    """State for the werewolves to choose their target."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": "Werewolves, open your eyes.", "zh": "狼人请睁眼。"}, visible_to_roles=["Werewolf", "Black Werewolf King"], camps=["Werewolves"]))

        werewolves = [p for p in self.game.players if p.is_alive and (isinstance(p.role, Werewolf) or isinstance(p.role, BlackWerewolfKing))]
        if not werewolves:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "There are no werewolves.", "zh": "场上没有狼人。"}, visible_to_roles=["Werewolf", "Black Werewolf King"], camps=["Werewolves"]))
            return

        # Identify teammates
        for werewolf in werewolves:
            teammates = [p.name for p in werewolves if p != werewolf]
            if teammates:
                teammates_str = ", ".join(teammates)
                self.game.log(LogEntry(
                    log_type=LogType.SYSTEM,
                    message={"en": f"Your teammates are: {teammates_str}", "zh": f"你的队友是: {teammates_str}"},
                    visible_to_players=[werewolf],
                    camps=["Werewolves"]
                ))
            else:
                self.game.log(LogEntry(
                    log_type=LogType.SYSTEM,
                    message={"en": "You are the only werewolf.", "zh": "你是唯一的狼人。"},
                    visible_to_players=[werewolf],
                    camps=["Werewolves"]
                ))

        # Werewolf private discussion
        for werewolf in werewolves:
            speech = werewolf.controller.get_speech(werewolf)
            self.game.log(LogEntry(
                log_type=LogType.WHISPER,
                message={"en": f"({werewolf.name}): {speech}", "zh": f"({werewolf.name}): {speech}"},
                source=werewolf,
                visible_to_roles=["Werewolf", "Black Werewolf King"],
                camps=["Werewolves"]
            ))

        # One werewolf chooses the target
        acting_werewolf = random.choice(werewolves)
        
        potential_targets = [p for p in self.game.players if p.is_alive]
        target = acting_werewolf.controller.get_werewolf_target(acting_werewolf, potential_targets)
        
        if target:
            self.game.night_kill_target = target
            self.game.event_bus.publish(WerewolfTargetSelected(target=target))
            self.game.log(LogEntry(
                log_type=LogType.WEREWOLF_TARGET,
                message={"en": f"The werewolves have targeted {target.name}.", "zh": f"狼人选择了袭击 {target.name}。"},
                source=acting_werewolf,
                target=target,
                visible_to_roles=["Werewolf", "Black Werewolf King"],
                camps=["Werewolves"]
            ))
        else:
            self.game.log(LogEntry(
                log_type=LogType.WEREWOLF_TARGET,
                message={"en": "The werewolves decided not to kill anyone tonight.", "zh": "狼人今晚决定不杀任何人。"},
                visible_to_roles=["Werewolf", "Black Werewolf King"],
                camps=["Werewolves"]
            ))

    def transition(self):
        return "witch_action", {}


class WitchNightState(GameState):
    """State for the witch to use their potions."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        witch_player = next((p for p in self.game.players if p.is_alive and isinstance(p.role, Witch)), None)
        if not witch_player:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "There is no witch.", "zh": "场上没有女巫。"}, visible_to_roles=["Witch"], camps=["Villagers"]))
            return
            
        self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": f"{witch_player.name} (Witch), open your eyes.", "zh": f"{witch_player.name} (女巫)，请睁眼。"}, visible_to_roles=["Witch"], camps=["Villagers"]))
        witch_role: Witch = witch_player.role
        used_save = False

        # --- Save Action ---
        target = self.game.night_kill_target
        if witch_role.has_save:
            if target:
                self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": f"This player was targeted by the werewolves: {target.name}.", "zh": f"今晚 {target.name} 被狼人袭击了。"}, visible_to_roles=["Witch"], camps=["Villagers"]))
                # Witch cannot save herself
                if target == witch_player:
                    self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": "You cannot save yourself.", "zh": "你不能自救。"}, visible_to_roles=["Witch"], camps=["Villagers"]))
                elif witch_player.controller.get_witch_save_decision(witch_player, target):
                    witch_role.save_player(target)
                    self.game.saved_this_night = target
                    used_save = True
                    self.game.event_bus.publish(WitchSave(player=witch_player))
                    self.game.log(LogEntry(log_type=LogType.WITCH_ACTION, message={"en": f"You have saved {target.name}.", "zh": f"你使用解药救了 {target.name}。"}, source=witch_player, target=target, data={"action": "save"}, visible_to_roles=["Witch"], camps=["Villagers"]))
            else:
                self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": "No one was targeted by the werewolves tonight.", "zh": "今晚平安夜。"}, visible_to_roles=["Witch"], camps=["Villagers"]))
        else:
            self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": "You have no save potion left.", "zh": "你没有解药了。"}, visible_to_roles=["Witch"], camps=["Villagers"]))

        # --- Poison Action (only if save was not used) ---
        if not used_save:
            if witch_role.has_poison:
                poison_targets = [p for p in self.game.players if p.is_alive]
                poison_target = witch_player.controller.get_witch_poison_target(witch_player, poison_targets)
                if poison_target:
                    witch_role.poison_player(poison_target)
                    self.game.night_poison_target = poison_target
                    self.game.event_bus.publish(WitchPoison(player=witch_player, target=poison_target))
                    self.game.log(LogEntry(log_type=LogType.WITCH_ACTION, message={"en": f"You have poisoned {poison_target.name}.", "zh": f"你毒死了 {poison_target.name}。"}, source=witch_player, target=poison_target, data={"action": "poison"}, visible_to_roles=["Witch"], camps=["Villagers"]))
            else:
                self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": "You have no poison potion left.", "zh": "你没有毒药了。"}, visible_to_roles=["Witch"], camps=["Villagers"]))
            
        self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": f"{witch_player.name}, close your eyes.", "zh": f"{witch_player.name}，请闭眼。"}, visible_to_roles=["Witch"], camps=["Villagers"]))

    def transition(self):
        return "seer_check", {}


class SeerNightState(GameState):
    """State for the seer to check a player's identity."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        seer_player = next((p for p in self.game.players if p.is_alive and isinstance(p.role, Seer)), None)
        if not seer_player:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "There is no seer.", "zh": "场上没有预言家。"}, visible_to_roles=["Seer"], camps=["Villagers"]))
            return

        self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": f"{seer_player.name} (Seer), open your eyes.", "zh": f"{seer_player.name} (预言家)，请睁眼。"}, visible_to_roles=["Seer"], camps=["Villagers"]))
        
        potential_targets = [p for p in self.game.players if p.is_alive]
        target = seer_player.controller.get_seer_target(seer_player, potential_targets)
        
        if target:
            # The Seer sees the camp (Werewolf or Villager)
            camp = target.role.camp
            # If the target is a Werewolf, the camp is "Werewolves". If Villager/Witch/Seer, it's "Villagers".
            # However, usually Seer sees "Good" or "Bad".
            # Based on user request: "seer can check anyone and get its camp, villager or werewolf."
            # And Role.camp returns "Werewolves" or "Villagers".
            
            result = "Werewolf" if target.role.camp == "Werewolves" else "Villager"
            
            self.game.event_bus.publish(
                SeerCheckResult(player=seer_player, target=target, is_werewolf=(result == "Werewolf"))
            )
            self.game.log(LogEntry(
                log_type=LogType.SEER_CHECK,
                message={"en": f"You checked {target.name}. They are in {result} camp.", "zh": f"你查验了 {target.name}，他是 {result} 阵营。"},
                source=seer_player,
                target=target,
                data={"result": result},
                visible_to_roles=["Seer"],
                camps=["Villagers"]
            ))
        else:
             self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": "You decided not to check anyone.", "zh": "你决定不查验任何人。"}, visible_to_roles=["Seer"], camps=["Villagers"]))

        self.game.log(LogEntry(log_type=LogType.ACTION, message={"en": f"{seer_player.name}, close your eyes.", "zh": f"{seer_player.name}，请闭眼。"}, visible_to_roles=["Seer"], camps=["Villagers"]))

    def transition(self):
        return "night_end", {}


class NightEndState(GameState):
    """State to signify the end of the night and process deaths."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        # Clear the set for the current night's deaths
        self.game.killed_this_night.clear()

        werewolf_target = self.game.night_kill_target
        saved_player = self.game.saved_this_night
        protected_player = self.game.protected_this_night
        poisoned_player = self.game.night_poison_target
        
        # --- Resolve Deaths ---
        # 1. Werewolf Kill vs. Save/Protect
        if werewolf_target:
            is_saved = (werewolf_target == saved_player)
            is_protected = (werewolf_target == protected_player)
            
            # Dies if not saved AND not protected, or if saved AND protected (conflicting magic)
            # Check configuration for conflicting magic rule
            allow_conflict = GAME_RULES.get("allow_guard_and_save_conflict", True)
            
            if (not is_saved and not is_protected):
                werewolf_target.death_reason = "werewolf"
                self.game.killed_this_night.add(werewolf_target)
            elif (is_saved and is_protected):
                if allow_conflict:
                    werewolf_target.death_reason = "werewolf"
                    self.game.killed_this_night.add(werewolf_target)
                else:
                    # If conflict is not allowed, the player is safe (double protection)
                    pass

        # 2. Witch Poison Kill
        if poisoned_player:
            # If the poisoned player was also the werewolf target and was saved, poison still kills.
            # The set will handle duplicates.
            poisoned_player.death_reason = "poison"
            self.game.killed_this_night.add(poisoned_player)

        # --- End of Night ---
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "The night is over, and dawn is approaching.", "zh": "长夜已过，黎明将至。"}, camps=["All"]))
        self.game.event_bus.publish(NightEnd(night_number=self.game.day))

    def transition(self):
        # Always transition to DayStartState to announce the day
        return "day_start", {}
