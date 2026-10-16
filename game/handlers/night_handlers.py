from game.events.night_events import (
    GuardProtect,
    SeerCheck,
    SeerCheckResult,
    SeerTurnStarted,
    WerewolfTargetSelected,
    WerewolfTurnStarted,
    WitchPoison,
    WitchSave,
    WitchTurnStarted,
)
from game.events.game_flow import NightEnd
from game.player import Werewolf


def handle_guard_turn_started(game, event):
    guard = next((p for p in game.players if p.role.name == "Guard"), None)
    if guard and guard.is_alive:
        alive_players = [p for p in game.players if p.is_alive]
        target = guard.controller.get_guard_protect(guard, alive_players)
        game.event_bus.publish(GuardProtect(player=guard, target=target))
    else:
        game.event_bus.publish(WerewolfTurnStarted())


def handle_guard_protect(game, event):
    game.protected_by_guard = event.target
    game.event_bus.publish(WerewolfTurnStarted())


def handle_werewolf_turn_started(game, event):
    werewolves = [p for p in game.players if isinstance(p.role, Werewolf) and p.is_alive]
    if werewolves:
        # For simplicity, let the first werewolf decide
        acting_werewolf = werewolves[0]
        potential_targets = [
            p for p in game.players if p.is_alive and not isinstance(p.role, Werewolf)
        ]
        target = acting_werewolf.controller.get_werewolf_target(
            acting_werewolf, potential_targets
        )
        game.event_bus.publish(WerewolfTargetSelected(target=target))
    else:
        game.event_bus.publish(WitchTurnStarted())


def handle_werewolf_target_selected(game, event):
    game.night_kill_target = event.target
    game.event_bus.publish(WitchTurnStarted())


def handle_witch_turn_started(game, event):
    witch = next(
        (p for p in game.players if p.role and p.role.name == "Witch" and p.is_alive), None
    )
    if witch:
        if witch.role.has_save and game.night_kill_target:
            if witch.controller.get_witch_save_decision(witch, game.night_kill_target):
                game.event_bus.publish(WitchSave(player=witch))
                # Witch used save, so can't use poison in the same turn
                game.event_bus.publish(SeerTurnStarted())
                return

        if witch.role.has_poison:
            potential_targets = [p for p in game.players if p.is_alive]
            poison_target = witch.controller.get_witch_poison_target(
                witch, potential_targets
            )
            if poison_target:
                game.event_bus.publish(
                    WitchPoison(player=witch, target=poison_target)
                )

    game.event_bus.publish(SeerTurnStarted())


def handle_witch_save(game, event):
    if event.player.role.has_save and game.night_kill_target is not None:
        game.night_kill_target = None
        event.player.role.has_save = False


def handle_witch_poison(game, event):
    if event.player.role.has_poison:
        game.poisoned_by_witch = event.target
        event.player.role.has_poison = False


def handle_seer_turn_started(game, event):
    seer = next((p for p in game.players if p.role and p.role.name == "Seer" and p.is_alive), None)
    if seer:
        alive_players = [p for p in game.players if p.is_alive]
        target = seer.controller.get_seer_target(seer, alive_players)
        game.event_bus.publish(SeerCheck(player=seer, target=target))
    else:
        game.event_bus.publish(NightEnd())


def handle_seer_check(game, event):
    is_werewolf = isinstance(event.target.role, Werewolf)
    game.event_bus.publish(
        SeerCheckResult(
            player=event.player, target=event.target, is_werewolf=is_werewolf
        )
    )
    game.event_bus.publish(NightEnd())
