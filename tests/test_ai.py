import random
import unittest
from backend.chess.ai import AIPlayer, evaluate, DIFFICULTY
from backend.chess.board import Board
from backend.chess.moves import legal_moves, move_to_uci
from backend.chess.rules import build_state, status
from .helpers import play


class AITests(unittest.TestCase):
    def test_evaluation_symmetry(self):
        self.assertEqual(evaluate(Board()), 0)

    def test_evaluation_prefers_extra_material(self):
        self.assertGreater(evaluate(Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")), 500)

    def test_every_difficulty_returns_legal_move(self):
        for level in DIFFICULTY:
            b = Board()
            m = AIPlayer(level, random.Random(1)).get_best_move(b, time_limit=2)
            self.assertIn(m, legal_moves(b))

    def test_finds_mate_in_one(self):
        b = Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
        self.assertEqual(move_to_uci(AIPlayer("medium").get_best_move(b)), "h5f7")

    def test_captures_hanging_queen(self):
        b = Board("4k3/8/8/3q4/8/8/8/3QK3 w - - 0 1")
        self.assertEqual(move_to_uci(AIPlayer("medium").get_best_move(b)), "d1d5")

    def test_avoids_stalemate_when_winning(self):
        b = Board("7k/8/5K2/6Q1/8/8/8/8 w - - 0 1")
        m = AIPlayer("hard").get_best_move(b, time_limit=3)
        b.push(m)
        self.assertFalse(status(b)["stalemate"])

    def test_easy_prefers_captures(self):
        b = Board("4k3/8/8/3q4/8/8/8/3QK3 w - - 0 1")
        rng = random.Random(0)
        hits = sum(move_to_uci(AIPlayer("easy", rng).get_best_move(b)) == "d1d5" for _ in range(200))
        self.assertGreater(hits, 200 / len(legal_moves(b)))

    def test_no_move_when_game_over(self):
        b = play(Board(), "f2f3", "e7e5", "g2g4", "d8h4")
        self.assertIsNone(AIPlayer("medium").get_best_move(b))

    def test_plays_full_legal_game_segment(self):
        b, ai, played = Board(), AIPlayer("medium"), []
        for _ in range(40):
            m = ai.get_best_move(b, time_limit=1)
            if m is None:
                break
            played.append(move_to_uci(m))
            b.push(m)
        build_state(None, played)            # raises if any move were illegal

    def test_draw_response_is_deterministic(self):
        b = Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        self.assertEqual(AIPlayer("medium").respond_to_draw(b, "b"), AIPlayer("medium").respond_to_draw(b, "b"))
        worse = Board("4k3/8/8/8/8/8/Q7/4K3 b - - 0 1")
        self.assertTrue(AIPlayer("medium").respond_to_draw(worse, "b")[0])

    def test_unknown_difficulty(self):
        with self.assertRaises(ValueError):
            AIPlayer("godlike")


if __name__ == "__main__":
    unittest.main()
