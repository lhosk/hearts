import random
from game.card import Card, SUITS, RANKS


class Deck:
    def __init__(self):
        self.cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self, num_players=4):
        """Deal cards evenly to num_players. Returns list of lists."""
        self.shuffle()
        hands = [[] for _ in range(num_players)]
        for i, card in enumerate(self.cards):
            hands[i % num_players].append(card)
        return hands