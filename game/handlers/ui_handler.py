from game.events.day_events import PlayerDied
from game.events.night_events import SeerCheckResult


class UIEventHandler:
    def __init__(self, game, websocket_manager):
        self.game = game
        self.websocket_manager = websocket_manager

    def handle_event(self, event):
        if isinstance(event, PlayerDied):
            self.websocket_manager.broadcast(
                {
                    "type": "player_died",
                    "player": event.player.name,
                    "reason": event.reason,
                }
            )
        elif isinstance(event, SeerCheckResult):
            # This should only be sent to the seer
            seer_controller = self.game.get_player_by_name(event.player.name).controller
            if hasattr(seer_controller, "websocket"):
                self.websocket_manager.send(
                    seer_controller.websocket,
                    {
                        "type": "seer_check_result",
                        "target": event.target.name,
                        "is_werewolf": event.is_werewolf,
                    },
                )
