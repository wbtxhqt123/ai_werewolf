from game.events.game_flow import GameStarted, NightPhaseStarted, NightEnd, DayStart
from game.events.day_events import AnnounceDeaths, PlayerDied
from game.events.night_events import GuardTurnStarted

def handle_game_started(game, event):
    print("--- GameStarted event handled, starting first night ---")
    game.event_bus.publish(NightPhaseStarted(night_number=1))

def handle_night_phase_started(game, event):
    print(f"--- NightPhaseStarted event handled for night: {event.night_number} ---")
    game.event_bus.publish(GuardTurnStarted())

def handle_night_end(game, event):
    deaths = []
    if game.night_kill_target and game.night_kill_target != game.protected_by_guard:
        deaths.append((game.night_kill_target, "killed by werewolves"))

    if game.poisoned_by_witch:
        deaths.append((game.poisoned_by_witch, "poisoned by witch"))

    for player, reason in deaths:
        if player.is_alive:
            player.is_alive = False
            game.event_bus.publish(PlayerDied(player=player, reason=reason))

    # Reset night state
    game.night_kill_target = None
    game.protected_by_guard = None
    game.poisoned_by_witch = None

    game.event_bus.publish(DayStart())


def handle_day_start(game, event):
    game.event_bus.publish(AnnounceDeaths())
