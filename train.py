"""
train.py — A2C with proper curriculum learning
Stage 1: agent vs 3x RandomPlayer
Stage 2: agent vs 3x frozen Stage-1 agent
Stage 3: agent vs 3x frozen Stage-2 agent
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import random
import numpy as np

from game.deck import Deck
from game.hand import Hand
from players.random_player import RandomPlayer
from players.rl_player import RLPlayer
from models.rl_agent import RLAgent, card_to_idx

HANDS_PER_STAGE = 10_000
NUM_STAGES      = 3
LOG_INTERVAL    = 500
WEIGHTS_DIR     = "weights"
LOGS_DIR        = "logs"

os.makedirs(WEIGHTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,    exist_ok=True)

MODELS = [
    ("minimize_none",   "minimize", "none"),
    ("minimize_left",   "minimize", "left"),
    ("minimize_right",  "minimize", "right"),
    ("minimize_across", "minimize", "across"),
    ("sabotage_none",   "sabotage", "none"),
    ("sabotage_left",   "sabotage", "left"),
    ("sabotage_right",  "sabotage", "right"),
    ("sabotage_across", "sabotage", "across"),
]


def play_hand(agent, opponents, pass_direction, player_idx=0):
    deck  = Deck()
    dealt = deck.deal(4)
    hands = [Hand(c) for c in dealt]

    if pass_direction != 'none':
        dir_map = {'left': [1,2,3,0], 'right': [3,0,1,2], 'across': [2,3,0,1]}
        targets = dir_map[pass_direction]
        passed  = []
        for p in range(4):
            if p == player_idx:
                passed.append(agent.choose_pass(hands[p]))
            else:
                opp_i = p - 1 if p > player_idx else p
                passed.append(opponents[opp_i].choose_pass(hands[p]))
        for src, cards in enumerate(passed):
            for c in cards:
                hands[src].remove(c)
                hands[targets[src]].cards.append(c)

    scores        = [0, 0, 0, 0]
    hearts_broken = False
    seen_cards    = []

    current = next(i for i, h in enumerate(hands) if h.has_2_of_clubs())

    for trick_num in range(13):
        trick = []

        for _ in range(4):
            hand  = hands[current]
            legal = hand.legal_plays(trick, hearts_broken)

            if current == player_idx:
                state = agent.build_state(
                    hand, trick, seen_cards, hearts_broken, scores, current
                )
                _, card = agent.select_action(state, legal)
            else:
                opp_i = current - 1 if current > player_idx else current
                opp_state = {
                    'trick': trick, 'hearts_broken': hearts_broken,
                    'trick_num': trick_num, 'scores': scores[:],
                    'player_index': current,
                }
                card = opponents[opp_i].choose_card(trick, hand, opp_state)

            hand.remove(card)
            trick.append((current, card))
            seen_cards.append(card)
            if card.suit == 'H':
                hearts_broken = True
            current = (current + 1) % 4

        led_suit = trick[0][1].suit
        winner   = max(trick, key=lambda x: x[1].value if x[1].suit == led_suit else -1)[0]
        scores[winner] += sum(c.points() for _, c in trick)
        current = winner

    # Moon check
    for i, s in enumerate(scores):
        if s == 26:
            scores = [26 if j != i else 0 for j in range(4)]
            break

    return scores


def build_opponents(name, reward_mode, stage):
    """
    Stage 1: 3x RandomPlayer
    Stage 2: 3x frozen Stage-1 agent
    Stage 3: 3x frozen Stage-2 agent
    """
    if stage == 1:
        return [RandomPlayer(), RandomPlayer(), RandomPlayer()]

    prev_path = os.path.join(WEIGHTS_DIR, f"{name}_stage{stage-1}.pt")
    opponents = []
    for _ in range(3):
        opp = RLAgent(reward_mode=reward_mode)
        opp.load(prev_path)
        opponents.append(RLPlayer(opp))
    return opponents


def train_model(name, reward_mode, pass_direction):
    print(f"\n{'='*60}")
    print(f"Training: {name}  |  mode={reward_mode}  |  pass={pass_direction}")
    print(f"{'='*60}")

    agent = RLAgent(reward_mode=reward_mode)

    for stage in range(1, NUM_STAGES + 1):
        print(f"\n-- Stage {stage} --")

        opponents = build_opponents(name, reward_mode, stage)
        opp_type  = "RandomPlayer" if stage == 1 else f"Stage-{stage-1} agent"
        print(f"   Opponents: {opp_type}")

        stage_log = {
            "model": name, "stage": stage,
            "reward_mode": reward_mode, "pass_direction": pass_direction,
            "opponents": opp_type,
            "hand_scores": [], "episode_rewards": [],
            "avg_loss_per_interval": [],
        }

        interval_losses  = []
        interval_scores  = []
        interval_rewards = []

        for hand_num in range(1, HANDS_PER_STAGE + 1):
            scores = play_hand(agent, opponents, pass_direction, player_idx=0)

            own_score     = scores[0]
            others_scores = scores[1:]
            final_reward  = agent.compute_final_reward(own_score, others_scores)
            loss          = agent.update(final_reward)

            interval_scores.append(own_score)
            interval_rewards.append(final_reward)
            if loss is not None:
                interval_losses.append(loss)

            if hand_num % LOG_INTERVAL == 0:
                avg_score  = np.mean(interval_scores)
                avg_reward = np.mean(interval_rewards)
                avg_loss   = np.mean(interval_losses) if interval_losses else 0.0

                stage_log["hand_scores"].extend(interval_scores)
                stage_log["episode_rewards"].extend(interval_rewards)
                stage_log["avg_loss_per_interval"].append(avg_loss)

                print(f"  Hand {hand_num:>5} | "
                      f"avg_score={avg_score:.2f} | "
                      f"avg_reward={avg_reward:.4f} | "
                      f"loss={avg_loss:.4f}")

                interval_losses  = []
                interval_scores  = []
                interval_rewards = []

        weight_path = os.path.join(WEIGHTS_DIR, f"{name}_stage{stage}.pt")
        agent.save(weight_path)

        log_path = os.path.join(LOGS_DIR, f"{name}_stage{stage}.json")
        with open(log_path, "w") as f:
            json.dump(stage_log, f)
        print(f"  Log saved: {log_path}")

    print(f"\n✓ Done: {name}")
    return agent


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="all", help="Model name or 'all'")
    args = parser.parse_args()

    targets = MODELS if args.model == "all" else [
        m for m in MODELS if m[0] == args.model
    ]

    if not targets:
        print(f"Unknown model: {args.model}")
        print("Available:", [m[0] for m in MODELS])
        sys.exit(1)

    for name, reward_mode, pass_direction in targets:
        train_model(name, reward_mode, pass_direction)

    print("\n✓ All training complete.")
