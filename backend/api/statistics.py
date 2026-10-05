"""Statistics endpoint."""
from fastapi import APIRouter

from ..database import db

router = APIRouter()


@router.get("/statistics")
def statistics():
    with db() as conn:
        players = [dict(r) for r in conn.execute(
            "SELECT player_name, games_played, wins, losses, draws FROM statistics ORDER BY wins DESC, games_played DESC")]
        done = "status='finished' AND mode IN ('pvp','pvc')"
        total = conn.execute("SELECT COUNT(*) FROM games WHERE %s" % done).fetchone()[0]
        by_result = {r["result"]: r["n"] for r in conn.execute(
            "SELECT result, COUNT(*) n FROM games WHERE %s GROUP BY result" % done)}
        by_mode = {r["mode"]: r["n"] for r in conn.execute(
            "SELECT mode, COUNT(*) n FROM games WHERE %s GROUP BY mode" % done)}
        vs_ai = []
        for r in conn.execute(
                "SELECT ai_difficulty d, human_color h, result r, COUNT(*) n FROM games "
                "WHERE %s AND mode='pvc' GROUP BY ai_difficulty, human_color, result" % done):
            vs_ai.append(dict(r))
        avg = conn.execute(
            "SELECT AVG(c) FROM (SELECT COUNT(*) c FROM moves WHERE game_id IN "
            "(SELECT id FROM games WHERE %s) GROUP BY game_id)" % done).fetchone()[0]
        return {"total_games": total, "by_result": by_result, "by_mode": by_mode,
                "vs_computer": vs_ai, "average_plies": round(avg or 0, 1), "players": players}
