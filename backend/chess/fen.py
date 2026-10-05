"""FEN parsing, validation and export."""
from .moves import is_attacked
from .pieces import square_name, square_index


class FenError(ValueError):
    """Raised when a FEN string is malformed or describes an impossible position."""


def board_to_fen(b):
    rows = []
    for r in range(8):
        row, empty = "", 0
        for c in range(8):
            p = b.sq[r * 8 + c]
            if p == ".":
                empty += 1
            else:
                if empty:
                    row += str(empty)
                    empty = 0
                row += p
        if empty:
            row += str(empty)
        rows.append(row)
    ep = square_name(b.ep) if b.ep >= 0 else "-"
    return "%s %s %s %s %d %d" % ("/".join(rows), b.turn, b.castling or "-", ep, b.halfmove, b.fullmove)


def load_fen(b, fen):
    """Populate board *b* from *fen*; raise FenError with a clear message."""
    if not isinstance(fen, str):
        raise FenError("FEN must be text.")
    if len(fen) > 100:
        raise FenError("FEN is too long.")
    parts = fen.split()
    if len(parts) not in (4, 6):
        raise FenError("FEN needs 6 fields (pieces, turn, castling, en passant, halfmove, fullmove).")
    placement, turn, castling, ep = parts[:4]
    halfmove, fullmove = (parts[4], parts[5]) if len(parts) == 6 else ("0", "1")

    ranks = placement.split("/")
    if len(ranks) != 8:
        raise FenError("Piece placement must have 8 ranks separated by '/'.")
    sq = ["."] * 64
    counts = {}
    for r, rank in enumerate(ranks):
        c = 0
        for ch in rank:
            if ch.isdigit():
                if ch in "09":
                    raise FenError("Rank %d: invalid digit '%s'." % (8 - r, ch))
                c += int(ch)
            elif ch in "KQRBNPkqrbnp":
                if c >= 8:
                    raise FenError("Rank %d has more than 8 squares." % (8 - r))
                sq[r * 8 + c] = ch
                counts[ch] = counts.get(ch, 0) + 1
                c += 1
            else:
                raise FenError("Rank %d: invalid character '%s'." % (8 - r, ch))
        if c != 8:
            raise FenError("Rank %d must describe exactly 8 squares (found %d)." % (8 - r, c))
    if counts.get("K", 0) != 1 or counts.get("k", 0) != 1:
        raise FenError("Each side must have exactly one king.")
    for p in sq[:8] + sq[56:]:
        if p in "Pp":
            raise FenError("Pawns cannot stand on the first or last rank.")
    if counts.get("P", 0) > 8 or counts.get("p", 0) > 8:
        raise FenError("A side cannot have more than 8 pawns.")
    for side in ("KQRBNP", "kqrbnp"):
        if sum(counts.get(x, 0) for x in side) > 16:
            raise FenError("A side cannot have more than 16 pieces.")

    if turn not in ("w", "b"):
        raise FenError("Side to move must be 'w' or 'b'.")

    if castling != "-":
        if not castling or any(ch not in "KQkq" for ch in castling) or len(set(castling)) != len(castling):
            raise FenError("Invalid castling field '%s'." % castling)
        need = {"K": (60, "K", 63, "R"), "Q": (60, "K", 56, "R"),
                "k": (4, "k", 7, "r"), "q": (4, "k", 0, "r")}
        for ch in castling:
            ks, kp, rs, rp = need[ch]
            if sq[ks] != kp or sq[rs] != rp:
                raise FenError("Castling right '%s' does not match king/rook positions." % ch)
        castling = "".join(ch for ch in "KQkq" if ch in castling)
    else:
        castling = ""

    ep_idx = -1
    if ep != "-":
        try:
            ep_idx = square_index(ep)
        except ValueError:
            raise FenError("Invalid en passant square '%s'." % ep)
        row = ep_idx >> 3
        if (turn == "w" and row != 2) or (turn == "b" and row != 5):
            raise FenError("En passant square '%s' is on the wrong rank for the side to move." % ep)
        behind = ep_idx + 8 if turn == "w" else ep_idx - 8   # where the pawn that just moved stands
        origin = ep_idx - 8 if turn == "w" else ep_idx + 8
        pawn = "p" if turn == "w" else "P"
        if sq[ep_idx] != "." or sq[origin] != "." or sq[behind] != pawn:
            raise FenError("En passant square '%s' is inconsistent with the pawns on the board." % ep)

    try:
        hm, fm = int(halfmove), int(fullmove)
    except ValueError:
        raise FenError("Halfmove and fullmove counters must be integers.")
    if hm < 0 or hm > 150:
        raise FenError("Halfmove clock must be between 0 and 150.")
    if fm < 1 or fm > 9999:
        raise FenError("Fullmove number must be between 1 and 9999.")

    b.sq = sq
    b.turn = turn
    b.castling = castling
    b.ep = ep_idx
    b.halfmove = hm
    b.fullmove = fm
    b.kpos = {"w": sq.index("K"), "b": sq.index("k")}
    b.stack = []
    other = "b" if turn == "w" else "w"
    if is_attacked(b, b.kpos[other], turn):
        raise FenError("The side not to move is in check, which is impossible.")


def validate_fen(fen):
    """Return ``(normalised_fen, None)`` or ``(None, error_message)``."""
    from .board import Board
    try:
        return Board(fen).fen(), None
    except FenError as e:
        return None, str(e)
