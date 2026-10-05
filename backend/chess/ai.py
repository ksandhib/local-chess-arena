"""Local chess AI: evaluation, alpha-beta search, move ordering and AIPlayer.

``minimax`` is implemented in negamax form (one function that negates the score
for the opponent), which is mathematically identical to minimax with
alpha-beta pruning. A transposition table keyed by a board hash string is used.
"""
import os
import random
import time

from .moves import (BISHOP_RAYS, ROOK_RAYS, QUEEN_RAYS, is_attacked, is_king_in_check,
                    legal_moves, pseudo_moves)
from .pieces import KING_END_PST, PIECE_VALUES, PST

INF = 10 ** 9
MATE = 100000
MAX_PLY = 64
QS_DEPTH = 6

# Configurable per difficulty. Override with env vars, e.g. CHESS_AI_EXPERT_DEPTH=5
DIFFICULTY = {
    "easy":   {"depth": 1, "time": 1.0,  "random": True},
    "medium": {"depth": 2, "time": 5.0,  "random": False},
    "hard":   {"depth": 3, "time": 10.0, "random": False},
    "expert": {"depth": 5, "time": 20.0, "random": False},
}
for _name, _cfg in DIFFICULTY.items():
    try:
        _cfg["depth"] = int(os.environ.get("CHESS_AI_%s_DEPTH" % _name.upper(), _cfg["depth"]))
        _cfg["time"] = float(os.environ.get("CHESS_AI_%s_TIME" % _name.upper(), _cfg["time"]))
    except ValueError:
        pass

_PSTW = {p: PST[p] for p in "PNBRQK"}
_PSTB = {p: [PST[p][i ^ 56] for i in range(64)] for p in "PNBRQK"}
_KEND_B = [KING_END_PST[i ^ 56] for i in range(64)]
_MOBW = {"B": 3, "R": 2, "Q": 1}
_RAYS = {"B": BISHOP_RAYS, "R": ROOK_RAYS, "Q": QUEEN_RAYS}
_PASSED = [0, 5, 10, 20, 35, 60, 100, 0]


def _mobility(sq, i, p, white):
    n = 0
    for ray in _RAYS[p][i]:
        for t in ray:
            q = sq[t]
            if q == ".":
                n += 1
            else:
                if q.isupper() != white:
                    n += 1
                break
    return n * _MOBW[p]


def evaluate(b):
    """Static evaluation in centipawns from White's point of view.

    Terms: material, piece-square tables, slider mobility, pawn structure
    (doubled / isolated / passed), king safety, centre control, bishop pair.
    """
    sq = b.sq
    score = 0
    npm = 0
    wcols, bcols = [0] * 8, [0] * 8
    wpawns, bpawns = [], []
    wb = bb = 0
    wk = bk = 0
    for i in range(64):
        p = sq[i]
        if p == ".":
            continue
        if p.isupper():
            if p == "P":
                score += 100 + _PSTW["P"][i]
                wcols[i & 7] += 1
                wpawns.append(i)
            elif p == "K":
                wk = i
            else:
                v = PIECE_VALUES[p]
                score += v + _PSTW[p][i]
                npm += v
                if p == "B":
                    wb += 1
                if p in "BRQ":
                    score += _mobility(sq, i, p, True)
        else:
            u = p.upper()
            if u == "P":
                score -= 100 + _PSTB["P"][i]
                bcols[i & 7] += 1
                bpawns.append(i)
            elif u == "K":
                bk = i
            else:
                v = PIECE_VALUES[u]
                score -= v + _PSTB[u][i]
                npm += v
                if u == "B":
                    bb += 1
                if u in "BRQ":
                    score -= _mobility(sq, i, u, False)
    phase = min(npm, 6400) / 6400.0
    score += int(phase * (PST["K"][wk] - PST["K"][bk ^ 56]) + (1 - phase) * (KING_END_PST[wk] - _KEND_B[bk]))
    if wb >= 2:
        score += 30
    if bb >= 2:
        score -= 30
    # pawn structure
    for cols, sign in ((wcols, 1), (bcols, -1)):
        for c in range(8):
            n = cols[c]
            if n > 1:
                score -= sign * 15 * (n - 1)
            if n and (c == 0 or not cols[c - 1]) and (c == 7 or not cols[c + 1]):
                score -= sign * 12 * n
    for i in wpawns:
        r, c = i >> 3, i & 7
        if not any(abs((j & 7) - c) <= 1 and (j >> 3) < r for j in bpawns):
            score += _PASSED[6 - r]
    for i in bpawns:
        r, c = i >> 3, i & 7
        if not any(abs((j & 7) - c) <= 1 and (j >> 3) > r for j in wpawns):
            score -= _PASSED[r - 1]
    # king safety (middlegame weight)
    if phase > 0.3:
        r, c = wk >> 3, wk & 7
        if r >= 6:
            sh = 0
            for dr, w in ((1, 8), (2, 4)):
                for cc in (c - 1, c, c + 1):
                    if 0 <= cc < 8 and sq[(r - dr) * 8 + cc] == "P":
                        sh += w
            score += int(sh * phase)
        if not wcols[c]:
            score -= int(15 * phase)
        r, c = bk >> 3, bk & 7
        if r <= 1:
            sh = 0
            for dr, w in ((1, 8), (2, 4)):
                for cc in (c - 1, c, c + 1):
                    if 0 <= cc < 8 and sq[(r + dr) * 8 + cc] == "p":
                        sh += w
            score -= int(sh * phase)
        if not bcols[c]:
            score += int(15 * phase)
    # centre control
    for s in (27, 28, 35, 36):
        p = sq[s]
        if p == "P":
            score += 10
        elif p == "p":
            score -= 10
        elif p in "NB":
            score += 5
        elif p in "nb":
            score -= 5
    return score


class SearchTimeout(Exception):
    pass


class Search:
    def __init__(self):
        self.tt = {}
        self.killers = [[None, None] for _ in range(MAX_PLY + 4)]
        self.history = {}
        self.nodes = 0
        self.deadline = 0

    # -- helpers ----------------------------------------------------------
    def _tick(self):
        self.nodes += 1
        if not (self.nodes & 1023) and time.time() > self.deadline:
            raise SearchTimeout()

    @staticmethod
    def _eval(b):
        e = evaluate(b)
        return e if b.turn == "w" else -e

    def order(self, b, moves, ply, tt_move, use_checks):
        sq = b.sq
        scored = []
        kil = self.killers[ply]
        for m in moves:
            f, t, promo = m
            s = 0
            if m == tt_move:
                s = 10 ** 7
            else:
                victim = sq[t]
                if victim == "." and sq[f] in "Pp" and (f & 7) != (t & 7):
                    victim = "P"
                if victim != ".":
                    s = 100000 + 10 * PIECE_VALUES[victim.upper()] - PIECE_VALUES[sq[f].upper()] // 10
                elif promo:
                    s = 90000
                elif m == kil[0] or m == kil[1]:
                    s = 50000
                else:
                    s = self.history.get((f, t), 0)
                if promo:
                    s += PIECE_VALUES[promo.upper()]
                if use_checks:
                    b.push(m)
                    if is_king_in_check(b):
                        s += 40000
                    b.pop()
            scored.append((s, m))
        scored.sort(key=lambda x: -x[0])
        return [m for _, m in scored]

    # -- search -----------------------------------------------------------
    def quiesce(self, b, alpha, beta, qd):
        self._tick()
        stand = self._eval(b)
        if stand >= beta:
            return beta
        if stand > alpha:
            alpha = stand
        if qd >= QS_DEPTH:
            return alpha
        us = b.turn
        them = "b" if us == "w" else "w"
        sq = b.sq
        caps = pseudo_moves(b, True)
        caps.sort(key=lambda m: -(PIECE_VALUES[(sq[m[1]] if sq[m[1]] != "." else "P").upper()] * 10
                                  - PIECE_VALUES[sq[m[0]].upper()] // 10))
        for m in caps:
            b.push(m)
            if is_attacked(b, b.kpos[us], them):
                b.pop()
                continue
            score = -self.quiesce(b, -beta, -alpha, qd + 1)
            b.pop()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    def minimax(self, b, depth, alpha, beta, ply):
        """minimax(position, depth) with alpha-beta pruning (negamax form)."""
        self._tick()
        if ply > 0 and (b.halfmove >= 100 or b.is_repeat()):
            return 0
        if ply >= MAX_PLY:
            return self._eval(b)
        us = b.turn
        them = "b" if us == "w" else "w"
        in_chk = is_attacked(b, b.kpos[us], them)
        if in_chk:
            depth += 1
        if depth <= 0:
            return self.quiesce(b, alpha, beta, 0)
        a0 = alpha
        key = b.key()
        tt_move = None
        e = self.tt.get(key)
        if e is not None:
            tt_move = e[3]
            if e[0] >= depth:
                sc = e[2]
                if sc > MATE - 1000:
                    sc -= ply
                elif sc < -MATE + 1000:
                    sc += ply
                if e[1] == 0:
                    return sc
                if e[1] == 1 and sc > alpha:
                    alpha = sc
                elif e[1] == 2 and sc < beta:
                    beta = sc
                if alpha >= beta:
                    return sc
        moves = self.order(b, pseudo_moves(b), ply, tt_move, depth >= 3)
        best, best_move, legal = -INF, None, 0
        for m in moves:
            b.push(m)
            if is_attacked(b, b.kpos[us], them):
                b.pop()
                continue
            legal += 1
            score = -self.minimax(b, depth - 1, -beta, -alpha, ply + 1)
            b.pop()
            if score > best:
                best, best_move = score, m
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        if b.sq[m[1]] == ".":
                            k = self.killers[ply]
                            if k[0] != m:
                                k[1], k[0] = k[0], m
                            self.history[(m[0], m[1])] = self.history.get((m[0], m[1]), 0) + depth * depth
                            if self.history[(m[0], m[1])] > 30000:
                                self.history[(m[0], m[1])] = 30000
                        break
        if legal == 0:
            return -MATE + ply if in_chk else 0
        flag = 0 if a0 < best < beta else (1 if best >= beta else 2)
        sc = best
        if sc > MATE - 1000:
            sc += ply
        elif sc < -MATE + 1000:
            sc -= ply
        if len(self.tt) > 400000:
            self.tt.clear()
        self.tt[key] = (depth, flag, sc, best_move)
        return best

    def search(self, board, max_depth, time_limit):
        """Iterative deepening. Returns (move, score, depth, nodes)."""
        b = board.copy()
        self.deadline = time.time() + time_limit
        self.nodes = 0
        moves = legal_moves(b)
        if not moves:
            return None, 0, 0, 0
        best, best_score, reached = moves[0], 0, 0
        if len(moves) == 1:
            return best, 0, 0, 0
        for depth in range(1, max_depth + 1):
            try:
                alpha, cur = -INF, None
                for m in self.order(b, moves, 0, best, False):
                    b.push(m)
                    score = -self.minimax(b, depth - 1, -INF, -alpha, 1)
                    b.pop()
                    if cur is None or score > alpha:
                        alpha, cur = score, m
            except SearchTimeout:
                break
            best, best_score, reached = cur, alpha, depth
            if abs(alpha) > MATE - 100:
                break
        return best, best_score, reached, self.nodes


class AIPlayer:
    """Local AI opponent. ``AIPlayer.get_best_move(position, depth)``."""

    def __init__(self, difficulty="medium", rng=None):
        if difficulty not in DIFFICULTY:
            raise ValueError("Unknown difficulty: %s" % difficulty)
        self.difficulty = difficulty
        self.cfg = DIFFICULTY[difficulty]
        self.rng = rng or random.Random()
        self.search = Search()
        self.info = {}

    def get_best_move(self, board, depth=None, time_limit=None):
        legal = legal_moves(board)
        if not legal:
            return None
        t0 = time.time()
        if self.cfg["random"] and depth is None:
            weights = []
            for m in legal:
                cap = board.sq[m[1]] != "." or (board.sq[m[0]] in "Pp" and (m[0] & 7) != (m[1] & 7))
                weights.append(5 if cap or m[2] == "q" else 1)
            move = self.rng.choices(legal, weights)[0]
            self.info = {"depth": 0, "score": 0, "nodes": 0, "elapsed_ms": int((time.time() - t0) * 1000)}
            return move
        d = depth if depth is not None else self.cfg["depth"]
        tl = time_limit if time_limit is not None else self.cfg["time"]
        move, score, reached, nodes = self.search.search(board, d, tl)
        self.info = {"depth": reached, "score": score, "nodes": nodes,
                     "elapsed_ms": int((time.time() - t0) * 1000)}
        return move

    def respond_to_draw(self, board, ai_color):
        """Deterministic draw-offer rule: accept when the AI judges itself clearly worse."""
        _, score, _, _ = Search().search(board, 2, 3.0)
        if board.turn != ai_color:
            score = -score
        if score <= -100:
            return True, "Computer accepts: it evaluates the position as slightly worse for itself."
        return False, "Computer declines: it does not evaluate the position as worse for itself."
