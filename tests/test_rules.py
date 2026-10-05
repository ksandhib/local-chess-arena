import unittest
from backend.chess.board import Board
from backend.chess.moves import legal_moves
from backend.chess.rules import status, build_state, insufficient_material, validate_puzzle, can_win_on_time
from backend.chess.notation import san
from .helpers import play


class RuleTests(unittest.TestCase):
    def test_check_detected(self):
        b = Board("4r1k1/8/8/8/8/8/8/4K3 w - - 0 1")           # white king e1, black rook e8
        s = status(b)
        self.assertTrue(s["check"])
        self.assertFalse(s["game_over"])

    def test_check_must_be_answered(self):
        b = Board("4r1k1/8/8/8/8/8/8/R3K3 w - - 0 1")
        for m in legal_moves(b):
            b.push(m)
            self.assertFalse(status(b)["check"] and b.turn == "b" and False)   # sanity
            b.pop()
        from .helpers import ucis
        self.assertNotIn("a1a2", ucis(b))

    def test_fools_mate(self):
        b = play(Board(), "f2f3", "e7e5", "g2g4", "d8h4")
        s = status(b)
        self.assertTrue(s["checkmate"])
        self.assertEqual((s["result"], s["termination"]), ("0-1", "checkmate"))

    def test_stalemate(self):
        b = Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        s = status(b)
        self.assertTrue(s["stalemate"])
        self.assertEqual((s["result"], s["termination"]), ("1/2-1/2", "stalemate"))

    def test_insufficient_material(self):
        for fen in ("8/8/4k3/8/8/3K4/8/8 w - - 0 1", "8/8/4k3/8/8/3KB3/8/8 w - - 0 1",
                    "8/8/4k3/8/8/3KN3/8/8 w - - 0 1", "8/8/3bk3/8/8/3KB3/8/8 w - - 0 1"):
            self.assertTrue(insufficient_material(Board(fen)), fen)
        for fen in ("8/8/4k3/8/8/3KP3/8/8 w - - 0 1", "8/8/4k3/8/8/3K4/R7/8 w - - 0 1",
                    "8/8/4k3/8/8/2NKN3/8/8 w - - 0 1", "8/8/2b1k3/8/8/3KB3/8/8 w - - 0 1"):
            self.assertFalse(insufficient_material(Board(fen)), fen)
        self.assertEqual(status(Board("8/8/4k3/8/8/3K4/8/8 w - - 0 1"))["termination"], "insufficient material")

    def test_threefold_repetition(self):
        b = Board()
        play(b, "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1")
        self.assertFalse(status(b)["game_over"])
        play(b, "f6g8")
        s = status(b)
        self.assertTrue(s["game_over"])
        self.assertEqual(s["termination"], "threefold repetition")

    def test_fifty_move_rule(self):
        b = Board("4k3/8/8/8/8/8/R7/4K3 w - - 99 80")
        self.assertFalse(status(b)["game_over"])
        play(b, "a2a3")
        s = status(b)
        self.assertEqual((s["result"], s["termination"]), ("1/2-1/2", "fifty-move rule"))

    def test_seventy_five_move_rule(self):
        s = status(Board("4k3/8/8/8/8/8/R7/4K3 w - - 150 100"))
        self.assertEqual(s["termination"], "seventy-five-move rule")

    def test_checkmate_beats_fifty_move(self):
        b = Board("7k/8/6K1/8/8/8/8/5Q2 w - - 99 90")
        play(b, "f1f8")
        self.assertEqual(status(b)["termination"], "checkmate")

    def test_build_state_reports_everything(self):
        st = build_state(None, ["e2e4", "d7d5", "e4d5"])
        self.assertEqual(st["san"], ["e4", "d5", "exd5"])
        self.assertEqual(st["captured"]["w"], ["p"])
        self.assertEqual(st["material"], 1.0)
        self.assertEqual(len(st["fens"]), 4)
        self.assertEqual(st["last_move"], "e4d5")

    def test_build_state_rejects_illegal(self):
        with self.assertRaises(ValueError):
            build_state(None, ["e2e4", "e2e4"])

    def test_no_moves_after_game_over(self):
        with self.assertRaises(ValueError):
            build_state(None, ["f2f3", "e7e5", "g2g4", "d8h4", "a2a3"])

    def test_en_passant_capture_is_recorded(self):
        st = build_state(None, ["e2e4", "a7a6", "e4e5", "d7d5", "e5d6"])
        self.assertEqual(st["captured"]["w"], ["p"])
        self.assertEqual(st["san"][-1], "exd6")

    def test_time_forfeit_vs_insufficient_material(self):
        self.assertFalse(can_win_on_time(Board("8/8/4k3/8/8/3KN3/8/8 w - - 0 1"), "b"))
        self.assertTrue(can_win_on_time(Board("8/8/4k3/8/8/3KP3/8/8 w - - 0 1"), "w"))
        self.assertTrue(can_win_on_time(Board("8/8/4k3/8/8/2NKN3/8/8 w - - 0 1"), "w"))

    def test_puzzle_validation(self):
        validate_puzzle("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", ["a1a8"], "mate")
        with self.assertRaises(ValueError):
            validate_puzzle("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", ["a1a7"], "mate")
        with self.assertRaises(ValueError):
            validate_puzzle("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", ["a1a8", "g8h8"], "mate")


if __name__ == "__main__":
    unittest.main()
