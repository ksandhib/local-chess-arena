"""Standard algebraic notation (SAN) generation and parsing."""
from .moves import legal_moves, is_king_in_check
from .pieces import FILES, square_name


def san_core(b, m, legal=None):
    """SAN without the check / mate suffix. Call *before* pushing the move."""
    f, t, promo = m
    piece = b.sq[f]
    up = piece.upper()
    if up == "K" and abs((t & 7) - (f & 7)) == 2:
        return "O-O" if t > f else "O-O-O"
    capture = b.sq[t] != "." or (up == "P" and t == b.ep and (f & 7) != (t & 7))
    if up == "P":
        s = (FILES[f & 7] + "x" if capture else "") + square_name(t)
        if promo:
            s += "=" + promo.upper()
        return s
    legal = legal if legal is not None else legal_moves(b)
    others = [x for x in legal if x[1] == t and x[0] != f and b.sq[x[0]] == piece]
    dis = ""
    if others:
        if all((x[0] & 7) != (f & 7) for x in others):
            dis = FILES[f & 7]
        elif all((x[0] >> 3) != (f >> 3) for x in others):
            dis = str(8 - (f >> 3))
        else:
            dis = square_name(f)
    return up + dis + ("x" if capture else "") + square_name(t)


def san(b, m, legal=None):
    """Full SAN including '+' or '#'. Call *before* pushing the move."""
    s = san_core(b, m, legal)
    b.push(m)
    if is_king_in_check(b):
        s += "#" if not legal_moves(b) else "+"
    b.pop()
    return s


def _norm(text):
    return text.replace("0", "O").rstrip("+#!?").replace("e.p.", "").strip()


def parse_san(b, text):
    """Return the legal move matching SAN *text* or raise ValueError."""
    want = _norm(text)
    if not want:
        raise ValueError("Empty move")
    legal = legal_moves(b)
    for m in legal:
        if san_core(b, m, legal) == want:
            return m
    # tolerate a missing '=' in promotions (e8Q) and over-specified squares (Ng1f3)
    for m in legal:
        core = san_core(b, m, legal)
        if core.replace("=", "") == want.replace("=", ""):
            return m
        if m[2] == "" and b.sq[m[0]].upper() != "P" and want[1:3] == square_name(m[0]) \
                and core[0] + want[3:] == want[0] + want[3:] and want[3:].lstrip("x") == square_name(m[1]):
            return m
    raise ValueError("Illegal or unreadable move: %s" % text)
