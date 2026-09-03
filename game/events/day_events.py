from game.events.base import Event


class AnnounceDeaths(Event):
    pass


class LastWordsStarted(Event):
    def __init__(self, player):
        self.player = player


class SheriffElectionStarted(Event):
    pass


class SheriffDecideSpeechOrder(Event):
    pass


class SpeechPhaseStarted(Event):
    pass


class PlayerVoted(Event):
    def __init__(self, voter, target):
        self.voter = voter
        self.target = target


class ExecutionComplete(Event):
    def __init__(self, player):
        self.player = player


class PlayerDied(Event):
    def __init__(self, player, reason):
        self.player = player
        self.reason = reason
