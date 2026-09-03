from game.events.base import Event


class GameStarted(Event):
    """Event triggered when the game starts."""
    def __init__(self, game=None):
        self.game = game


class PhaseChanged(Event):
    """Event triggered when the state machine transitions to a new phase."""
    def __init__(self, phase_name: str, day: int = 1):
        self.phase_name = phase_name
        self.day = day


class GameOver(Event):
    """Event triggered when a win condition is reached."""
    def __init__(self, winner: str):
        self.winner = winner


class NightPhaseStarted(Event):
    """Event triggered when the night phase starts."""
    def __init__(self, night_number: int):
        self.night_number = night_number


class NightEnd(Event):
    """Event triggered when the night phase concludes."""
    def __init__(self, night_number: int = 1):
        self.night_number = night_number


class DayStart(Event):
    """Event triggered when the day phase begins."""
    def __init__(self, day_number: int = 1):
        self.day_number = day_number

