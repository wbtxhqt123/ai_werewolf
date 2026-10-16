import asyncio
import inspect
from game.events.day_events import PlayerDied
from game.events.night_events import SeerCheckResult


class UIEventHandler:
    def __init__(self, game, websocket_manager):
        self.game = game
        self.websocket_manager = websocket_manager

    def _dispatch(self, coro_or_result):
        """Safely dispatches an async coroutine from a synchronous game thread if needed."""
        if not inspect.iscoroutine(coro_or_result):
            return
        loop = getattr(self.websocket_manager, "loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(coro_or_result, loop)
        else:
            coro_or_result.close()

    def handle_event(self, event):
        if isinstance(event, PlayerDied):
            payload = {
                "type": "player_died",
                "player": event.player.name,
                "reason": event.reason,
            }
            self._dispatch(self.websocket_manager.broadcast(payload))
        elif isinstance(event, SeerCheckResult):
            # This should only be sent to the seer
            seer_player = self.game.get_player_by_name(event.player.name)
            seer_controller = seer_player.controller if seer_player else None
            websocket = getattr(seer_controller, "websocket", None)
            if websocket:
                payload = {
                    "type": "seer_check_result",
                    "target": event.target.name,
                    "is_werewolf": event.is_werewolf,
                }
                if hasattr(self.websocket_manager, "send_personal_message"):
                    self._dispatch(self.websocket_manager.send_personal_message(payload, websocket))
                elif hasattr(self.websocket_manager, "send"):
                    self._dispatch(self.websocket_manager.send(websocket, payload))
