from game.events.day_events import (
    AnnounceDeaths,
    SheriffElectionStarted,
    SheriffDecideSpeechOrder,
    SpeechPhaseStarted,
    PlayerVoted,
    ExecutionComplete,
)
from game.events.game_flow import DayStart


def handle_announce_deaths(game, event):
    if game.day == 1:
        game.event_bus.publish(SheriffElectionStarted())
    else:
        game.event_bus.publish(SheriffDecideSpeechOrder())


def handle_sheriff_election_started(game, event):
    game.set_state("sheriff_election")


def handle_sheriff_decide_speech_order(game, event):
    game.set_state("sheriff_speech_order")


def handle_speech_phase_started(game, event):
    game.set_state("speech")


def handle_player_voted(game, event):
    # This will be handled by the VoteState
    pass


def handle_execution_complete(game, event):
    game.set_state("execution")
