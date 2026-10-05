"""Saved games (position + history + clocks) stored in SQLite."""
import json

from fastapi import APIRouter, HTTPException, Path

from ..chess.pgn import export_pgn
from ..database import db, now
from ..models import SaveIn
from .games import game_dict, load_game, move_list, safe_state

router = APIRouter()
SID = Path(ge=1, le=2_000_000_000)


def _summary(r):
    d = json.loads(r["data"])
    return {"id": r["id"], "name": r["name"], "created_at": r["created_at"], "mode": d.get("mode"),
            "white": d.get("white"), "black": d.get("black"), "difficulty": d.get("difficulty"),
            "move_count": len(d.get("moves", [])), "fen": r["fen"]}


@router.get("/saved-games")
def list_saved():
    with db() as conn:
        return {"saved": [_summary(r) for r in conn.execute("SELECT * FROM saved_games ORDER BY id DESC")]}


@router.post("/saved-games")
def create_saved(body: SaveIn):
    with db() as conn:
        g = game_dict(load_game(conn, body.game_id))
        ucis = move_list(conn, body.game_id)
        state = safe_state(g["start_fen"], ucis)
        pgn = export_pgn(state["san"], state["status"]["result"], g["white_player"], g["black_player"],
                         start_fen=g["start_fen"])
        data = {"mode": g["mode"], "white": g["white_player"], "black": g["black_player"],
                "human_color": g["human_color"], "difficulty": g["ai_difficulty"],
                "start_fen": g["start_fen"], "moves": ucis, "time_control": g["time_control"],
                "clocks": body.clocks, "turn": state["turn"], "halfmove": state["halfmove"],
                "fullmove": state["fullmove"]}
        cur = conn.execute("INSERT INTO saved_games(name,fen,pgn,data,created_at) VALUES(?,?,?,?,?)",
                           (body.name, state["fen"], pgn, json.dumps(data), now()))
        row = conn.execute("SELECT * FROM saved_games WHERE id=?", (cur.lastrowid,)).fetchone()
        return _summary(row)


@router.get("/saved-games/{sid}")
def get_saved(sid: int = SID):
    with db() as conn:
        r = conn.execute("SELECT * FROM saved_games WHERE id=?", (sid,)).fetchone()
        if not r:
            raise HTTPException(404, "Saved game not found")
        return {"id": r["id"], "name": r["name"], "fen": r["fen"], "pgn": r["pgn"],
                "created_at": r["created_at"], "data": json.loads(r["data"])}


@router.delete("/saved-games/{sid}")
def delete_saved(sid: int = SID):
    with db() as conn:
        cur = conn.execute("DELETE FROM saved_games WHERE id=?", (sid,))
        if not cur.rowcount:
            raise HTTPException(404, "Saved game not found")
        return {"deleted": sid}
