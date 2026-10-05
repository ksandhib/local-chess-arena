"""Puzzle list, creation, attempt checking and hints."""
import json

from fastapi import APIRouter, HTTPException, Path

from ..chess.board import Board
from ..chess.fen import validate_fen
from ..chess.moves import legal_moves, move_to_uci, parse_uci
from ..chess.rules import status, validate_puzzle
from ..database import db, now
from ..models import AttemptIn, HintIn, PuzzleIn

router = APIRouter()
PID = Path(ge=1, le=2_000_000_000)


def _row(conn, pid):
    r = conn.execute("SELECT * FROM puzzles WHERE id=?", (pid,)).fetchone()
    if not r:
        raise HTTPException(404, "Puzzle not found")
    return r


def _public(r):
    b = Board(r["fen"])
    return {"id": r["id"], "title": r["title"], "description": r["description"], "fen": r["fen"],
            "goal": r["goal"], "difficulty": r["difficulty"], "side": b.turn,
            "solution_length": len(json.loads(r["solution"]))}


def _replay(fen, moves):
    b = Board(fen)
    for m in moves:
        b.push(parse_uci(b, m))
    return b


@router.get("/puzzles")
def list_puzzles():
    with db() as conn:
        return {"puzzles": [_public(r) for r in conn.execute("SELECT * FROM puzzles ORDER BY id")]}


@router.get("/puzzles/{pid}")
def get_puzzle(pid: int = PID):
    with db() as conn:
        return _public(_row(conn, pid))


@router.post("/puzzles")
def create_puzzle(body: PuzzleIn):
    norm, err = validate_fen(body.fen)
    if err:
        raise HTTPException(400, "Invalid FEN: %s" % err)
    try:
        validate_puzzle(norm, body.solution, body.goal)
    except ValueError as e:
        raise HTTPException(400, str(e))
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO puzzles(slug,title,description,fen,goal,solution,difficulty,created_at) VALUES(NULL,?,?,?,?,?,?,?)",
            (body.title, body.description, norm, body.goal, json.dumps(body.solution), body.difficulty, now()))
        return _public(_row(conn, cur.lastrowid))


@router.post("/puzzles/{pid}/attempt")
def attempt(body: AttemptIn, pid: int = PID):
    """*moves* = every move played so far (yours and the replies this API returned)."""
    with db() as conn:
        p = _row(conn, pid)
    sol = json.loads(p["solution"])
    moves = body.moves
    k = len(moves) - 1
    if k % 2 != 0 or k >= len(sol):
        raise HTTPException(400, "Moves do not match this puzzle's progress.")
    if moves[:k] != sol[:k]:
        raise HTTPException(400, "Earlier moves do not match the puzzle line.")
    b = _replay(p["fen"], moves[:k])
    try:
        m = parse_uci(b, moves[k])
    except ValueError:
        return {"legal": False, "correct": False, "complete": False, "message": "That move is not legal."}
    last = k == len(sol) - 1
    correct = moves[k] == sol[k]
    if not correct and last and p["goal"] == "mate":
        b.push(m)
        correct = status(b)["checkmate"]
    if not correct:
        return {"legal": True, "correct": False, "complete": False, "message": "Not the solution. Try again."}
    if last:
        return {"legal": True, "correct": True, "complete": True, "reply": None,
                "message": "Solved!"}
    return {"legal": True, "correct": True, "complete": False, "reply": sol[k + 1],
            "message": "Correct. Keep going."}


@router.post("/puzzles/{pid}/hint")
def hint(body: HintIn, pid: int = PID):
    with db() as conn:
        p = _row(conn, pid)
    sol = json.loads(p["solution"])
    k = len(body.moves)
    if k % 2 != 0 or k >= len(sol) or body.moves != sol[:k]:
        raise HTTPException(400, "Moves do not match this puzzle's progress.")
    mv = sol[k]
    return {"from": mv[:2], "to": mv[2:4] if body.level >= 2 else None}
