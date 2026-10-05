"""Local AI endpoints. Search runs in a worker thread so the server stays responsive."""
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from ..chess.ai import AIPlayer
from ..chess.board import Board
from ..chess.fen import FenError
from ..chess.moves import move_to_uci
from ..chess.notation import san
from ..chess.rules import build_state, status
from ..database import db
from ..models import AiMoveIn
from .games import load_game, move_list

router = APIRouter()
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chess-ai")


def _position(body):
    """Return (board, difficulty, human_color) from a game id or a FEN."""
    difficulty, human = body.difficulty, None
    if body.game_id is not None:
        with db() as conn:
            g = load_game(conn, body.game_id)
            ucis = move_list(conn, body.game_id)
            difficulty = difficulty or g["ai_difficulty"]
            human = g["human_color"]
            start = g["start_fen"]
        try:
            st = build_state(start, ucis)
        except ValueError as e:
            raise HTTPException(400, str(e))
        board = Board(st["start_fen"])
        from ..chess.moves import parse_uci
        for u in ucis:
            board.push(parse_uci(board, u))
    elif body.fen:
        try:
            board = Board(body.fen)
        except FenError as e:
            raise HTTPException(400, "Invalid FEN: %s" % e)
    else:
        raise HTTPException(400, "Provide game_id or fen.")
    return board, difficulty or "medium", human


def _compute_move(body):
    board, difficulty, _ = _position(body)
    if status(board)["game_over"]:
        raise HTTPException(409, "Game is already over")
    ai = AIPlayer(difficulty)
    m = ai.get_best_move(board)
    if m is None:
        raise HTTPException(409, "No legal moves")
    return {"move": move_to_uci(m), "san": san(board, m), "difficulty": difficulty, **ai.info}


def _compute_draw(body):
    board, difficulty, human = _position(body)
    ai_color = "b" if human == "w" else "w"
    accept, reason = AIPlayer(difficulty).respond_to_draw(board, ai_color)
    return {"accept": accept, "reason": reason}


@router.post("/ai/move")
async def ai_move(body: AiMoveIn):
    return await asyncio.get_running_loop().run_in_executor(_pool, _compute_move, body)


@router.post("/ai/draw-response")
async def ai_draw(body: AiMoveIn):
    return await asyncio.get_running_loop().run_in_executor(_pool, _compute_draw, body)
