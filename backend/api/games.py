"""Games, positions, FEN and PGN endpoints."""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query

from ..chess.board import Board, START_FEN
from ..chess.fen import FenError, validate_fen
from ..chess.pgn import export_pgn, parse_pgn
from ..chess.rules import build_state, can_win_on_time
from ..database import db, now
from ..models import (FenIn, FinishIn, GameCreate, MoveIn, PgnExportIn, PgnIn,
                      PositionIn, UndoIn)

router = APIRouter()
GID = Path(ge=1, le=2_000_000_000)


def load_game(conn, gid):
    row = conn.execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
    if not row:
        raise HTTPException(404, "Game not found")
    return row


def move_list(conn, gid):
    return [r["uci"] for r in conn.execute("SELECT uci FROM moves WHERE game_id=? ORDER BY ply", (gid,))]


def safe_state(start_fen, ucis):
    try:
        return build_state(start_fen, ucis)
    except FenError as e:
        raise HTTPException(400, "Invalid FEN: %s" % e)
    except ValueError as e:
        raise HTTPException(400, str(e))


def game_dict(g):
    d = dict(g)
    d["time_control"] = json.loads(d["time_control"]) if d.get("time_control") else None
    return d


def finish_game(conn, g, result, termination, status="finished"):
    conn.execute("UPDATE games SET result=?, termination=?, status=?, ended_at=? WHERE id=?",
                 (result, termination, status, now(), g["id"]))
    if status != "finished" or g["mode"] not in ("pvp", "pvc"):
        return
    sides = [("w", g["white_player"]), ("b", g["black_player"])]
    for side, name in sides:
        if g["mode"] == "pvc" and g["human_color"] != side:
            continue
        outcome = "draws" if result == "1/2-1/2" else ("wins" if (result == "1-0") == (side == "w") else "losses")
        conn.execute("INSERT OR IGNORE INTO statistics(player_name) VALUES(?)", (name,))
        conn.execute("UPDATE statistics SET games_played=games_played+1, %s=%s+1 WHERE player_name=?" % (outcome, outcome),
                     (name,))


@router.get("/games")
def list_games(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    with db() as conn:
        rows = conn.execute(
            "SELECT g.*, (SELECT COUNT(*) FROM moves m WHERE m.game_id=g.id) AS move_count "
            "FROM games g ORDER BY g.id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        return {"total": total, "games": [game_dict(r) for r in rows]}


@router.post("/games")
def create_game(body: GameCreate):
    fen = body.start_fen or START_FEN
    norm, err = validate_fen(fen)
    if err:
        raise HTTPException(400, "Invalid FEN: %s" % err)
    state = safe_state(norm, body.moves)
    if body.mode == "pvc" and (not body.human_color or not body.difficulty):
        raise HTTPException(400, "Player vs computer needs human_color and difficulty.")
    white, black = body.white, body.black
    with db() as conn:
        for n in (white, black):
            conn.execute("INSERT OR IGNORE INTO players(name, created_at) VALUES(?,?)", (n, now()))
        cur = conn.execute(
            "INSERT INTO games(white_player,black_player,mode,ai_difficulty,human_color,start_fen,time_control,started_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (white, black, body.mode, body.difficulty, body.human_color, norm,
             json.dumps(body.time_control.model_dump()) if body.time_control else None, now()))
        gid = cur.lastrowid
        for i, u in enumerate(body.moves):
            ply_white = (state["start_turn"] == "w") == (i % 2 == 0)
            num = state["start_fullmove"] + (i + (0 if state["start_turn"] == "w" else 1)) // 2
            conn.execute("INSERT INTO moves(game_id,ply,move_number,side,uci,notation,fen) VALUES(?,?,?,?,?,?,?)",
                         (gid, i, num, "w" if ply_white else "b", u, state["san"][i], state["fens"][i + 1]))
        g = load_game(conn, gid)
        if state["status"]["game_over"]:
            finish_game(conn, g, state["status"]["result"], state["status"]["termination"])
            g = load_game(conn, gid)
        return {"game": game_dict(g), "state": state}


@router.get("/games/{gid}")
def get_game(gid: int = GID):
    with db() as conn:
        g = load_game(conn, gid)
        return {"game": game_dict(g), "state": safe_state(g["start_fen"], move_list(conn, gid))}


@router.post("/games/{gid}/moves")
def post_move(body: MoveIn, gid: int = GID):
    with db() as conn:
        g = load_game(conn, gid)
        if g["status"] != "active":
            raise HTTPException(409, "Game is not active")
        ucis = move_list(conn, gid)
        cur = safe_state(g["start_fen"], ucis)
        if cur["status"]["game_over"]:
            raise HTTPException(409, "Game is already over")
        if body.uci not in cur["legal"]:
            raise HTTPException(400, "Illegal move: %s" % body.uci)
        new = safe_state(g["start_fen"], ucis + [body.uci])
        ply = len(ucis)
        conn.execute("INSERT INTO moves(game_id,ply,move_number,side,uci,notation,fen) VALUES(?,?,?,?,?,?,?)",
                     (gid, ply, cur["fullmove"], cur["turn"], body.uci, new["san"][-1], new["fen"]))
        if new["status"]["game_over"]:
            finish_game(conn, g, new["status"]["result"], new["status"]["termination"])
        g = load_game(conn, gid)
        return {"game": game_dict(g), "state": new}


@router.post("/games/{gid}/undo")
def undo(body: UndoIn, gid: int = GID):
    with db() as conn:
        g = load_game(conn, gid)
        if g["status"] != "active":
            raise HTTPException(409, "Finished games cannot be changed")
        ucis = move_list(conn, gid)
        if body.count > len(ucis):
            raise HTTPException(400, "Not enough moves to undo")
        keep = len(ucis) - body.count
        conn.execute("DELETE FROM moves WHERE game_id=? AND ply>=?", (gid, keep))
        return {"game": game_dict(g), "state": safe_state(g["start_fen"], ucis[:keep]), "undone": ucis[keep:]}


@router.post("/games/{gid}/finish")
def finish(body: FinishIn, gid: int = GID):
    with db() as conn:
        g = load_game(conn, gid)
        if g["status"] != "active":
            raise HTTPException(409, "Game is not active")
        ucis = move_list(conn, gid)
        state = safe_state(g["start_fen"], ucis)
        if body.termination == "abandoned":
            finish_game(conn, g, "*", "abandoned", status="abandoned")
        elif body.termination == "agreement":
            finish_game(conn, g, "1/2-1/2", "agreement")
        else:
            if body.loser not in ("w", "b"):
                raise HTTPException(400, "loser is required")
            win_result = "0-1" if body.loser == "w" else "1-0"
            if body.termination == "time":
                winner = "b" if body.loser == "w" else "w"
                if not can_win_on_time(Board(state["fen"]), winner):
                    finish_game(conn, g, "1/2-1/2", "timeout vs insufficient material")
                else:
                    finish_game(conn, g, win_result, "time")
            else:
                finish_game(conn, g, win_result, "resignation")
        g = load_game(conn, gid)
        return {"game": game_dict(g), "state": state}


@router.delete("/games/{gid}")
def delete_game(gid: int = GID):
    with db() as conn:
        load_game(conn, gid)
        conn.execute("DELETE FROM games WHERE id=?", (gid,))
        return {"deleted": gid}


@router.post("/position")
def position(body: PositionIn):
    return safe_state(body.start_fen or START_FEN, body.moves)


@router.post("/fen/validate")
def fen_validate(body: FenIn):
    norm, err = validate_fen(body.fen)
    return {"valid": err is None, "fen": norm, "error": err}


@router.post("/pgn/parse")
def pgn_parse(body: PgnIn):
    try:
        headers, start_fen, ucis, result = parse_pgn(body.pgn)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"headers": headers, "start_fen": start_fen, "moves": ucis, "result": result,
            "state": safe_state(start_fen, ucis)}


@router.post("/pgn/export")
def pgn_export(body: PgnExportIn):
    start = body.start_fen or START_FEN
    state = safe_state(start, body.moves)
    result = state["status"]["result"] if state["status"]["game_over"] else body.result
    return {"pgn": export_pgn(state["san"], result, body.white, body.black, start_fen=state["start_fen"])}
