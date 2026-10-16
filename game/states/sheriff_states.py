from __future__ import annotations
from typing import TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..log import LogEntry, LogType
from .base import GameState
from ..utils import state_handler

if TYPE_CHECKING:
    from ..game import Game
    from ..player import Player


class SheriffElectionState(GameState):
    """State for players to decide whether to join the election."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "Players can now choose to run for sheriff.", "zh": "现在开始竞选警长。"}, camps=["All"]))
        
        candidates = []
        pending_election_logs = []
        with ThreadPoolExecutor() as executor:
            future_to_player = {executor.submit(player.controller.get_join_election_decision, player): player for player in self.game.players}
            for future in as_completed(future_to_player):
                player = future_to_player[future]
                try:
                    if future.result():
                        candidates.append(player)
                        pending_election_logs.append((player, LogEntry(log_type=LogType.SHERIFF_CANDIDATE, message={"en": f"{player.name} has decided to run for sheriff.", "zh": f"{player.name} 决定竞选警长。"}, source=player, camps=["All"])))
                    else:
                        pending_election_logs.append((player, LogEntry(log_type=LogType.SHERIFF_CANDIDATE, message={"en": f"{player.name} has decided to not run for sheriff.", "zh": f"{player.name} 决定不竞选警长。"}, source=player, camps=["All"])))
                except Exception as exc:
                    pending_election_logs.append((player, LogEntry(log_type=LogType.SYSTEM, message={"en": f"{player.name} encountered an error and will not run for sheriff.", "zh": f"{player.name} 遇到错误，将不参与警长竞选。"}, camps=["All"])))

        # Update candidate status only after all players have completed their decision
        for candidate in candidates:
            candidate.is_sheriff_candidate = True

        self.game.election_players = candidates

        # Announce election decisions simultaneously in player seat order
        pending_election_logs.sort(key=lambda item: self.game.players.index(item[0]) if item[0] in self.game.players else 0)
        for _, log_entry in pending_election_logs:
            self.game.log(log_entry)

        if len(candidates) == 0:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "No one is running for sheriff.", "zh": "没有人竞选警长。"}, camps=["All"]))
        elif len(candidates) == 1:
            sheriff = candidates[0]
            self.game.sheriff = sheriff
            sheriff.is_sheriff = True
            sheriff.is_sheriff_candidate = False
            self.game.log(LogEntry(log_type=LogType.SHERIFF_ELECTED, message={"en": f"{sheriff.name} is the only candidate and has been elected sheriff!", "zh": f"{sheriff.name} 是唯一候选人，自动当选警长！"}, target=sheriff, camps=["All"]))
        else:
            names = ", ".join(p.name for p in candidates)
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"The candidates for sheriff are: {names}", "zh": f"警长竞选人有：{names}"}, camps=["All"]))

    def transition(self):
        if len(self.game.election_players) > 1:
            return "sheriff_speech", {}
        else:
            return "day_announcement", {}


class SheriffSpeechState(GameState):
    """State for players who join the sheriff election."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "All election players will now give their speeches.", "zh": "请竞选玩家发表竞选演说。"}, camps=["All"]))
        for player in self.game.election_players:
            speech = player.controller.get_speech(player)
            self.game.log(LogEntry(log_type=LogType.SPEECH, message={"en": f"({player.name}): {speech}", "zh": f"({player.name}): {speech}"}, source=player, camps=["All"]))

    def transition(self):
        return "sheriff_vote", {}


class SheriffVoteState(GameState):
    """State for players vote the sheriff."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "All living players who are not candidates will now vote for the sheriff.", "zh": "请警下玩家开始投票。"}, camps=["All"]))
        
        voters = [p for p in self.game.players if p.is_alive and p not in self.game.election_players]
        candidates = self.game.election_players

        if not voters:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "No one is eligible to vote.", "zh": "没有玩家有资格投票。"}, camps=["All"]))
            for p in self.game.players:
                p.is_sheriff_candidate = False
            self.game.election_players = [] # Clear candidates
            return

        votes: dict[Player, int] = {p: 0 for p in candidates}
        raw_votes = {}
        vote_details = {c.name: [] for c in candidates}
        vote_details["Abstained"] = []
        
        pending_vote_logs = []
        with ThreadPoolExecutor() as executor:
            future_to_voter = {executor.submit(voter.controller.get_vote_for_sheriff, voter, candidates): voter for voter in voters}
            for future in as_completed(future_to_voter):
                voter = future_to_voter[future]
                try:
                    target = future.result()
                    if target and target in votes:
                        votes[target] += 1
                        raw_votes[voter] = target
                        vote_details[target.name].append(voter.name)
                        pending_vote_logs.append((voter, LogEntry(log_type=LogType.SHERIFF_VOTE, message={"en": f"{voter.name} voted for {target.name}.", "zh": f"{voter.name} 投票给了 {target.name}。"}, source=voter, target=target, camps=["All"])))
                    else:
                        raw_votes[voter] = "Abstained"
                        vote_details["Abstained"].append(voter.name)
                        pending_vote_logs.append((voter, LogEntry(log_type=LogType.SHERIFF_VOTE, message={"en": f"{voter.name} abstained.", "zh": f"{voter.name} 弃票。"}, source=voter, camps=["All"])))
                except Exception as exc:
                    raw_votes[voter] = "Abstained"
                    vote_details["Abstained"].append(voter.name)
                    pending_vote_logs.append((voter, LogEntry(log_type=LogType.SHERIFF_VOTE, message={"en": f"{voter.name} encountered an error and abstained.", "zh": f"{voter.name} 遇到错误并弃票。"}, source=voter, camps=["All"])))

        # Announce all votes simultaneously after all votes are cast (sorted in voter order)
        pending_vote_logs.sort(key=lambda item: voters.index(item[0]) if item[0] in voters else 0)
        for _, log_entry in pending_vote_logs:
            self.game.log(log_entry)

        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "--- Sheriff Vote Results ---", "zh": "--- 警长投票结果 ---"}, camps=["All"]))
        
        if not any(votes.values()):
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "No votes were cast. No sheriff is elected.", "zh": "无人投票，警长未选出。"}, camps=["All"]))
            self.game.log(LogEntry(
                log_type=LogType.VOTE_RESULT,
                message={"en": "No Sheriff elected.", "zh": "未选出警长。"},
                data={"phase": "Sheriff Election", "votes": vote_details, "result": "None"},
                camps=["All"]
            ))
            self.game.record_vote("Sheriff Election", raw_votes, "None")
            for p in self.game.players:
                p.is_sheriff_candidate = False
            self.game.election_players = []
            return

        max_votes = 0
        players_with_max_votes = []
        for player, vote_count in votes.items():
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{player.name}: {vote_count} vote(s)", "zh": f"{player.name}: {vote_count} 票"}, camps=["All"]))
            if vote_count > max_votes:
                max_votes = vote_count
                players_with_max_votes = [player]
            elif vote_count == max_votes:
                players_with_max_votes.append(player)

        if len(players_with_max_votes) == 1:
            sheriff = players_with_max_votes[0]
            self.game.sheriff = sheriff
            sheriff.is_sheriff = True
            for p in self.game.players:
                p.is_sheriff_candidate = False
            self.game.log(LogEntry(
                log_type=LogType.VOTE_RESULT,
                message={"en": f"{sheriff.name} elected Sheriff.", "zh": f"{sheriff.name} 当选警长。"},
                data={"phase": "Sheriff Election", "votes": vote_details, "result": sheriff.name},
                camps=["All"]
            ))
            self.game.record_vote("Sheriff Election", raw_votes, sheriff.name)
            self.game.log(LogEntry(log_type=LogType.SHERIFF_ELECTED, message={"en": f"{sheriff.name} has been elected as the new Sheriff!", "zh": f"{sheriff.name} 当选为新任警长！"}, target=sheriff, camps=["All"]))
        else:
            self.game.tied_players = players_with_max_votes
            for p in self.game.players:
                if p not in players_with_max_votes:
                    p.is_sheriff_candidate = False
            for p in players_with_max_votes:
                p.is_tie = True
            self.game.tie_context = "sheriff"
            self.game.log(LogEntry(
                log_type=LogType.VOTE_RESULT,
                message={"en": "Tie vote.", "zh": "平票。"},
                data={"phase": "Sheriff Election", "votes": vote_details, "result": "Tie"},
                camps=["All"]
            ))
            self.game.record_vote("Sheriff Election", raw_votes, "Tie")
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "There was a tie. Another speech and vote will be held for the tied players.", "zh": "出现平票。平票玩家将进行PK发言和再次投票。"}, camps=["All"]))

    def transition(self):
        if self.game.tied_players:
            return "tie_speech", {}
        else:
            self.game.election_players = []
            # Go to DayAnnouncementState to announce night deaths, then SheriffSpeechOrderState
            return "day_announcement", {}


class SheriffSpeechOrderState(GameState):
    """State for the Sheriff to decide the speech order."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        sheriff = self.game.sheriff
        
        # If no sheriff or sheriff is dead, default to clockwise from index 0 (or random?)
        # Usually if no sheriff, it's by time or fixed order. Let's assume fixed order from player 0.
        if not sheriff or not sheriff.is_alive:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "There is no active Sheriff. Speech will proceed in default order.", "zh": "没有在场警长。发言将按默认顺序进行。"}, camps=["All"]))
            self.game.speech_sequence = [p for p in self.game.players if p.is_alive]
            return

        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{sheriff.name} (Sheriff) is deciding the speech order...", "zh": f"{sheriff.name} (警长) 正在决定发言顺序..."}, camps=["All"]))
        
        decision = sheriff.controller.get_speech_order_decision(sheriff)
        
        # Calculate order
        living_players = [p for p in self.game.players if p.is_alive]
        if not living_players:
            self.game.speech_sequence = []
            return

        try:
            sheriff_index = living_players.index(sheriff)
        except ValueError:
            # Sheriff might have died just now? But we checked is_alive.
            # Maybe logic error. Fallback.
            self.game.speech_sequence = living_players
            return

        if decision == "clockwise":
            # Start from left of sheriff (index + 1)
            # living_players is already sorted by initial index (assuming game.players order is preserved and filtered)
            # We need to rotate the list so it starts with (sheriff_index + 1)
            start_index = (sheriff_index + 1) % len(living_players)
            self.game.speech_sequence = living_players[start_index:] + living_players[:start_index]
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "The Sheriff decided: Clockwise order.", "zh": "警长决定：顺时针发言。"}, camps=["All"]))
        else: # counter_clockwise
            # Start from right of sheriff (index - 1)
            # And go backwards
            start_index = (sheriff_index - 1) % len(living_players)
            # Create reversed list starting from start_index
            # E.g. [0, 1, 2, 3], Sheriff=0. Right=3. Order: 3, 2, 1, 0.
            # E.g. [0, 1, 2, 3], Sheriff=1. Right=0. Order: 0, 3, 2, 1.
            
            # Constructing counter-clockwise list:
            # We want the sequence to be: start_index, start_index-1, ..., sheriff
            
            # Easy way: reverse the list, then rotate?
            # Or just manually build indices
            n = len(living_players)
            indices = []
            curr = start_index
            for _ in range(n):
                indices.append(curr)
                curr = (curr - 1) % n
            
            self.game.speech_sequence = [living_players[i] for i in indices]
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "The Sheriff decided: Counter-clockwise order.", "zh": "警长决定：逆时针发言。"}, camps=["All"]))

    def transition(self):
        return "speech", {}


class SheriffDeathState(GameState):
    """State for the sheriff to pass the badge or destroy it upon death."""
    def __init__(self, game: Game, sheriff: Player, next_state_name: str, next_state_kwargs: dict):
        super().__init__(game)
        self.sheriff = sheriff
        self.next_state_name = next_state_name
        self.next_state_kwargs = next_state_kwargs

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{self.sheriff.name} (Sheriff) has died and must decide what to do with the badge.", "zh": f"{self.sheriff.name} (警长) 死亡，必须决定警徽的去向。"}, camps=["All"]))
        
        potential_targets = [p for p in self.game.players if p.is_alive]
        target = self.sheriff.controller.get_sheriff_death_decision(self.sheriff, potential_targets)
        
        if target:
            self.game.sheriff = target
            target.is_sheriff = True
            self.sheriff.is_sheriff = False
            self.game.log(LogEntry(log_type=LogType.SHERIFF_ELECTED, message={"en": f"{self.sheriff.name} passed the badge to {target.name}.", "zh": f"{self.sheriff.name} 将警徽移交给了 {target.name}。"}, source=self.sheriff, target=target, camps=["All"]))
            self.game.log(LogEntry(log_type=LogType.SHERIFF_ELECTED, message={"en": f"{target.name} is now the Sheriff!", "zh": f"{target.name} 继任成为警长！"}, target=target, camps=["All"]))
        else:
            self.game.sheriff = None
            self.sheriff.is_sheriff = False
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{self.sheriff.name} destroyed the badge. There is no Sheriff.", "zh": f"{self.sheriff.name} 撕毁了警徽。本局游戏不再有警长。"}, source=self.sheriff, camps=["All"]))

    def transition(self):
        winner = self.game.check_win_condition()
        if winner:
            return "game_over", {"winner": winner}
        return self.next_state_name, self.next_state_kwargs
