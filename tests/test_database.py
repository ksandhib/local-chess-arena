import json
import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp()
os.environ["CHESS_DB"] = os.path.join(_tmp, "test.db")

from backend import database                      # noqa: E402
from backend.api import games, puzzles, saved_games, statistics   # noqa: E402
from backend.models import GameCreate, MoveIn, SaveIn, FinishIn, UndoIn, PuzzleIn, AttemptIn   # noqa: E402
from fastapi import HTTPException                 # noqa: E402


class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.DB_PATH = database.Path(os.environ["CHESS_DB"])
        database.init_db()

    def test_tables_exist(self):
        with database.db() as c:
            names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"players", "games", "moves", "saved_games", "puzzles", "statistics"} <= names)

    def test_puzzles_seeded_and_valid(self):
        listing = puzzles.list_puzzles()["puzzles"]
        self.assertGreaterEqual(len(listing), 10)

    def _new(self, **kw):
        body = dict(mode="pvp", white="Alice", black="Bob")
        body.update(kw)
        return games.create_game(GameCreate(**body))

    def test_full_game_and_statistics(self):
        gid = self._new()["game"]["id"]
        for u in ("f2f3", "e7e5", "g2g4", "d8h4"):
            res = games.post_move(MoveIn(uci=u), gid)
        self.assertEqual(res["game"]["result"], "0-1")
        self.assertEqual(res["game"]["termination"], "checkmate")
        with self.assertRaises(HTTPException) as cm:
            games.post_move(MoveIn(uci="a2a3"), gid)
        self.assertEqual(cm.exception.status_code, 409)
        stats = {p["player_name"]: p for p in statistics.statistics()["players"]}
        self.assertEqual(stats["Bob"]["wins"], 1)
        self.assertEqual(stats["Alice"]["losses"], 1)

    def test_illegal_move_rejected_by_server(self):
        gid = self._new()["game"]["id"]
        with self.assertRaises(HTTPException) as cm:
            games.post_move(MoveIn(uci="e2e5"), gid)
        self.assertEqual(cm.exception.status_code, 400)

    def test_undo_and_resign(self):
        gid = self._new()["game"]["id"]
        games.post_move(MoveIn(uci="e2e4"), gid)
        games.post_move(MoveIn(uci="e7e5"), gid)
        r = games.undo(UndoIn(count=2), gid)
        self.assertEqual(r["state"]["ply"], 0)
        self.assertEqual(r["undone"], ["e2e4", "e7e5"])
        with self.assertRaises(HTTPException):
            games.undo(UndoIn(count=1), gid)
        fin = games.finish(FinishIn(termination="resignation", loser="w"), gid)
        self.assertEqual(fin["game"]["result"], "0-1")

    def test_time_loss_against_bare_king_is_draw(self):
        gid = self._new(start_fen="8/8/4k3/8/8/3K4/R7/8 w - - 0 1")["game"]["id"]
        fin = games.finish(FinishIn(termination="time", loser="w"), gid)   # black has only a king
        self.assertEqual(fin["game"]["result"], "1/2-1/2")

    def test_save_and_load(self):
        gid = self._new(mode="pvc", human_color="w", difficulty="easy", black="Computer (Easy)",
                        time_control={"base": 300, "inc": 2})["game"]["id"]
        games.post_move(MoveIn(uci="d2d4"), gid)
        s = saved_games.create_saved(SaveIn(name="my save", game_id=gid, clocks={"w": 290000, "b": 300000}))
        data = saved_games.get_saved(s["id"])["data"]
        self.assertEqual(data["moves"], ["d2d4"])
        self.assertEqual(data["clocks"]["w"], 290000)
        self.assertEqual(data["time_control"], {"base": 300, "inc": 2})
        again = games.create_game(GameCreate(mode=data["mode"], white=data["white"], black=data["black"],
                                             human_color=data["human_color"], difficulty=data["difficulty"],
                                             start_fen=data["start_fen"], moves=data["moves"]))
        self.assertEqual(again["state"]["fen"], saved_games.get_saved(s["id"])["fen"])
        saved_games.delete_saved(s["id"])
        with self.assertRaises(HTTPException):
            saved_games.get_saved(s["id"])

    def test_name_validation(self):
        with self.assertRaises(ValueError):
            GameCreate(mode="pvp", white="<script>", black="Bob")
        with self.assertRaises(ValueError):
            GameCreate(mode="pvp", white="x" * 40, black="Bob")

    def test_sql_injection_is_inert(self):
        name = "Robert'); DROP TABLE games;--"
        with self.assertRaises(ValueError):
            GameCreate(mode="pvp", white=name, black="Bob")
        with database.db() as c:
            c.execute("INSERT OR IGNORE INTO players(name, created_at) VALUES(?,?)", (name, database.now()))
            self.assertEqual(c.execute("SELECT COUNT(*) FROM games").fetchone()[0] >= 0, True)

    def test_custom_puzzle_and_attempts(self):
        p = puzzles.create_puzzle(PuzzleIn(title="Test mate", fen="6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
                                           goal="mate", solution=["a1a8"]))
        self.assertTrue(puzzles.attempt(AttemptIn(moves=["a1a8"]), p["id"])["complete"])
        self.assertFalse(puzzles.attempt(AttemptIn(moves=["a1a7"]), p["id"])["correct"])
        self.assertFalse(puzzles.attempt(AttemptIn(moves=["a1a5"]), p["id"])["correct"])
        with self.assertRaises(HTTPException):
            puzzles.create_puzzle(PuzzleIn(title="bad", fen="6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", goal="mate", solution=["a1a7"]))

    def test_all_seeded_puzzles_are_solvable(self):
        for item in puzzles.list_puzzles()["puzzles"]:
            with database.db() as c:
                sol = json.loads(c.execute("SELECT solution FROM puzzles WHERE id=?", (item["id"],)).fetchone()[0])
            moves = []
            for k in range(0, len(sol), 2):
                moves.append(sol[k])
                r = puzzles.attempt(AttemptIn(moves=moves), item["id"])
                self.assertTrue(r["correct"], item["title"])
                if k + 1 < len(sol):
                    moves.append(sol[k + 1])
            self.assertTrue(r["complete"], item["title"])


if __name__ == "__main__":
    unittest.main()
