"""Move generation, attack detection and legal move validation.

A move is a tuple ``(from_square, to_square, promotion)`` where *promotion* is
'' or one of 'q', 'r', 'b', 'n'. Castling is a king move of two files; en
passant is a pawn capture onto ``board.ep``.
"""
import re

from .pieces import square_name, square_index, opponent


def _build_tables():
    knight, king = [[] for _ in range(64)], [[] for _ in range(64)]
    rook_rays, bishop_rays = [[] for _ in range(64)], [[] for _ in range(64)]
    pawn_att = {"w": [[] for _ in range(64)], "b": [[] for _ in range(64)]}
    for s in range(64):
        r, c = s >> 3, s & 7
        for dr, dc in ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8:
                knight[s].append(rr * 8 + cc)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if (dr or dc) and 0 <= rr < 8 and 0 <= cc < 8:
                    king[s].append(rr * 8 + cc)
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ray, rr, cc = [], r + dr, c + dc
            while 0 <= rr < 8 and 0 <= cc < 8:
                ray.append(rr * 8 + cc)
                rr, cc = rr + dr, cc + dc
            if ray:
                rook_rays[s].append(ray)
        for dr, dc in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            ray, rr, cc = [], r + dr, c + dc
            while 0 <= rr < 8 and 0 <= cc < 8:
                ray.append(rr * 8 + cc)
                rr, cc = rr + dr, cc + dc
            if ray:
                bishop_rays[s].append(ray)
        for dc in (-1, 1):
            if 0 <= c + dc < 8:
                if r + 1 < 8:
                    pawn_att["w"][s].append((r + 1) * 8 + c + dc)   # white pawn below s attacks s
                if r - 1 >= 0:
                    pawn_att["b"][s].append((r - 1) * 8 + c + dc)   # black pawn above s attacks s
    return knight, king, rook_rays, bishop_rays, pawn_att


KNIGHT, KING, ROOK_RAYS, BISHOP_RAYS, PAWN_ATT = _build_tables()
QUEEN_RAYS = [ROOK_RAYS[s] + BISHOP_RAYS[s] for s in range(64)]


def is_attacked(b, s, by):
    """isSquareAttacked(): is square *s* attacked by any piece of colour *by*?"""
    sq = b.sq
    if by == "w":
        pawn, knight, king, rook, bishop, queen = "P", "N", "K", "R", "B", "Q"
    else:
        pawn, knight, king, rook, bishop, queen = "p", "n", "k", "r", "b", "q"
    for t in PAWN_ATT[by][s]:
        if sq[t] == pawn:
            return True
    for t in KNIGHT[s]:
        if sq[t] == knight:
            return True
    for t in KING[s]:
        if sq[t] == king:
            return True
    for ray in ROOK_RAYS[s]:
        for t in ray:
            p = sq[t]
            if p != ".":
                if p == rook or p == queen:
                    return True
                break
    for ray in BISHOP_RAYS[s]:
        for t in ray:
            p = sq[t]
            if p != ".":
                if p == bishop or p == queen:
                    return True
                break
    return False


def is_king_in_check(b, color=None):
    """isKingInCheck()."""
    color = color or b.turn
    return is_attacked(b, b.kpos[color], opponent(color))


def pseudo_moves(b, captures_only=False):
    """Pseudo-legal moves (may leave own king in check) for the side to move."""
    sq = b.sq
    white = b.turn == "w"
    out = []
    add = out.append
    for f in range(64):
        p = sq[f]
        if p == "." or p.isupper() != white:
            continue
        up = p.upper()
        if up == "P":
            r, c = f >> 3, f & 7
            if white:
                step, start_row, promo_row = -8, 6, 1
            else:
                step, start_row, promo_row = 8, 1, 6
            t = f + step
            if sq[t] == ".":
                if r == promo_row:
                    for pr in ("q" if captures_only else "qrbn"):
                        add((f, t, pr))
                elif not captures_only:
                    add((f, t, ""))
                    if r == start_row and sq[t + step] == ".":
                        add((f, t + step, ""))
            for dc in (-1, 1):
                cc = c + dc
                if 0 <= cc < 8:
                    t = f + step + dc
                    q = sq[t]
                    if (q != "." and q.isupper() != white) or (q == "." and t == b.ep):
                        if r == promo_row:
                            for pr in "qrbn":
                                add((f, t, pr))
                        else:
                            add((f, t, ""))
        elif up == "N":
            for t in KNIGHT[f]:
                q = sq[t]
                if q == ".":
                    if not captures_only:
                        add((f, t, ""))
                elif q.isupper() != white:
                    add((f, t, ""))
        elif up == "K":
            for t in KING[f]:
                q = sq[t]
                if q == ".":
                    if not captures_only:
                        add((f, t, ""))
                elif q.isupper() != white:
                    add((f, t, ""))
            if not captures_only and b.castling:
                _castling(b, f, white, add)
        else:
            rays = ROOK_RAYS[f] if up == "R" else BISHOP_RAYS[f] if up == "B" else QUEEN_RAYS[f]
            for ray in rays:
                for t in ray:
                    q = sq[t]
                    if q == ".":
                        if not captures_only:
                            add((f, t, ""))
                        continue
                    if q.isupper() != white:
                        add((f, t, ""))
                    break
    return out


def _castling(b, f, white, add):
    sq, c = b.sq, b.castling
    if white:
        if f != 60:
            return
        if "K" in c and sq[61] == "." and sq[62] == "." and sq[63] == "R" \
                and not is_attacked(b, 60, "b") and not is_attacked(b, 61, "b") and not is_attacked(b, 62, "b"):
            add((60, 62, ""))
        if "Q" in c and sq[59] == "." and sq[58] == "." and sq[57] == "." and sq[56] == "R" \
                and not is_attacked(b, 60, "b") and not is_attacked(b, 59, "b") and not is_attacked(b, 58, "b"):
            add((60, 58, ""))
    else:
        if f != 4:
            return
        if "k" in c and sq[5] == "." and sq[6] == "." and sq[7] == "r" \
                and not is_attacked(b, 4, "w") and not is_attacked(b, 5, "w") and not is_attacked(b, 6, "w"):
            add((4, 6, ""))
        if "q" in c and sq[3] == "." and sq[2] == "." and sq[1] == "." and sq[0] == "r" \
                and not is_attacked(b, 4, "w") and not is_attacked(b, 3, "w") and not is_attacked(b, 2, "w"):
            add((4, 2, ""))


def legal_moves(b):
    """generateLegalMoves(): pseudo-legal moves filtered so the mover's king is safe."""
    us = b.turn
    them = opponent(us)
    out = []
    for m in pseudo_moves(b):
        b.push(m)
        if not is_attacked(b, b.kpos[us], them):
            out.append(m)
        b.pop()
    return out


def is_legal_move(b, m):
    """isLegalMove(): true when *m* is in the legal move list."""
    return m in legal_moves(b)


def move_to_uci(m):
    return square_name(m[0]) + square_name(m[1]) + m[2]


_UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


def parse_uci(b, text, legal=None):
    """Convert a UCI string to a legal move tuple or raise ValueError."""
    if not isinstance(text, str) or not _UCI_RE.match(text):
        raise ValueError("Invalid move format: %r" % (text,))
    m = (square_index(text[:2]), square_index(text[2:4]), text[4:])
    legal = legal if legal is not None else legal_moves(b)
    if m in legal:
        return m
    if not m[2] and (m[0], m[1], "q") in legal:
        raise ValueError("Promotion piece required")
    raise ValueError("Illegal move: %s" % text)
