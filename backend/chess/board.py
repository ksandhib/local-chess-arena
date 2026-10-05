"""Board state with make/unmake and position keys."""
from .fen import load_fen, board_to_fen

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Castling rights lost when a piece moves from / to these squares
_RIGHTS_LOST = {60: "KQ", 63: "K", 56: "Q", 4: "kq", 7: "k", 0: "q"}


class Board:
    """Mutable chess position. ``push``/``pop`` make and unmake moves."""

    def __init__(self, fen=START_FEN):
        self.sq = ["."] * 64
        self.turn = "w"
        self.castling = ""
        self.ep = -1
        self.halfmove = 0
        self.fullmove = 1
        self.kpos = {"w": 60, "b": 4}
        self.stack = []
        self.keys = []
        load_fen(self, fen)
        self.keys = [self.key()]

    def fen(self):
        return board_to_fen(self)

    def key(self):
        """Position key (pieces, side, castling, capturable en passant)."""
        ep = ""
        if self.ep >= 0:
            r, c = self.ep >> 3, self.ep & 7
            white = self.turn == "w"
            pr = r + 1 if white else r - 1
            pawn = "P" if white else "p"
            for dc in (-1, 1):
                cc = c + dc
                if 0 <= cc < 8 and 0 <= pr < 8 and self.sq[pr * 8 + cc] == pawn:
                    ep = str(self.ep)
                    break
        return "".join(self.sq) + self.turn + self.castling + ep

    def copy(self):
        b = Board.__new__(Board)
        b.sq = self.sq[:]
        b.turn, b.castling, b.ep = self.turn, self.castling, self.ep
        b.halfmove, b.fullmove = self.halfmove, self.fullmove
        b.kpos = dict(self.kpos)
        b.stack = self.stack[:]
        b.keys = self.keys[:]
        return b

    def repetition_count(self):
        return self.keys.count(self.keys[-1])

    def is_repeat(self):
        """True if the current position already occurred earlier (search use)."""
        n = self.halfmove + 1
        return self.keys[-1] in self.keys[-n - 1:-1]

    def push(self, m):
        f, t, promo = m
        sq = self.sq
        piece = sq[f]
        captured = sq[t]
        cap_sq = t
        us = self.turn
        up = piece.upper()
        old = (self.castling, self.ep, self.halfmove)
        rook_move = None
        if up == "P":
            if t == self.ep and captured == "." and (f & 7) != (t & 7):
                cap_sq = (f & ~7) | (t & 7)
                captured = sq[cap_sq]
                sq[cap_sq] = "."
        elif up == "K":
            if t - f == 2:
                sq[f + 1] = sq[f + 3]
                sq[f + 3] = "."
                rook_move = (f + 3, f + 1)
            elif f - t == 2:
                sq[f - 1] = sq[f - 4]
                sq[f - 4] = "."
                rook_move = (f - 4, f - 1)
            self.kpos[us] = t
        sq[t] = (promo.upper() if us == "w" else promo) if promo else piece
        sq[f] = "."
        c = self.castling
        if c:
            for s in (f, t):
                lost = _RIGHTS_LOST.get(s)
                if lost:
                    for ch in lost:
                        c = c.replace(ch, "")
            self.castling = c
        self.ep = (f + t) // 2 if up == "P" and abs(t - f) == 16 else -1
        self.halfmove = 0 if (up == "P" or captured != ".") else self.halfmove + 1
        if us == "b":
            self.fullmove += 1
        self.turn = "b" if us == "w" else "w"
        self.stack.append((m, piece, captured, cap_sq, rook_move, old))
        self.keys.append(self.key())

    def pop(self):
        m, piece, captured, cap_sq, rook_move, old = self.stack.pop()
        self.keys.pop()
        f, t, _ = m
        sq = self.sq
        us = "b" if self.turn == "w" else "w"
        self.turn = us
        if us == "b":
            self.fullmove -= 1
        sq[f] = piece
        sq[t] = "."
        if captured != ".":
            sq[cap_sq] = captured
        if rook_move:
            a, b = rook_move
            sq[a] = sq[b]
            sq[b] = "."
        if piece in "Kk":
            self.kpos[us] = f
        self.castling, self.ep, self.halfmove = old
