from game.events.base import Event

class GameStarted(Event):
    """
    Event triggered when the game starts.
    """
    pass

class NightPhaseStarted(Event):
    """
    Event triggered when the night phase starts.
    """
    def __init__(self, night_number: int):
        self.night_number = night_number


class NightEnd(Event):
    pass


class DayStart(Event):
    pass
