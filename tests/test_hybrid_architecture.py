import unittest
from game.game import Game
from game.controllers import RandomController
from game.events.game_flow import GameStarted, PhaseChanged, GameOver
from game.events.day_events import PlayerDied, PlayerVoted

class FastController(RandomController):
    """A RandomController that does not sleep during tests."""
    def _think(self):
        pass

class TestHybridArchitecture(unittest.TestCase):
    def test_state_machine_emits_events(self):
        players = {
            f"Player {i+1}": FastController() for i in range(6)
        }
        game = Game(players)
        
        received_events = []
        game.event_bus.subscribe(GameStarted, lambda e: received_events.append(("GameStarted", e)))
        game.event_bus.subscribe(PhaseChanged, lambda e: received_events.append(("PhaseChanged", e.phase_name)))
        game.event_bus.subscribe(PlayerDied, lambda e: received_events.append(("PlayerDied", e.player.name, e.reason)))
        game.event_bus.subscribe(GameOver, lambda e: received_events.append(("GameOver", e.winner)))
        
        # Run game until completion
        game.start()
        
        event_names = [e[0] for e in received_events]
        
        # 1. Verify GameStarted was published
        self.assertIn("GameStarted", event_names)
        
        # 2. Verify PhaseChanged events occurred (e.g. night_begin)
        phase_changes = [e[1] for e in received_events if e[0] == "PhaseChanged"]
        self.assertIn("night_begin", phase_changes)
        
        # 3. Verify GameOver was published exactly once and winner matches game.winner
        self.assertIn("GameOver", event_names)
        game_over_events = [e for e in received_events if e[0] == "GameOver"]
        self.assertEqual(len(game_over_events), 1)
        self.assertEqual(game_over_events[0][1], game.winner)
        
        # 4. Verify PlayerDied events were emitted when players died
        if len(game.death) > 0:
            self.assertIn("PlayerDied", event_names)

if __name__ == "__main__":
    unittest.main()
