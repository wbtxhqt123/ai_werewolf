from game.events.special_events import HunterShoot, BlackWerewolfKingShoot
from game.events.day_events import PlayerDied


def handle_player_died(game, event):
    player = event.player
    if not player.role:
        return
    if player.role.name == "Hunter":
        potential_targets = [p for p in game.players if p.is_alive]
        target = player.controller.get_hunter_shoot_target(player, potential_targets)
        if target:
            game.event_bus.publish(HunterShoot(player=player, target=target))
    elif player.role.name in ("Black Werewolf King", "BlackWerewolfKing"):
        potential_targets = [p for p in game.players if p.is_alive]
        target = player.controller.get_hunter_shoot_target(player, potential_targets)
        if target:
            game.event_bus.publish(BlackWerewolfKingShoot(player=player, target=target))


def handle_hunter_shoot(game, event):
    event.target.is_alive = False
    game.event_bus.publish(PlayerDied(player=event.target, reason="shot by hunter"))


def handle_black_werewolf_king_shoot(game, event):
    event.target.is_alive = False
    game.event_bus.publish(PlayerDied(player=event.target, reason="shot by black werewolf king"))
