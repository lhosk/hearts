"""
rl_player.py — wraps RLAgent for use as an opponent in HeartsGame
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.rl_agent import RLAgent


class RLPlayer:
    def __init__(self, agent: RLAgent):
        self.agent = agent
        self._seen = []
        self._scores = [0, 0, 0, 0]
        self._hearts_broken = False

    def reset_hand(self):
        self._seen = []
        self._scores = [0, 0, 0, 0]
        self._hearts_broken = False

    def choose_card(self, trick, hand, state):
        hearts_broken = state.get("hearts_broken", self._hearts_broken)
        scores        = state.get("scores", self._scores)
        player_idx    = state.get("player_index", 0)
        seen          = self._seen[:]
        s = self.agent.build_state(hand, trick, seen, hearts_broken, scores, player_idx)
        legal = hand.legal_plays(trick, hearts_broken)
        _, card = self.agent.select_action(s, legal, greedy=True)
        self._seen.append(card)
        return card

    def choose_pass(self, hand):
        return self.agent.choose_pass(hand)
