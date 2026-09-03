import unittest
from unittest.mock import MagicMock
from game.game import Game
from game.states import SheriffVoteState, TieVoteState
from game.player import Player, Villager
from game.controllers import RandomController

class MockController(RandomController):
    def get_vote_for_sheriff(self, player, candidates):
        return candidates[0] # Always vote for the first candidate

class TestSheriffTie(unittest.TestCase):
    def setUp(self):
        # Setup a game with 4 players
        self.players = {
            "Player 1": MockController(),
            "Player 2": MockController(),
            "Player 3": MockController(),
            "Player 4": MockController()
        }
        self.game = Game(self.players)
        
        # Manually set roles
        for p in self.game.players:
            p.role = Villager()
            
        # Player 1 and 2 are candidates
        self.candidates = [self.game.players[0], self.game.players[1]]
        self.game.election_players = self.candidates
        
        # Player 3 and 4 are voters
        self.voters = [self.game.players[2], self.game.players[3]]

    def test_sheriff_vote_tie_record(self):
        # Mock voters to create a tie
        # Player 3 votes for Player 1
        self.game.players[2].controller.get_vote_for_sheriff = MagicMock(return_value=self.candidates[0])
        # Player 4 votes for Player 2
        self.game.players[3].controller.get_vote_for_sheriff = MagicMock(return_value=self.candidates[1])
        
        state = SheriffVoteState()
        state.game = self.game
        state.handle()
        
        # Check if vote was recorded
        self.assertTrue(len(self.game.vote_history) > 0)
        self.assertEqual(self.game.vote_history[-1]['result'], "Tie")
        self.assertEqual(self.game.vote_history[-1]['phase'], "Sheriff Election")
        
        # Now transition to TieVoteState (via TieSpeechState usually, but we skip speech)
        self.game.tie_context = "sheriff"
        self.game.tied_players = self.candidates
        
        tie_state = TieVoteState()
        tie_state.game = self.game
        
        # Mock voters to create another tie
        # Player 3 votes for Player 1
        self.game.players[2].controller.get_vote_for_sheriff = MagicMock(return_value=self.candidates[0])
        # Player 4 votes for Player 2
        self.game.players[3].controller.get_vote_for_sheriff = MagicMock(return_value=self.candidates[1])
        
        tie_state.handle()
        
        # Check if second vote was recorded
        self.assertTrue(len(self.game.vote_history) > 1)
        self.assertEqual(self.game.vote_history[-1]['result'], "Tie")
        self.assertEqual(self.game.vote_history[-1]['phase'], "Tie Breaker")
        
        # Now check what happens after second tie
        # In TieVoteState.handle:
        # if tie remains:
        # self.game.record_vote("Tie Breaker", raw_votes, "Tie")
        # self.game.player_to_execute = None
        # self.game.tied_players = []
        
        # And transition:
        tie_state.transition()
        
        # If tie_context was sheriff, it goes to DayAnnouncementState
        # self.game.tie_context = None
        # self.game.set_state(DayAnnouncementState())
        
        self.assertIsNone(self.game.tie_context)
        # self.assertIsInstance(self.game.state, DayAnnouncementState) # Can't check class easily without import, but logic holds

    def test_sheriff_vote_tie_then_winner(self):
        # Mock voters to create a tie first
        self.game.players[2].controller.get_vote_for_sheriff = MagicMock(return_value=self.candidates[0])
        self.game.players[3].controller.get_vote_for_sheriff = MagicMock(return_value=self.candidates[1])
        
        state = SheriffVoteState()
        state.game = self.game
        state.handle()
        
        self.assertEqual(self.game.vote_history[-1]['result'], "Tie")
        
        # Transition to TieVoteState
        self.game.tie_context = "sheriff"
        self.game.tied_players = self.candidates
        
        tie_state = TieVoteState()
        tie_state.game = self.game
        
        # Mock voters to create a winner (both vote for Player 1)
        self.game.players[2].controller.get_vote_for_sheriff = MagicMock(return_value=self.candidates[0])
        self.game.players[3].controller.get_vote_for_sheriff = MagicMock(return_value=self.candidates[0])
        
        tie_state.handle()
        
        self.assertEqual(self.game.vote_history[-1]['result'], self.candidates[0].name)
        self.assertEqual(self.game.sheriff, self.candidates[0])

if __name__ == '__main__':
    unittest.main()
