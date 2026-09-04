import unittest
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
from game.controllers import Controller, RandomController
from game.log import LogEntry, LogType


class TestOperationsAndVoteHistory(unittest.TestCase):
    def setUp(self):
        controllers: dict[str, Controller] = {
            f"Player {i}": RandomController() for i in range(1, 10)
        }
        self.game = Game(controllers, player_role=None)
        # Assign explicit roles for testing
        role_assignments = [
            (self.game.players[0], Werewolf()),
            (self.game.players[1], Werewolf()),
            (self.game.players[2], BlackWerewolfKing()),
            (self.game.players[3], Seer()),
            (self.game.players[4], Witch()),
            (self.game.players[5], Guard()),
            (self.game.players[6], Hunter()),
            (self.game.players[7], Villager()),
            (self.game.players[8], Villager()),
        ]
        for player, role in role_assignments:
            player.role = role

    def test_werewolf_operations_history(self):
        p1 = self.game.players[0]  # Werewolf
        p2 = self.game.players[1]  # Werewolf
        p3 = self.game.players[2]  # Black Werewolf King
        victim1 = self.game.players[7]
        victim2 = self.game.players[8]

        # Simulate Night 1 werewolf kill
        self.game.day = 1
        self.game.log(
            LogEntry(
                log_type=LogType.WEREWOLF_TARGET,
                message="Targeted Player 8",
                source=p1,
                target=victim1,
                visible_to_roles=["Werewolf", "Black Werewolf King"],
                camps=["Werewolves"],
            )
        )

        # Simulate Night 2 werewolf kill
        self.game.day = 2
        self.game.log(
            LogEntry(
                log_type=LogType.WEREWOLF_TARGET,
                message="Targeted Player 9",
                source=p2,
                target=victim2,
                visible_to_roles=["Werewolf", "Black Werewolf King"],
                camps=["Werewolves"],
            )
        )

        history = self.game.get_player_operations_history(p1.name)
        self.assertEqual(history["role"], "Werewolf")
        self.assertIn("Player 2", history["teammates"])
        self.assertIn("Player 3", history["teammates"])
        self.assertEqual(history["king"], "Player 3")

        # Check kills history
        self.assertIn("kills", history)
        self.assertEqual(len(history["kills"]), 2)
        self.assertEqual(history["kills"][0], {"night": 1, "target": victim1.name})
        self.assertEqual(history["kills"][1], {"night": 2, "target": victim2.name})

        # Ensure werewolf CANNOT see seer checks or witch actions
        self.assertNotIn("checked", history)
        self.assertNotIn("saved", history)
        self.assertNotIn("poisoned", history)
        self.assertNotIn("protected", history)

    def test_seer_operations_history(self):
        seer = self.game.players[3]
        target_wolf = self.game.players[0]
        target_villager = self.game.players[7]

        self.game.day = 1
        self.game.log(
            LogEntry(
                log_type=LogType.SEER_CHECK,
                message="Checked wolf",
                source=seer,
                target=target_wolf,
                data={"result": "Werewolf"},
                visible_to_roles=["Seer"],
                camps=["Villagers"],
            )
        )

        self.game.day = 2
        self.game.log(
            LogEntry(
                log_type=LogType.SEER_CHECK,
                message="Checked villager",
                source=seer,
                target=target_villager,
                data={"result": "Villager"},
                visible_to_roles=["Seer"],
                camps=["Villagers"],
            )
        )

        history = self.game.get_player_operations_history(seer.name)
        self.assertEqual(history["role"], "Seer")
        self.assertEqual(len(history["checked"]), 2)
        self.assertEqual(
            history["checked"][0],
            {"night": 1, "player": target_wolf.name, "camp": "Werewolves"},
        )
        self.assertEqual(
            history["checked"][1],
            {"night": 2, "player": target_villager.name, "camp": "Villagers"},
        )

    def test_witch_and_guard_operations_history(self):
        witch = self.game.players[4]
        guard = self.game.players[5]
        target1 = self.game.players[7]
        target2 = self.game.players[8]

        # Witch actions
        self.game.day = 1
        self.game.log(
            LogEntry(
                log_type=LogType.WITCH_ACTION,
                message="Saved target",
                source=witch,
                target=target1,
                data={"action": "save"},
                visible_to_roles=["Witch"],
                camps=["Villagers"],
            )
        )

        self.game.day = 2
        self.game.log(
            LogEntry(
                log_type=LogType.WITCH_ACTION,
                message="Poisoned target",
                source=witch,
                target=target2,
                data={"action": "poison"},
                visible_to_roles=["Witch"],
                camps=["Villagers"],
            )
        )

        witch_history = self.game.get_player_operations_history(witch.name)
        self.assertEqual(witch_history["saved"], [target1.name])
        self.assertEqual(witch_history["poisoned"], [target2.name])
        self.assertEqual(
            witch_history["saved_details"], [{"night": 1, "target": target1.name}]
        )
        self.assertEqual(
            witch_history["poisoned_details"], [{"night": 2, "target": target2.name}]
        )

        # Guard action
        self.game.day = 1
        self.game.log(
            LogEntry(
                log_type=LogType.GUARD_PROTECT,
                message="Protected target",
                source=guard,
                target=target1,
                visible_to_roles=["Guard"],
                camps=["Villagers"],
            )
        )
        guard_history = self.game.get_player_operations_history(guard.name)
        self.assertEqual(guard_history["protected"], [target1.name])
        self.assertEqual(
            guard_history["protected_details"], [{"night": 1, "target": target1.name}]
        )

    def test_hunter_and_public_shots(self):
        hunter = self.game.players[6]
        black_king = self.game.players[2]
        target1 = self.game.players[0]
        target2 = self.game.players[7]
        villager = self.game.players[8]

        self.game.day = 2
        self.game.log(
            LogEntry(
                log_type=LogType.HUNTER_SHOOT,
                message="Hunter shoots target",
                source=hunter,
                target=target1,
                camps=["All"],
            )
        )

        self.game.day = 3
        self.game.log(
            LogEntry(
                log_type=LogType.BLACKWEREWOLFKING_SHOOT,
                message="Black king shoots target",
                source=black_king,
                target=target2,
                camps=["All"],
            )
        )

        # Hunter should see their shot in personal history and in public shots
        hunter_history = self.game.get_player_operations_history(hunter.name)
        self.assertEqual(hunter_history["shot"], [target1.name])
        self.assertEqual(
            hunter_history["shot_details"], [{"day": 2, "target": target1.name}]
        )

        # Villager can see public shots, but has no private role actions
        villager_history = self.game.get_player_operations_history(villager.name)
        self.assertEqual(len(villager_history["public_shots"]), 2)
        self.assertEqual(villager_history["public_shots"][0]["shooter"], hunter.name)
        self.assertEqual(villager_history["public_shots"][0]["role"], "Hunter")
        self.assertEqual(villager_history["public_shots"][0]["target"], target1.name)
        self.assertEqual(villager_history["public_shots"][1]["shooter"], black_king.name)
        self.assertEqual(
            villager_history["public_shots"][1]["role"], "Black Werewolf King"
        )
        self.assertEqual(villager_history["public_shots"][1]["target"], target2.name)

    def test_vote_history_recording(self):
        p1 = self.game.players[0]
        p2 = self.game.players[1]
        p3 = self.game.players[2]

        # Record Sheriff Election vote
        self.game.day = 1
        sheriff_votes = {p1: p2, p3: "Abstained"}
        self.game.record_vote("Sheriff Election", sheriff_votes, p2.name)

        # Record Execution vote
        exec_votes = {p1: p3, p2: p3, p3: p1}
        self.game.record_vote("Execution Vote", exec_votes, p3.name)

        self.assertEqual(len(self.game.vote_history), 2)
        entry1 = self.game.vote_history[0]
        self.assertEqual(entry1["day"], 1)
        self.assertEqual(entry1["phase"], "Sheriff Election")
        self.assertEqual(entry1["votes"]["Player 1"], "Player 2")
        self.assertEqual(entry1["votes"]["Player 3"], "Abstained")
        self.assertEqual(entry1["result"], "Player 2")

        entry2 = self.game.vote_history[1]
        self.assertEqual(entry2["phase"], "Execution Vote")
        self.assertEqual(entry2["result"], "Player 3")

    def test_api_operations_and_records(self):
        from starlette.testclient import TestClient
        from web.server import app, game_manager
        from web.controller import WebController
        import threading

        web_ctrl = WebController()
        session_id = game_manager.create_game(
            self.game, web_ctrl, threading.Thread(target=lambda: None)
        )

        client = TestClient(app)

        # Test player operations endpoint
        res_op = client.get(f"/api/game/{session_id}/player/Player 1/operations")
        self.assertEqual(res_op.status_code, 200)
        data_op = res_op.json()
        self.assertEqual(data_op["role"], "Werewolf")
        self.assertIn("kills", data_op)
        self.assertIn("teammates", data_op)

        # Test game records endpoint
        res_rec = client.get(f"/api/game/{session_id}/records")
        self.assertEqual(res_rec.status_code, 200)
        data_rec = res_rec.json()
        self.assertIn("votes", data_rec)
        self.assertIn("deaths", data_rec)

        game_manager.remove_game(session_id)


if __name__ == "__main__":
    unittest.main()
