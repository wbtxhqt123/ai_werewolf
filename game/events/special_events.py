from game.events.base import Event


class HunterShoot(Event):
    def __init__(self, player, target):
        self.player = player
        self.target = target


class BlackWerewolfKingShoot(Event):
    def __init__(self, player, target):
        self.player = player
        self.target = target
