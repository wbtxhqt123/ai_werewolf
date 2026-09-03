from game.events.base import Event


class GuardTurnStarted(Event):
    pass


class GuardProtect(Event):
    def __init__(self, player, target):
        self.player = player
        self.target = target


class WerewolfTurnStarted(Event):
    pass


class WerewolfTargetSelected(Event):
    def __init__(self, target):
        self.target = target


class WitchTurnStarted(Event):
    pass


class WitchSave(Event):
    def __init__(self, player):
        self.player = player


class WitchPoison(Event):
    def __init__(self, player, target):
        self.player = player
        self.target = target


class SeerTurnStarted(Event):
    pass


class SeerCheck(Event):
    def __init__(self, player, target):
        self.player = player
        self.target = target


class SeerCheckResult(Event):
    def __init__(self, player, target, is_werewolf):
        self.player = player
        self.target = target
        self.is_werewolf = is_werewolf
