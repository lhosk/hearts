from game.card import Card


class Hand:
    def __init__(self, cards):
        self.cards = list(cards)

    def remove(self, card):
        self.cards.remove(card)

    def has(self, card):
        return card in self.cards

    def suits(self):
        return set(c.suit for c in self.cards)

    def of_suit(self, suit):
        return [c for c in self.cards if c.suit == suit]

    def points(self):
        return sum(c.points() for c in self.cards)

    def has_only_hearts(self):
        return all(c.suit == 'H' for c in self.cards)

    def has_2_of_clubs(self):
        return any(c.rank == '2' and c.suit == 'C' for c in self.cards)

    def legal_plays(self, trick, hearts_broken, trick_num=0):
        led_suit = trick[0][1].suit if trick else None

        # First card of the game must be 2 of clubs
        if not trick and self.has_2_of_clubs():
            return [c for c in self.cards if c.rank == '2' and c.suit == 'C']

        # Must follow suit if possible
        if led_suit:
            follow = self.of_suit(led_suit)
            if follow:
                return follow

        # Leading a trick
        if not led_suit:
            non_hearts = [c for c in self.cards if c.suit != 'H']
            if not hearts_broken and non_hearts:
                return non_hearts
            return self.cards

        # Can't follow suit — play anything, but on trick 1 no hearts or QS
        if trick_num == 0:
            safe = [c for c in self.cards
                    if c.suit != 'H' and not (c.rank == 'Q' and c.suit == 'S')]
            if safe:
                return safe

        return self.cards

    def __len__(self):
        return len(self.cards)

    def __repr__(self):
        return f"Hand({self.cards})"