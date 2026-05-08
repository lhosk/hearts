from game.deck import Deck
from game.hand import Hand
from game.card import Card


PASS_DIRECTIONS = ['left', 'right', 'across', 'none']


class HeartsGame:
    def __init__(self, players, pass_direction='left'):
        """
        players: list of 4 player objects with a .choose_card(trick, hand, state) method
                 and a .choose_pass(hand) method returning 3 cards
        pass_direction: 'left', 'right', 'across', or 'none'
        """
        assert len(players) == 4
        assert pass_direction in PASS_DIRECTIONS
        self.players = players
        self.pass_direction = pass_direction

    def play_game(self):
        """Play one full game. Returns list of final scores for each player."""
        deck = Deck()
        dealt = deck.deal(4)
        hands = [Hand(cards) for cards in dealt]

        # Passing phase
        if self.pass_direction != 'none':
            hands = self._do_passing(hands)

        scores = [0] * 4
        hearts_broken = False

        # Find who has 2 of clubs — they go first
        current = next(i for i, h in enumerate(hands) if h.has_2_of_clubs())

        for trick_num in range(13):
            trick = []  # list of (player_index, card)

            for _ in range(4):
                hand = hands[current]
                state = {
                    'trick': trick,
                    'hearts_broken': hearts_broken,
                    'trick_num': trick_num,
                    'scores': scores[:],
                    'player_index': current,
                }
                card = self.players[current].choose_card(trick, hand, state)
                hand.remove(card)
                trick.append((current, card))

                if card.suit == 'H':
                    hearts_broken = True

                current = (current + 1) % 4

            # Determine trick winner
            led_suit = trick[0][1].suit
            winner = max(
                trick,
                key=lambda x: x[1].value if x[1].suit == led_suit else -1
            )[0]

            trick_points = sum(c.points() for _, c in trick)
            scores[winner] += trick_points
            current = winner

        # Check for shoot the moon
        for i, s in enumerate(scores):
            if s == 26:
                scores = [26 if j != i else 0 for j in range(4)]
                break

        return scores

    def _do_passing(self, hands):
        direction_map = {
            'left':   [1, 2, 3, 0],
            'right':  [3, 0, 1, 2],
            'across': [2, 3, 0, 1],
        }
        targets = direction_map[self.pass_direction]

        passed_cards = []
        for i, player in enumerate(self.players):
            cards = player.choose_pass(hands[i])
            assert len(cards) == 3, "Must pass exactly 3 cards"
            passed_cards.append(cards)

        new_hands = [Hand(list(h.cards)) for h in hands]
        for i, cards in enumerate(passed_cards):
            target = targets[i]
            for card in cards:
                new_hands[i].remove(card)
                new_hands[target].cards.append(card)

        return new_hands