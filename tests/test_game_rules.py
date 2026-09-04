import unittest
from unittest.mock import MagicMock

from game.game import Game
from game.player import (
    Player,
    Villager,
    Werewolf,
    Witch,
    Seer,
    Guard,
    Hunter,
    BlackWerewolfKing,
)
from game.controllers import Controller, SafeController
from game.states.night_states import NightEndState
from game.states.special_states import ShootState
from game.states.sheriff_states import SheriffDeathState
from game.handlers.night_handlers import (
    handle_werewolf_turn_started,
    handle_seer_check,
)
from game.events.night_events import (
    WerewolfTurnStarted,
    WerewolfTargetSelected,
    SeerCheck,
    SeerCheckResult,
)


class MockActionController(Controller):
    def __init__(self, action_dict=None):
        self.actions = action_dict or {}

    def get_speech(self, player: Player) -> str:
        return "..."

    def get_vote(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return self.actions.get("vote")

    def get_werewolf_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return self.actions.get("werewolf_target")

    def get_witch_save_decision(self, player: Player, target: Player) -> bool:
        return self.actions.get("witch_save", False)

    def get_witch_poison_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return self.actions.get("witch_poison")

    def get_vote_for_sheriff(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return self.actions.get("vote_sheriff")

    def get_join_election_decision(self, player: Player) -> bool:
        return self.actions.get("join_election", False)

    def get_seer_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return self.actions.get("seer_target")

    def get_guard_protect(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return self.actions.get("guard_protect")

    def get_hunter_shoot_target(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return self.actions.get("shoot_target")

    def get_speech_order_decision(self, player: Player) -> str:
        return "clockwise"

    def get_sheriff_death_decision(self, player: Player, potential_targets: list[Player]) -> Player | None:
        return self.actions.get("badge_target")


class TestGameRules(unittest.TestCase):

    def setUp(self):
        self.p1 = Player("P1_Villager", MockActionController())
        self.p1.role = Villager()
        self.p2 = Player("P2_Villager", MockActionController())
        self.p2.role = Villager()
        self.p3 = Player("P3_Hunter", MockActionController())
        self.p3.role = Hunter()
        self.p4 = Player("P4_Witch", MockActionController())
        self.p4.role = Witch()
        self.p5 = Player("P5_Guard", MockActionController())
        self.p5.role = Guard()
        self.p6 = Player("P6_Seer", MockActionController())
        self.p6.role = Seer()
        self.p7 = Player("P7_Wolf", MockActionController())
        self.p7.role = Werewolf()
        self.p8 = Player("P8_King", MockActionController())
        self.p8.role = BlackWerewolfKing()

        self.all_players = [self.p1, self.p2, self.p3, self.p4, self.p5, self.p6, self.p7, self.p8]
        controllers = {p.name: p.controller for p in self.all_players}
        self.game = Game(controllers)
        self.game.players = self.all_players
        for p in self.all_players:
            p.controller.game = self.game

    # --- 1. Win Conditions ---

    def test_win_condition_all_werewolves_dead(self):
        # Kill both werewolves
        self.p7.is_alive = False
        self.p8.is_alive = False
        winner = self.game.check_win_condition()
        self.assertEqual(winner, "Villagers")

    def test_win_condition_equal_werewolves_and_villagers(self):
        # Kill all villagers except p1 and p2 (2 villagers alive, 2 werewolves alive: p7, p8)
        self.p3.is_alive = False
        self.p4.is_alive = False
        self.p5.is_alive = False
        self.p6.is_alive = False
        winner = self.game.check_win_condition()
        self.assertEqual(winner, "Werewolves")

    def test_win_condition_no_winner_yet(self):
        # 6 villagers alive, 2 werewolves alive
        winner = self.game.check_win_condition()
        self.assertIsNone(winner)

    # --- 2. NightEndState: Guard vs Witch Antidote Conflicts ---

    def test_night_conflict_guard_only(self):
        state = NightEndState(self.game)
        self.game.night_kill_target = self.p1
        self.game.protected_this_night = self.p1
        self.game.saved_this_night = None
        self.game.night_poison_target = None

        state.handle()
        self.assertNotIn(self.p1, self.game.killed_this_night)

    def test_night_conflict_save_only(self):
        state = NightEndState(self.game)
        self.game.night_kill_target = self.p1
        self.game.protected_this_night = None
        self.game.saved_this_night = self.p1
        self.game.night_poison_target = None

        state.handle()
        self.assertNotIn(self.p1, self.game.killed_this_night)

    def test_night_conflict_guard_and_save_causes_death(self):
        state = NightEndState(self.game)
        self.game.night_kill_target = self.p1
        self.game.protected_this_night = self.p1
        self.game.saved_this_night = self.p1
        self.game.night_poison_target = None

        state.handle()
        # Conflicting magic rule: player dies
        self.assertIn(self.p1, self.game.killed_this_night)
        self.assertEqual(self.p1.death_reason, "werewolf")

    def test_night_poison_kills(self):
        state = NightEndState(self.game)
        self.game.night_kill_target = None
        self.game.night_poison_target = self.p2

        state.handle()
        self.assertIn(self.p2, self.game.killed_this_night)
        self.assertEqual(self.p2.death_reason, "poison")

    # --- 3. Death Triggers: Hunter and Black Werewolf King ---

    def test_hunter_shoot_state(self):
        self.p3.death_reason = "werewolf"
        self.p3.controller.actions["shoot_target"] = self.p7  # Hunter shoots Wolf

        shoot_state = ShootState(self.game, self.p3, "next_state", {})
        shoot_state.handle()

        self.assertFalse(self.p7.is_alive)
        self.assertEqual(self.p7.death_reason, "hunter_shot")

    def test_black_werewolf_king_shoot_state(self):
        self.p8.death_reason = "execution"
        self.p8.controller.actions["shoot_target"] = self.p6  # King shoots Seer

        shoot_state = ShootState(self.game, self.p8, "next_state", {})
        shoot_state.handle()

        self.assertFalse(self.p6.is_alive)
        self.assertEqual(self.p6.death_reason, "black_werewolf_king_shot")

    def test_chained_shooting(self):
        # Hunter shoots Black Werewolf King, King triggers shoot trigger
        self.p3.controller.actions["shoot_target"] = self.p8
        self.game.shoot_triggers = []

        shoot_state = ShootState(self.game, self.p3, "next_state", {})
        shoot_state.handle()

        self.assertIn(self.p8, self.game.shoot_triggers)

    # --- 4. Sheriff Rules: Badge Passing & Destruction ---

    def test_sheriff_pass_badge(self):
        self.game.sheriff = self.p1
        self.p1.is_sheriff = True
        self.p1.controller.actions["badge_target"] = self.p2

        sheriff_death_state = SheriffDeathState(self.game, self.p1, "next_state", {})
        sheriff_death_state.handle()

        self.assertFalse(self.p1.is_sheriff)
        self.assertTrue(self.p2.is_sheriff)
        self.assertEqual(self.game.sheriff, self.p2)

    def test_sheriff_destroy_badge(self):
        self.game.sheriff = self.p1
        self.p1.is_sheriff = True
        self.p1.controller.actions["badge_target"] = None  # Abstain to destroy

        sheriff_death_state = SheriffDeathState(self.game, self.p1, "next_state", {})
        sheriff_death_state.handle()

        self.assertFalse(self.p1.is_sheriff)
        self.assertIsNone(self.game.sheriff)

    # --- 5. Polymorphism: BlackWerewolfKing in Night Handlers ---

    def test_black_werewolf_king_polymorphism_in_night_handlers(self):
        # Only King is alive among werewolves
        self.p7.is_alive = False
        self.p8.is_alive = True
        self.p8.controller.actions["werewolf_target"] = self.p1

        published_events = []
        self.game.event_bus.subscribe(WerewolfTargetSelected, lambda e: published_events.append(e))

        handle_werewolf_turn_started(self.game, WerewolfTurnStarted())
        self.assertEqual(len(published_events), 1)
        self.assertEqual(published_events[0].target, self.p1)

    def test_seer_check_black_werewolf_king(self):
        published_events = []
        self.game.event_bus.subscribe(SeerCheckResult, lambda e: published_events.append(e))

        event = SeerCheck(player=self.p6, target=self.p8)
        handle_seer_check(self.game, event)

        self.assertEqual(len(published_events), 1)
        self.assertTrue(published_events[0].is_werewolf)


if __name__ == "__main__":
    unittest.main()
