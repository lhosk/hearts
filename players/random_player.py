import random

class RandomPlayer:
    def choose_card(self, trick, hand, state):
        return random.choice(hand.legal_plays(trick, state['hearts_broken']))

    def choose_pass(self, hand):
        return random.sample(hand.cards, 3)