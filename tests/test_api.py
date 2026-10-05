import os
import tempfile
import unittest

os.environ["CHESS_DB"] = os.path.join(tempfile.mkdtemp(), "api.db")
try:
    from fastapi.testclient import TestClient
    HAVE_CLIENT = True
except Exception:          # httpx missing
    HAVE_CLIENT = False


@unittest.skipUnless(HAVE_CLIENT, "install httpx (requirements-dev.txt) to run API tests")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend import database
        database.DB_PATH = database.Path(os.environ["CHESS_DB"])
        from backend.main import app
        cls.ctx = TestClient(app)
        cls.c = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)

    def test_health_and_index(self):
        self.assertEqual(self.c.get("/api/health").json()["status"], "ok")
        self.assertIn("LOCAL CHESS ARENA", self.c.get("/").text)

    def test_computer_game_flow(self):
        r = self.c.post("/api/games", json={"mode": "pvc", "white": "Me", "black": "Computer (Easy)",
                                             "human_color": "w", "difficulty": "easy"}).json()
        gid = r["game"]["id"]
        self.assertEqual(self.c.post(f"/api/games/{gid}/moves", json={"uci": "e2e4"}).status_code, 200)
        ai = self.c.post("/api/ai/move", json={"game_id": gid}).json()
        self.assertIn(ai["move"], self.c.get(f"/api/games/{gid}").json()["state"]["legal"])
        self.assertEqual(self.c.post(f"/api/games/{gid}/moves", json={"uci": ai["move"]}).status_code, 200)

    def test_validation_errors(self):
        self.assertEqual(self.c.post("/api/games", json={"mode": "pvp", "white": "<b>", "black": "x"}).status_code, 422)
        self.assertEqual(self.c.get("/api/games/0").status_code, 422)
        self.assertEqual(self.c.get("/api/games/99999").status_code, 404)
        self.assertEqual(self.c.post("/api/fen/validate", json={"fen": "bad"}).json()["valid"], False)
        self.assertEqual(self.c.post("/api/position", json={"moves": ["e2e5"]}).status_code, 400)

    def test_saved_games_endpoints(self):
        gid = self.c.post("/api/games", json={"mode": "pvp", "white": "A", "black": "B"}).json()["game"]["id"]
        self.c.post(f"/api/games/{gid}/moves", json={"uci": "e2e4"})
        s = self.c.post("/api/saved-games", json={"name": "t", "game_id": gid}).json()
        self.assertIn(s["id"], [x["id"] for x in self.c.get("/api/saved-games").json()["saved"]])
        self.assertEqual(self.c.delete(f"/api/saved-games/{s['id']}").status_code, 200)

    def test_pgn_and_fen_endpoints(self):
        pgn = self.c.post("/api/pgn/export", json={"moves": ["e2e4", "e7e5"], "white": "A", "black": "B"}).json()["pgn"]
        parsed = self.c.post("/api/pgn/parse", json={"pgn": pgn}).json()
        self.assertEqual(parsed["moves"], ["e2e4", "e7e5"])


if __name__ == "__main__":
    unittest.main()
