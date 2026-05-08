import tkinter as tk
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.deck import Deck
from game.hand import Hand
from game.hearts import PASS_DIRECTIONS
from players.random_player import RandomPlayer

# ── Colors ───────────────────────────────────────────────────────────────────
BG       = "#1a1a2e"
TABLE    = "#0d2b1e"
CARD_BG  = "#f5f0e8"
CARD_SEL = "#ffe082"
CARD_DIM = "#555"
RED      = "#e63946"
GREEN    = "#2d6a4f"
BLUE     = "#0f3460"
GOLD     = "#ffe082"
WHITE    = "#e0e0e0"
GRAY     = "#888"

SUIT_COLOR  = {"H": RED, "D": RED, "S": "#111", "C": GREEN}
SUIT_SYMBOL = {"H": "♥", "D": "♦", "S": "♠", "C": "♣"}

W, H = 960, 720
CARD_W, CARD_H = 60, 90
HAND_Y = H - 100


def clabel(card):
    return f"{card.rank}{SUIT_SYMBOL[card.suit]}"


PASS_ORDER = ["left", "right", "across", "none"]
GAME_OVER_SCORE = 100

# ── Game logic ────────────────────────────────────────────────────────────────
class Game:
    def __init__(self, total_scores=None):
        deck = Deck()
        dealt = deck.deal(4)
        self.hands = [Hand(c) for c in dealt]
        self.scores = total_scores[:] if total_scores else [0, 0, 0, 0]
        self.round_scores = [0, 0, 0, 0]
        self.trick = []
        self.trick_num = 0
        self.hearts_broken = False
        self.current = next(i for i, h in enumerate(self.hands) if h.has_2_of_clubs())
        self.bots = [RandomPlayer(), RandomPlayer(), RandomPlayer()]

    def bot_choose(self, p):
        state = {"trick": self.trick, "hearts_broken": self.hearts_broken,
                 "trick_num": self.trick_num, "scores": self.round_scores[:],
                 "player_index": p}
        return self.bots[p - 1].choose_card(self.trick, self.hands[p], state)

    def bot_pass(self, p):
        return self.bots[p - 1].choose_pass(self.hands[p])

    def play(self, p, card):
        self.hands[p].remove(card)
        self.trick.append((p, card))
        if card.suit == "H":
            self.hearts_broken = True

    def resolve_trick(self):
        led = self.trick[0][1].suit
        winner = max(self.trick, key=lambda x: x[1].value if x[1].suit == led else -1)[0]
        pts = sum(c.points() for _, c in self.trick)
        self.round_scores[winner] += pts
        self.trick_num += 1
        self.trick = []
        self.current = winner

    def apply_moon(self):
        for i, s in enumerate(self.round_scores):
            if s == 26:
                self.round_scores = [26 if j != i else 0 for j in range(4)]
                break
        for i in range(4):
            self.scores[i] += self.round_scores[i]

    def do_pass(self, direction, human_cards):
        dir_map = {"left": [1,2,3,0], "right": [3,0,1,2], "across": [2,3,0,1]}
        targets = dir_map[direction]
        all_passes = [human_cards] + [self.bot_pass(i) for i in range(1, 4)]
        for src, cards in enumerate(all_passes):
            for c in cards:
                self.hands[src].remove(c)
                self.hands[targets[src]].cards.append(c)
        self.current = next(i for i, h in enumerate(self.hands) if h.has_2_of_clubs())


# ── UI ────────────────────────────────────────────────────────────────────────
class HeartsUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Hearts")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self.cv = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=0)
        self.cv.pack()
        self.cv.bind("<Button-1>", self._click)

        self.phase = "menu"
        self.game = None
        self.selected = []
        self.pass_dir = "left"
        self.pass_idx = 0          # cycles through PASS_ORDER
        self.total_scores = [0, 0, 0, 0]   # persists across rounds
        self.human_waiting = False

        self._menu()

    # ── Primitives ────────────────────────────────────────────────────────────

    def _c(self):
        self.cv.delete("all")

    def _txt(self, x, y, s, size=12, color=WHITE, bold=False, anchor="center", tag=None):
        kw = dict(text=s, font=("Georgia", size, "bold" if bold else ""),
                  fill=color, anchor=anchor)
        if tag:
            kw["tags"] = tag
        self.cv.create_text(x, y, **kw)

    def _rect(self, x0, y0, x1, y1, fill=BLUE, outline=RED, width=1, tag=None):
        kw = dict(fill=fill, outline=outline, width=width)
        if tag:
            kw["tags"] = tag
        self.cv.create_rectangle(x0, y0, x1, y1, **kw)

    def _draw_card(self, x, y, card, dim=False, sel=False, tag=None):
        t = tag or ("card_" + str(id(card)))
        bg = CARD_SEL if sel else (CARD_DIM if dim else CARD_BG)
        fg = (GRAY if dim else SUIT_COLOR[card.suit])
        x0, y0 = x - CARD_W//2, y - CARD_H//2
        x1, y1 = x + CARD_W//2, y + CARD_H//2
        self.cv.create_rectangle(x0, y0, x1, y1, fill=bg, outline="#bbb", width=1, tags=t)
        self.cv.create_text(x, y, text=clabel(card),
                            font=("Georgia", 13, "bold"), fill=fg, tags=t)

    def _btn(self, x, y, label, tag):
        pw = len(label) * 7 + 28
        self._rect(x - pw//2, y-18, x + pw//2, y+18, fill=RED, outline="", tag=tag)
        self._txt(x, y, label, size=12, bold=True, color=WHITE, tag=tag)

    # ── Hand drawing ──────────────────────────────────────────────────────────

    def _draw_hand(self, selectable=False, mode="play"):
        cards = self.game.hands[0].cards
        n = len(cards)
        if n == 0:
            return
        spacing = min(CARD_W + 6, (W - 100) // n)
        total = spacing * (n - 1) + CARD_W
        sx = (W - total) // 2

        legal_ids = set()
        if mode == "play" and selectable:
            legal = self.game.hands[0].legal_plays(self.game.trick, self.game.hearts_broken)
            legal_ids = set(id(c) for c in legal)

        for i, card in enumerate(cards):
            x = sx + i * spacing
            is_legal = (mode == "pass") or (id(card) in legal_ids)
            self._draw_card(x, HAND_Y, card,
                            dim=(not is_legal and mode == "play"),
                            sel=(card in self.selected),
                            tag=f"hcard_{i}")

    def _hand_card_at(self, x, y):
        cards = self.game.hands[0].cards
        n = len(cards)
        if n == 0:
            return None
        spacing = min(CARD_W + 6, (W - 100) // n)
        total = spacing * (n - 1) + CARD_W
        sx = (W - total) // 2
        for i, card in enumerate(cards):
            cx = sx + i * spacing
            if cx - CARD_W//2 <= x <= cx + CARD_W//2 and \
               HAND_Y - CARD_H//2 <= y <= HAND_Y + CARD_H//2:
                return card
        return None

    # ── Screens ───────────────────────────────────────────────────────────────

    def _menu(self):
        self.phase = "menu"
        self._c()
        cx = W // 2
        self._txt(cx, 200, "♥", size=72, color=RED)
        self._txt(cx, 310, "HEARTS", size=28, bold=True)
        self._txt(cx, 360, "Pass order:  left → right → across → none → repeat",
                  size=11, color=GRAY)
        self._btn(cx, 430, "New Game  →", "btn_deal")

    def _pass_screen(self):
        self.phase = "pass"
        self._c()
        self._txt(W//2, 35, f"Select 3 cards to pass {self.pass_dir}", size=13, color=GRAY)
        cnt = len(self.selected)
        self._txt(W//2, 65, f"{cnt} / 3 selected", size=11,
                  color=GOLD if cnt == 3 else WHITE)
        self._draw_hand(selectable=True, mode="pass")
        if cnt == 3:
            self._btn(W//2, H//2 - 20, "Confirm Pass  →", "btn_pass_confirm")

    def _play_screen(self):
        self._c()

        # Scores
        names = ["You", "Bot1", "Bot2", "Bot3"]
        for i, (nm, ts, rs) in enumerate(zip(names, self.game.scores, self.game.round_scores)):
            self._txt(100 + i * 240, 20, f"{nm}: {ts} (+{rs})", size=10,
                      color=GOLD if i == 0 else WHITE)

        # Table
        cx, cy = W//2, H//2 - 80
        self.cv.create_oval(cx-250, cy-165, cx+250, cy+165,
                            fill=TABLE, outline="#1a4a30", width=2)

        # Seat labels
        seat_pos = [(cx, cy-152), (cx+235, cy), (cx, cy+152), (cx-235, cy)]
        seat_names = ["Bot3", "Bot2", "Bot1", "You"]
        for (sx, sy), sn in zip(seat_pos, seat_names):
            self._txt(sx, sy, sn, size=9, color=GRAY)

        # Cards played in trick
        trick_pos = [(cx, cy-72), (cx+90, cy), (cx, cy+72), (cx-90, cy)]
        seat_map = {0: 3, 1: 2, 2: 1, 3: 0}  # player -> table position
        for pidx, card in self.game.trick:
            tx, ty = trick_pos[seat_map[pidx]]
            self._draw_card(tx, ty, card)

        # Hearts broken
        hb = "♥ broken" if self.game.hearts_broken else "♥ not broken"
        self._txt(W - 65, H - 175, hb, size=9,
                  color=RED if self.game.hearts_broken else GRAY)
        self._txt(65, H - 175, f"Trick {self.game.trick_num + 1} / 13", size=9, color=GRAY)

        # Status
        if self.human_waiting:
            self._txt(W//2, H - 175, "Your turn — click a card", size=11, color=GOLD)
        elif self.game.current != 0:
            self._txt(W//2, H - 175, f"Bot {self.game.current} thinking...",
                      size=11, color=GRAY)

        # Human hand at bottom
        self._draw_hand(selectable=self.human_waiting, mode="play")

    def _round_over_screen(self):
        self.phase = "round_over"
        self._c()
        cx, cy = W//2, H//2
        next_dir = PASS_ORDER[(self.pass_idx + 1) % len(PASS_ORDER)]
        self._rect(cx-230, cy-160, cx+230, cy+160, fill=BLUE, outline=RED, width=2)
        self._txt(cx, cy-130, f"Round Over  —  passing {self.pass_dir}", size=16, bold=True, color=RED)

        names = ["You", "Bot 1", "Bot 2", "Bot 3"]
        for i, (nm, rs, ts) in enumerate(
                zip(names, self.game.round_scores, self.total_scores)):
            self._txt(cx, cy - 75 + i * 38,
                      f"{nm}:  +{rs} this round  ({ts} total)",
                      size=12, color=GOLD if i == 0 else WHITE)

        self._txt(cx, cy + 95, f"Next: pass {next_dir}", size=11, color=GRAY)
        self._btn(cx, cy + 138, "Next Round  →", "btn_next_round")

    def _game_over_screen(self):
        self.phase = "end"
        self._c()
        cx, cy = W//2, H//2
        self._rect(cx-230, cy-170, cx+230, cy+170, fill=BLUE, outline=RED, width=2)
        self._txt(cx, cy-140, "Game Over", size=22, bold=True, color=RED)

        names = ["You", "Bot 1", "Bot 2", "Bot 3"]
        sorted_players = sorted(zip(self.total_scores, names), key=lambda x: x[0])
        for rank, (ts, nm) in enumerate(sorted_players):
            color = GOLD if nm == "You" else WHITE
            medal = ["🥇", "🥈", "🥉", "  "][rank]
            self._txt(cx, cy - 80 + rank * 42,
                      f"{medal}  {nm}:  {ts} pts", size=13, color=color)

        winner = sorted_players[0][1]
        self._txt(cx, cy + 108, f"🏆 {winner} wins the game!", size=14, bold=True, color=GOLD)
        self._btn(cx, cy + 150, "New Game", "btn_again")

    # ── Click handler ─────────────────────────────────────────────────────────

    def _click(self, event):
        x, y = event.x, event.y
        tags = self.cv.gettags(self.cv.find_closest(x, y))

        if self.phase == "menu":
            if "btn_deal" in tags:
                self._new_game()

        elif self.phase == "pass":
            if "btn_pass_confirm" in tags and len(self.selected) == 3:
                self.game.do_pass(self.pass_dir, self.selected)
                self.selected = []
                self._begin_play()
                return
            card = self._hand_card_at(x, y)
            if card:
                if card in self.selected:
                    self.selected.remove(card)
                elif len(self.selected) < 3:
                    self.selected.append(card)
                self._pass_screen()

        elif self.phase == "play" and self.human_waiting:
            card = self._hand_card_at(x, y)
            if card:
                legal = self.game.hands[0].legal_plays(
                    self.game.trick, self.game.hearts_broken)
                if card in legal:
                    self.human_waiting = False
                    self._do_play(0, card)

        elif self.phase == "round_over":
            if "btn_next_round" in tags:
                self._next_round()

        elif self.phase == "end":
            if "btn_again" in tags:
                self._new_game()

    # ── Game flow ─────────────────────────────────────────────────────────────

    def _new_game(self):
        self.game = Game()
        self.selected = []
        self.human_waiting = False
        self.pass_idx = 0
        self.total_scores = [0, 0, 0, 0]
        self.pass_dir = PASS_ORDER[self.pass_idx]
        if self.pass_dir != "none":
            self._pass_screen()
        else:
            self._begin_play()

    def _next_round(self):
        self.pass_idx = (self.pass_idx + 1) % len(PASS_ORDER)
        self.pass_dir = PASS_ORDER[self.pass_idx]
        self.game = Game(total_scores=self.total_scores)
        self.selected = []
        self.human_waiting = False
        if self.pass_dir != "none":
            self._pass_screen()
        else:
            self._begin_play()

    def _begin_play(self):
        self.phase = "play"
        self._next_turn()

    def _next_turn(self):
        if self.game.current == 0:
            self.human_waiting = True
            self._play_screen()
        else:
            self.human_waiting = False
            self._play_screen()
            self.root.after(600, self._bot_turn)

    def _bot_turn(self):
        p = self.game.current
        card = self.game.bot_choose(p)
        self._do_play(p, card)

    def _do_play(self, p, card):
        self.game.play(p, card)
        self._play_screen()
        if len(self.game.trick) == 4:
            self.root.after(900, self._resolve)
        else:
            self.game.current = (p + 1) % 4
            self.root.after(150, self._next_turn)

    def _resolve(self):
        self.game.resolve_trick()
        if self.game.trick_num == 13:
            self.game.apply_moon()
            self.total_scores = self.game.scores[:]
            if max(self.total_scores) >= GAME_OVER_SCORE:
                self.root.after(400, self._game_over_screen)
            else:
                self.root.after(400, self._round_over_screen)
        else:
            self.root.after(200, self._next_turn)


if __name__ == "__main__":
    root = tk.Tk()
    HeartsUI(root)
    root.mainloop()