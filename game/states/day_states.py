from __future__ import annotations
from typing import TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..log import LogEntry, LogType
from ..player import Hunter, BlackWerewolfKing, Player
from ..utils import state_handler
from .base import GameState
from ..events.game_flow import DayStart
from ..events.day_events import ExecutionComplete
from ..utils import state_handler

if TYPE_CHECKING:
    from ..game import Game
    from ..player import Player


class DayStartState(GameState):
    """State to announce the beginning of the day."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        self.game.event_bus.publish(DayStart(day_number=self.game.day))
        self.game.log(LogEntry(log_type=LogType.DAY_BREAKS, message={"en": f"--- Day {self.game.day} ---", "zh": f"--- 第 {self.game.day} 天 ---"}, camps=["All"]))
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "A new day begins.", "zh": "天亮了。"}, camps=["All"]))

    def transition(self):
        winner = self.game.check_win_condition()
        if winner:
            return "game_over", {"winner": winner}
        else:
            if self.game.day == 1:
                return "sheriff_election", {}
            else:
                return "day_announcement", {}


class DayAnnouncementState(GameState):
    """State to handle the consequences of the night's events."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        # This state is now primarily for setting up the consequences of night deaths.
        # The actual death announcements have been moved to NightEndState.
        if self.game.killed_this_night:
            for player in self.game.killed_this_night:
                player.is_alive = False
                self.game.log(LogEntry(log_type=LogType.PLAYER_ELIMINATED, message={"en": f"Last night, {player.name} was eliminated.", "zh": f"昨晚，{player.name} 死亡。"}, target=player, camps=["All"]))
                # Record to historical log
                self.game.record_death(player, player.death_reason, phase="night")
        else:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "A peaceful night... no one was eliminated.", "zh": "昨晚是平安夜，无人死亡。"}, camps=["All"]))
        
        # Check for Hunter or Black Werewolf King death to trigger shooting
        self.game.shoot_triggers = []
        for player in self.game.killed_this_night:
            # A player killed by poison cannot shoot
            if isinstance(player.role, (Hunter, BlackWerewolfKing)) and player.death_reason != "poison":
                self.game.shoot_triggers.append(player)

    def transition(self):
        # Check for win condition after deaths have been processed
        winner = self.game.check_win_condition()
        if winner:
            return "game_over", {"winner": winner}

        # The next state will be speeches, potentially preceded by shooting or last words.
        next_state_name = "sheriff_speech_order"
        next_state_kwargs = {}

        # The transition logic constructs a chain of states to handle all consequences
        # of the night's events. The chain is built in reverse order to ensure correct sequencing.
        # For example, the final state is determined first (e.g., speeches), and then
        # preceding states (like last words, shooting, or badge passing) are inserted before it.

        # 3. Last Words: If players died on the first night, they get to speak.
        if self.game.day == 1 and self.game.killed_this_night:
            sorted_dead = sorted(list(self.game.killed_this_night), key=lambda p: self.game.players.index(p))
            for player in reversed(sorted_dead):
                next_state_name, next_state_kwargs = "last_words", {"player": player, "next_state_name": next_state_name, "next_state_kwargs": next_state_kwargs}

        # 2. Shooting: If a Hunter or Black Werewolf King died, their shooting action is triggered.
        if self.game.shoot_triggers:
            sorted_shooters = sorted(self.game.shoot_triggers, key=lambda p: self.game.players.index(p))
            for shooter in reversed(sorted_shooters):
                next_state_name, next_state_kwargs = "shoot", {"shooter": shooter, "next_state_name": next_state_name, "next_state_kwargs": next_state_kwargs}
        
        # 1. Cleanup: Reset all night-related variables for the next cycle.
        self.game.night_kill_target = None
        self.game.saved_this_night = None
        self.game.protected_this_night = None
        self.game.night_poison_target = None

        # Sheriff Death: If the Sheriff died, the badge must be passed or destroyed.
        sheriff_died = any(p.is_sheriff for p in self.game.killed_this_night)
        
        if sheriff_died:
            # This state is inserted at the beginning of the chain.
            next_state_name, next_state_kwargs = "sheriff_death", {"sheriff": self.game.sheriff, "next_state_name": next_state_name, "next_state_kwargs": next_state_kwargs}

        return next_state_name, next_state_kwargs


class SpeechState(GameState):
    """State for players to give speeches."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "All living players will now give their speeches.", "zh": "请所有玩家依次发言。"}, camps=["All"]))
        
        # Use the sequence decided by Sheriff, or fallback to default
        players_to_speak = self.game.speech_sequence
        if not players_to_speak:
             players_to_speak = [p for p in self.game.players if p.is_alive]

        for player in players_to_speak:
            if player.is_alive: # Check again in case they died during speech? (Unlikely in this simple engine)
                speech = player.controller.get_speech(player)
                self.game.log(LogEntry(log_type=LogType.SPEECH, message={"en": f"({player.name}): {speech}", "zh": f"({player.name}): {speech}"}, source=player, camps=["All"]))

    def transition(self):
        return "vote", {}


class VoteState(GameState):
    """State for players to vote on who to execute."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "It's time to vote. Who do you want to execute?", "zh": "现在开始放逐投票。"}, camps=["All"]))
        living_players = [p for p in self.game.players if p.is_alive]
        if not living_players:
            return

        votes: dict[Player, float] = {p: 0 for p in living_players}
        raw_votes = {} # Voter -> Target
        vote_details = {p.name: [] for p in living_players}
        vote_details["Abstained"] = []
        
        with ThreadPoolExecutor() as executor:
            future_to_voter = {executor.submit(voter.controller.get_vote, voter, [p for p in living_players if p != voter]): voter for voter in living_players}
            for future in as_completed(future_to_voter):
                voter = future_to_voter[future]
                try:
                    target = future.result()
                    if target:
                        vote_weight = 1.5 if voter.is_sheriff else 1
                        votes[target] += vote_weight
                        raw_votes[voter] = target
                        vote_details[target.name].append(voter.name)
                        self.game.log(LogEntry(log_type=LogType.EXECUTION_VOTE, message={"en": f"{voter.name} voted for {target.name} ({vote_weight} votes).", "zh": f"{voter.name} 投票给了 {target.name} ({vote_weight} 票)。"}, source=voter, target=target, camps=["All"]))
                    else:
                        raw_votes[voter] = "Abstained"
                        vote_details["Abstained"].append(voter.name)
                        self.game.log(LogEntry(log_type=LogType.EXECUTION_VOTE, message={"en": f"{voter.name} abstained from voting.", "zh": f"{voter.name} 弃票。"}, source=voter, camps=["All"]))
                except Exception as exc:
                    raw_votes[voter] = "Abstained"
                    vote_details["Abstained"].append(voter.name)
                    self.game.log(LogEntry(log_type=LogType.EXECUTION_VOTE, message={"en": f"{voter.name} encountered an error and abstained from voting.", "zh": f"{voter.name} 遇到错误并弃票。"}, source=voter, camps=["All"]))
        
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "--- Vote Results ---", "zh": "--- 投票结果 ---"}, camps=["All"]))
        
        if not any(votes.values()):
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "No votes were cast.", "zh": "无人投票。"}, camps=["All"]))
            self.game.log(LogEntry(
                log_type=LogType.VOTE_RESULT,
                message={"en": "No one executed.", "zh": "无人被放逐。"},
                data={"phase": "Execution Vote", "votes": vote_details, "result": "None"},
                camps=["All"]
            ))
            self.game.record_vote("Execution Vote", raw_votes, "None")
            self.game.player_to_execute = None
            return

        max_votes = 0.0
        players_with_max_votes = []
        for player, vote_count in votes.items():
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{player.name}: {vote_count} vote(s)", "zh": f"{player.name}: {vote_count} 票"}, camps=["All"]))
            if vote_count > max_votes:
                max_votes = vote_count
                players_with_max_votes = [player]
            elif vote_count == max_votes:
                players_with_max_votes.append(player)

        if len(players_with_max_votes) == 1:
            player_to_execute = players_with_max_votes[0]
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{player_to_execute.name} has the most votes.", "zh": f"{player_to_execute.name} 票数最多。"}, camps=["All"]))
            self.game.log(LogEntry(
                log_type=LogType.VOTE_RESULT,
                message={"en": f"{player_to_execute.name} executed.", "zh": f"{player_to_execute.name} 被放逐。"},
                data={"phase": "Execution Vote", "votes": vote_details, "result": player_to_execute.name},
                camps=["All"]
            ))
            self.game.record_vote("Execution Vote", raw_votes, player_to_execute.name)
            self.game.player_to_execute = player_to_execute
        else:
            self.game.tied_players = players_with_max_votes
            self.game.tie_context = "execution"
            self.game.log(LogEntry(
                log_type=LogType.VOTE_RESULT,
                message={"en": "Tie vote.", "zh": "平票。"},
                data={"phase": "Execution Vote", "votes": vote_details, "result": "Tie"},
                camps=["All"]
            ))
            self.game.record_vote("Execution Vote", raw_votes, "Tie")
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "There was a tie. Another speech and vote will be held for the tied players.", "zh": "出现平票。平票玩家将进行PK发言和再次投票。"}, camps=["All"]))
            self.game.player_to_execute = None

    def transition(self):
        if self.game.tied_players:
            return "tie_speech", {}
        else:
            return "execution", {}


class ExecutionState(GameState):
    """State for executing a player."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        player = self.game.player_to_execute
        self.game.shoot_triggers = []
        
        if player:
            player.is_alive = False
            self.game.log(LogEntry(log_type=LogType.PLAYER_ELIMINATED, message={"en": f"With the most votes, {player.name} has been executed.", "zh": f"{player.name} 被放逐出局。"}, target=player, camps=["All"]))
            self.game.record_death(player, "execution", phase="day")
            self.game.event_bus.publish(ExecutionComplete(player=player))
            
            if isinstance(player.role, (Hunter, BlackWerewolfKing)):
                self.game.shoot_triggers.append(player)
        else:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "No one was executed today.", "zh": "今天无人被放逐。"}, camps=["All"]))
        
        # self.game.player_to_execute = None # Do not clear yet, needed for transition

    def transition(self):
        winner = self.game.check_win_condition()
        if winner:
            return "game_over", {"winner": winner}

        player = self.game.player_to_execute
        self.game.player_to_execute = None
        
        next_state_name = "day_end"
        next_state_kwargs = {}

        if self.game.shoot_triggers:
            next_shooter = self.game.shoot_triggers.pop(0)
            next_state_name, next_state_kwargs = "shoot", {"shooter": next_shooter, "next_state_name": next_state_name, "next_state_kwargs": next_state_kwargs}
        
        # Check if executed player was Sheriff
        if player and player.is_sheriff:
             next_state_name, next_state_kwargs = "sheriff_death", {"sheriff": player, "next_state_name": next_state_name, "next_state_kwargs": next_state_kwargs}

        if player:
            next_state_name, next_state_kwargs = "last_words", {"player": player, "next_state_name": next_state_name, "next_state_kwargs": next_state_kwargs}

        return next_state_name, next_state_kwargs


class DayEndState(GameState):
    """State to signify the end of the day."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        # Record day deaths
        recorded_deaths = {d['player'] for d in self.game.death}
        for player in self.game.players:
            if not player.is_alive and player.name not in recorded_deaths:
                self.game.record_death(player, player.death_reason, phase="day", update_status=False, guard_protect=False, witch_save=False)

        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "The day is over, and dusk is approaching.", "zh": "天黑了，黄昏降临。"}, camps=["All"]))

        # Trigger background summarization for all players
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "Players are reflecting on the day...", "zh": "玩家们正在回顾今天发生的事情..."}, camps=["All"]))
        
        executor = ThreadPoolExecutor(max_workers=len(self.game.players))
        for player in self.game.players:
            if hasattr(player.controller, 'summarize_history'):
                # Snapshot logs and clear them immediately to avoid race conditions
                logs_snapshot = list(player.logs)
                player.logs.clear()
                executor.submit(player.controller.summarize_history, player, logs_snapshot)
        
        # We do NOT wait for the futures to complete. The game proceeds to NightBeginState.
        # The executor will continue running in background threads.
        executor.shutdown(wait=False)

    def transition(self):
        winner = self.game.check_win_condition()
        if winner:
            return "game_over", {"winner": winner}
        else:
            return "night_begin", {"day": self.game.day + 1}

class TieSpeechState(GameState):
    """State for tied players to give speeches."""

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "The following players will give a speech:", "zh": "以下玩家请发表PK发言："}, camps=["All"]))
        for player in self.game.tied_players:
            speech = player.controller.get_speech(player)
            self.game.log(LogEntry(log_type=LogType.SPEECH, message={"en": f"({player.name}): {speech}", "zh": f"({player.name}): {speech}"}, source=player, camps=["All"]))

    def transition(self):
        return "tie_vote", {}


class TieVoteState(GameState):
    """Handles the revote process when a tie occurs.

    This state is triggered after a `TieSpeechState`. Only the players involved in the
    original tie are candidates. Players who were not part of the tie cast the deciding
    votes. If another tie occurs, the process may end with no result, depending on
    the context (sheriff election vs. execution).
    """

    def __init__(self, game: Game, **kwargs):
        super().__init__(game, **kwargs)

    @state_handler
    def handle(self):
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "It's time to vote again, only for the tied players.", "zh": "请再次投票，只能投给平票玩家。"}, camps=["All"]))
        
        # Only players who are not part of the tie can vote.
        voters = [p for p in self.game.players if p.is_alive and p not in self.game.tied_players]
        candidates = self.game.tied_players

        if not voters:
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "No one is eligible to vote.", "zh": "没有玩家有资格投票。"}, camps=["All"]))
            self.game.tied_players = []
            return

        votes: dict[Player, float] = {p: 0 for p in candidates}
        raw_votes = {} # Voter -> Target
        vote_details = {p.name: [] for p in candidates}
        vote_details["Abstained"] = []
        
        # The voting method depends on whether it's a sheriff tie or an execution tie.
        with ThreadPoolExecutor() as executor:
            future_to_voter = {}
            for voter in voters:
                vote_targets = candidates
                if self.game.tie_context == "sheriff":
                    future = executor.submit(voter.controller.get_vote_for_sheriff, voter, vote_targets)
                else:
                    future = executor.submit(voter.controller.get_vote, voter, vote_targets)
                future_to_voter[future] = voter

            for future in as_completed(future_to_voter):
                voter = future_to_voter[future]
                try:
                    target = future.result()
                    if target and target in votes:
                        vote_weight = 1.5 if voter.is_sheriff else 1
                        votes[target] += vote_weight
                        raw_votes[voter] = target
                        vote_details[target.name].append(voter.name)
                        self.game.log(LogEntry(log_type=LogType.EXECUTION_VOTE, message={"en": f"{voter.name} voted for {target.name} ({vote_weight} votes).", "zh": f"{voter.name} 投票给了 {target.name} ({vote_weight} 票)。"}, source=voter, target=target, camps=["All"]))
                    else:
                        raw_votes[voter] = "Abstained"
                        vote_details["Abstained"].append(voter.name)
                        self.game.log(LogEntry(log_type=LogType.EXECUTION_VOTE, message={"en": f"{voter.name} abstained from voting.", "zh": f"{voter.name} 弃票。"}, source=voter, camps=["All"]))
                except Exception as exc:
                    raw_votes[voter] = "Abstained"
                    vote_details["Abstained"].append(voter.name)
                    self.game.log(LogEntry(log_type=LogType.EXECUTION_VOTE, message={"en": f"{voter.name} encountered an error and abstained from voting.", "zh": f"{voter.name} 遇到错误并弃票。"}, source=voter, camps=["All"]))
        
        self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "--- Tie-breaker Vote Results ---", "zh": "--- PK投票结果 ---"}, camps=["All"]))
        if not any(votes.values()):
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "No votes were cast. The tie remains.", "zh": "无人投票，依然平票。"}, camps=["All"]))
            self.game.log(LogEntry(
                log_type=LogType.VOTE_RESULT,
                message={"en": "Tie remains.", "zh": "依然平票。"},
                data={"phase": "Tie Breaker", "votes": vote_details, "result": "Tie"},
                camps=["All"]
            ))
            self.game.record_vote("Tie Breaker", raw_votes, "Tie")
            self.game.player_to_execute = None
            self.game.tied_players = []
            return

        max_votes = 0.0
        players_with_max_votes = []
        for player, vote_count in votes.items():
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{player.name}: {vote_count} vote(s)", "zh": f"{player.name}: {vote_count} 票"}, camps=["All"]))
            if vote_count > max_votes:
                max_votes = vote_count
                players_with_max_votes = [player]
            elif vote_count == max_votes:
                players_with_max_votes.append(player)

        if len(players_with_max_votes) == 1:
            winner = players_with_max_votes[0]
            if self.game.tie_context == "sheriff":
                self.game.sheriff = winner
                winner.is_sheriff = True
                winner.is_sheriff_candidate = False
                winner.is_tie = False
                self.game.log(LogEntry(
                    log_type=LogType.VOTE_RESULT,
                    message={"en": f"{winner.name} elected Sheriff.", "zh": f"{winner.name} 当选警长。"},
                    data={"phase": "Tie Breaker", "votes": vote_details, "result": winner.name},
                    camps=["All"]
                ))
                self.game.record_vote("Tie Breaker", raw_votes, winner.name)
                self.game.log(LogEntry(log_type=LogType.SHERIFF_ELECTED, message={"en": f"{winner.name} has been elected as the new Sheriff!", "zh": f"{winner.name} 当选为新任警长！"}, target=winner, camps=["All"]))
            else:
                self.game.player_to_execute = winner
                self.game.log(LogEntry(
                    log_type=LogType.VOTE_RESULT,
                    message={"en": f"{winner.name} executed.", "zh": f"{winner.name} 被放逐。"},
                    data={"phase": "Tie Breaker", "votes": vote_details, "result": winner.name},
                    camps=["All"]
                ))
                self.game.record_vote("Tie Breaker", raw_votes, winner.name)
                self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": f"{winner.name} has the most votes.", "zh": f"{winner.name} 票数最多。"}, camps=["All"]))
        else:
            # If the tie-breaker vote also results in a tie, no one is elected or executed.
            self.game.log(LogEntry(
                log_type=LogType.VOTE_RESULT,
                message={"en": "Tie remains.", "zh": "依然平票。"},
                data={"phase": "Tie Breaker", "votes": vote_details, "result": "Tie"},
                camps=["All"]
            ))
            self.game.record_vote("Tie Breaker", raw_votes, "Tie")
            self.game.log(LogEntry(log_type=LogType.SYSTEM, message={"en": "There was another tie. No one will be elected or executed.", "zh": "再次平票。无人当选或被放逐。"}, camps=["All"]))
            self.game.player_to_execute = None
        
        # Clear tie status for all players involved in the tie
        for p in self.game.players:
            if p.is_tie:
                p.is_tie = False
        self.game.tied_players = []

    def transition(self):
        if self.game.tie_context == "sheriff":
            self.game.tie_context = None
            # Go to DayAnnouncementState to announce night deaths, then SheriffSpeechOrderState
            return "day_announcement", {}
        else:
            self.game.tie_context = None
            return "execution", {}
