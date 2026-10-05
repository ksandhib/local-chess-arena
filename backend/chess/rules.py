"""Game status (check, mate, draws) and replay-based state building."""
from .board import Board, START_FEN
from .moves import legal_moves, is_king_in_check, parse_uci, move_to_uci
from .notation import san
from .pieces import PIECE_VALUES, square_name


def insufficient_material(b):
    """K v K, K+minor v K, or only bishops all on one colour square."""
    minors, bishops_sq = [], []
    for i, p in enumerate(b.sq):
        if p in ".Kk":
            continue
        up = p.upper()
        if up in "PRQ":
            return False
        minors.append(up)
        if up == "B":
            bishops_sq.append(((i >> 3) + (i & 7)) & 1)
    if len(minors) <= 1:
        return True
    if all(x == "B" for x in minors) and len(set(bishops_sq)) == 1:
        return True
    return False


def can_win_on_time(b, color):
    """Could *color* still checkmate? Used to turn a lost-on-time into a draw."""
    mine = [p.upper() for p in b.sq if p not in ".Kk" and p.isupper() == (color == "w")]
    theirs = [p for p in b.sq if p not in ".Kk" and p.isupper() != (color == "w")]
    if any(p in "PRQ" for p in mine) or len(mine) >= 2:
        return True
    if len(mine) == 1:
        return bool(theirs)
    return False


def status(b, legal=None):
    """Return a dict describing the position's game state."""
    legal = legal if legal is not None else legal_moves(b)
    check = is_king_in_check(b)
    s = {"check": check, "checkmate": False, "stalemate": False, "game_over": False,
         "result": "*", "termination": None, "winner": None, "draw_reason": None,
         "repetitions": b.repetition_count()}

    def end(result, term, winner=None):
        s.update(game_over=True, result=result, termination=term, winner=winner)
        if result == "1/2-1/2":
            s["draw_reason"] = term

    if not legal:
        if check:
            s["checkmate"] = True
            end("0-1" if b.turn == "w" else "1-0", "checkmate", "b" if b.turn == "w" else "w")
        else:
            s["stalemate"] = True
            end("1/2-1/2", "stalemate")
    elif insufficient_material(b):
        end("1/2-1/2", "insufficient material")
    elif s["repetitions"] >= 5:
        end("1/2-1/2", "fivefold repetition")
    elif b.halfmove >= 150:
        end("1/2-1/2", "seventy-five-move rule")
    elif s["repetitions"] >= 3:
        end("1/2-1/2", "threefold repetition")
    elif b.halfmove >= 100:
        end("1/2-1/2", "fifty-move rule")
    return s


def material_balance(b):
    """White minus black material in pawns (kings excluded)."""
    total = 0
    for p in b.sq:
        if p in ".Kk":
            continue
        v = PIECE_VALUES[p.upper()]
        total += v if p.isupper() else -v
    return round(total / 100, 1)


def build_state(start_fen, ucis):
    """Replay *ucis* from *start_fen* validating every move; return full state dict.

    Raises ValueError("... (move N)") for the first illegal move.
    """
    b = Board(start_fen or START_FEN)
    start_turn, start_full = b.turn, b.fullmove
    sans, fens, captured = [], [b.fen()], {"w": [], "b": []}
    for n, u in enumerate(ucis):
        legal = legal_moves(b)
        try:
            m = parse_uci(b, u, legal)
        except ValueError as e:
            raise ValueError("%s (move %d)" % (e, n + 1))
        if status(b, legal)["game_over"]:
            raise ValueError("Game is already over (move %d)" % (n + 1))
        sans.append(san(b, m, legal))
        mover = b.turn
        victim = b.sq[m[1]]
        if victim == "." and b.sq[m[0]] in "Pp" and m[1] == b.ep and (m[0] & 7) != (m[1] & 7):
            victim = "p" if mover == "w" else "P"
        if victim != ".":
            captured[mover].append(victim)
        b.push(m)
        fens.append(b.fen())
    legal = legal_moves(b)
    st = status(b, legal)
    for side in "wb":
        captured[side].sort(key=lambda p: -PIECE_VALUES[p.upper()])
    last = None
    if ucis:
        last = ucis[-1]
    return {
        "fen": b.fen(), "start_fen": fens[0], "turn": b.turn, "fullmove": b.fullmove,
        "halfmove": b.halfmove, "ply": len(ucis), "start_turn": start_turn,
        "start_fullmove": start_full, "moves": list(ucis), "san": sans, "fens": fens,
        "legal": [move_to_uci(m) for m in legal], "check": st["check"],
        "check_square": square_name(b.kpos[b.turn]) if st["check"] else None,
        "status": st, "captured": captured, "material": material_balance(b),
        "last_move": last,
    }


def validate_puzzle(fen, solution, goal):
    """Check a puzzle: legal alternating solution of odd length; mate goal ends in mate."""
    if not isinstance(solution, list) or not solution or len(solution) % 2 == 0:
        raise ValueError("Solution must list an odd number of moves (yours, reply, yours...).")
    if goal not in ("mate", "tactic"):
        raise ValueError("Goal must be 'mate' or 'tactic'.")
    st = build_state(fen, solution)
    if goal == "mate" and not st["status"]["checkmate"]:
        raise ValueError("A 'mate' puzzle must end in checkmate.")
    return st
