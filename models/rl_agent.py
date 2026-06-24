"""
rl_agent.py — Actor-Critic (A2C) version
Fixes REINFORCE policy collapse by using a learned value network
as the baseline instead of a running mean.

Actor:  policy network — picks which card to play
Critic: value network — predicts expected final score from current state
Advantage = actual_return - critic_prediction (stable, doesn't collapse to 0)
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

SUITS = ['C', 'D', 'S', 'H']
RANKS = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
CARD_INDEX = {(r, s): i for i, (r, s) in enumerate(
    (r, s) for s in SUITS for r in RANKS
)}

def card_to_idx(card):
    return CARD_INDEX[(card.rank, card.suit)]

def cards_to_binary(cards, size=52):
    vec = np.zeros(size, dtype=np.float32)
    for c in cards:
        vec[card_to_idx(c)] = 1.0
    return vec


class ActorNetwork(nn.Module):
    def __init__(self, state_dim=165, action_dim=52, hidden=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden),   nn.ReLU(),
            nn.Linear(hidden, action_dim)
        )

    def forward(self, x, legal_mask):
        logits = self.net(x)
        # large negative on illegal actions so they get ~0 probability
        logits = logits - (1 - legal_mask) * 1e9
        return torch.distributions.Categorical(logits=logits)


class CriticNetwork(nn.Module):
    def __init__(self, state_dim=165, hidden=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden),   nn.ReLU(),
            nn.Linear(hidden, 1)
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


class RLAgent:
    def __init__(
        self,
        reward_mode="minimize",
        actor_lr=3e-4,
        critic_lr=1e-3,
        gamma=0.99,
        entropy_coef=0.01,   # encourages exploration, prevents collapse
    ):
        self.reward_mode  = reward_mode
        self.gamma        = gamma
        self.entropy_coef = entropy_coef

        self.actor  = ActorNetwork()
        self.critic = CriticNetwork()

        self.actor_opt  = optim.Adam(self.actor.parameters(),  lr=actor_lr)
        self.critic_opt = optim.Adam(self.critic.parameters(), lr=critic_lr)

        # Trajectory — reset each hand
        self.states      = []
        self.legal_masks = []
        self.actions     = []
        self.log_probs   = []
        self.entropies   = []

        # Logging
        self.episode_rewards = []
        self.losses          = []
        self.epsilons        = []  # unused, kept for compatibility

    def build_state(self, hand, trick, seen_cards, hearts_broken, scores, player_idx):
        hand_vec  = cards_to_binary([c for c in hand.cards])
        seen_vec  = cards_to_binary(seen_cards)
        trick_vec = cards_to_binary([c for _, c in trick])
        hb  = np.array([float(hearts_broken)], dtype=np.float32)
        sc  = np.array([s / 26.0 for s in scores], dtype=np.float32)
        pos = np.zeros(4, dtype=np.float32)
        pos[player_idx] = 1.0
        return np.concatenate([hand_vec, seen_vec, trick_vec, hb, sc, pos])

    def legal_mask(self, legal_cards):
        mask = np.zeros(52, dtype=np.float32)
        for c in legal_cards:
            mask[card_to_idx(c)] = 1.0
        return mask

    def select_action(self, state, legal_cards, greedy=False):
        mask_np = self.legal_mask(legal_cards)
        s_t = torch.tensor(state,   dtype=torch.float32).unsqueeze(0)
        m_t = torch.tensor(mask_np, dtype=torch.float32).unsqueeze(0)

        dist = self.actor(s_t, m_t)

        if greedy:
            idx = dist.probs.argmax(dim=1).item()
        else:
            idx = dist.sample().item()

        self.states.append(state)
        self.legal_masks.append(mask_np)
        self.actions.append(idx)
        self.log_probs.append(dist.log_prob(torch.tensor(idx)))
        self.entropies.append(dist.entropy())

        for c in legal_cards:
            if card_to_idx(c) == idx:
                return idx, c
        return card_to_idx(legal_cards[0]), legal_cards[0]

    def compute_final_reward(self, own_score, others_scores):
        if self.reward_mode == "minimize":
            return -float(own_score) / 26.0
        else:
            return (float(sum(others_scores)) - float(own_score)) / 26.0

    def update(self, final_reward):
        if not self.log_probs:
            return None

        T = len(self.log_probs)

        # Discounted returns for each timestep
        returns = []
        G = final_reward
        for _ in range(T):
            returns.insert(0, G)
            G *= self.gamma
        returns_t = torch.tensor(returns, dtype=torch.float32)

        # Critic predictions for each state
        states_t = torch.tensor(np.array(self.states), dtype=torch.float32)
        values   = self.critic(states_t)

        # Advantage = return - value (this is what stops collapse)
        advantages = returns_t - values.detach()

        # Normalize advantages for stability
        if T > 1:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # Actor loss
        log_probs_t = torch.stack(self.log_probs)
        entropies_t = torch.stack(self.entropies)
        actor_loss  = -(log_probs_t * advantages).mean() \
                      - self.entropy_coef * entropies_t.mean()

        # Critic loss
        critic_loss = nn.MSELoss()(values, returns_t)

        # Update actor
        self.actor_opt.zero_grad()
        actor_loss.backward()
        nn.utils.clip_grad_norm_(self.actor.parameters(), 1.0)
        self.actor_opt.step()

        # Update critic
        self.critic_opt.zero_grad()
        critic_loss.backward()
        nn.utils.clip_grad_norm_(self.critic.parameters(), 1.0)
        self.critic_opt.step()

        loss_val = actor_loss.item()
        self.losses.append(loss_val)
        self.episode_rewards.append(final_reward)

        # Clear trajectory
        self.states      = []
        self.legal_masks = []
        self.actions     = []
        self.log_probs   = []
        self.entropies   = []

        return loss_val

    def decay_epsilon(self):
        pass  # not used, kept for compatibility

    def choose_pass(self, hand):
        def danger(c):
            if c.rank == 'Q' and c.suit == 'S': return 100
            if c.suit == 'H': return c.value + 1
            return 0
        return sorted(hand.cards, key=danger, reverse=True)[:3]

    def save(self, path):
        torch.save({
            "actor":           self.actor.state_dict(),
            "critic":          self.critic.state_dict(),
            "episode_rewards": self.episode_rewards,
            "losses":          self.losses,
        }, path)
        print(f"  [save] {path}")

    def load(self, path):
        ck = torch.load(path, map_location="cpu")
        self.actor.load_state_dict(ck["actor"])
        self.critic.load_state_dict(ck["critic"])
        self.episode_rewards = ck.get("episode_rewards", [])
        self.losses          = ck.get("losses", [])
        print(f"  [load] {path}")
