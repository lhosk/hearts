SUITS = ['C', 'D', 'S', 'H']  # Clubs, Diamonds, Spades, Hearts
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS)}  # 2=0, A=12


class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = RANK_VALUES[rank]

    def points(self):
        if self.suit == 'H':
            return 1
        if self.rank == 'Q' and self.suit == 'S':
            return 13
        return 0

    def __repr__(self):
        return f"{self.rank}{self.suit}"

    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash((self.rank, self.suit))