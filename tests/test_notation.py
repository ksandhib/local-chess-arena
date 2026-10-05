import unittest
from backend.chess.board import Board
from backend.chess.moves import parse_uci
from backend.chess.notation import san, parse_san
from backend.chess.pgn import export_pgn, parse_pgn
from backend.chess.rules import build_state
from .helpers import play


class NotationTests(unittest.TestCase):
    def s(self, b, u):
        return san(b, parse_uci(b, u))

    def test_basic_san(self):
        b = Board()
        self.assertEqual(self.s(b, "e2e4"), "e4")
        self.assertEqual(self.s(b, "g1f3"), "Nf3")

    def test_capture_check_mate_castle_promotion(self):
        self.assertEqual(self.s(Board("3k4/8/8/3q4/8/8/8/3QK3 w - - 0 1"), "d1d5"), "Qxd5+")
        self.assertEqual(self.s(Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"), "e1g1"), "O-O")
        self.assertEqual(self.s(Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"), "e1c1"), "O-O-O")
        self.assertEqual(self.s(Board("1n2k3/P7/8/8/8/8/8/4K3 w - - 0 1"), "a7b8q"), "axb8=Q+")
        self.assertEqual(self.s(Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1"), "a7a8q"), "a8=Q+")
        b = Board("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1")
        self.assertEqual(self.s(b, "a1a8"), "Ra8#")
        self.assertEqual(self.s(Board("7k/8/6K1/8/8/8/8/5Q2 w - - 0 1"), "f1f7"), "Qf7")
        self.assertEqual(self.s(Board("7k/8/6K1/8/8/8/8/5Q2 w - - 0 1"), "f1f8"), "Qf8#")

    def test_disambiguation(self):
        b = Board("4k3/8/8/8/8/8/4K3/R6R w - - 0 1")
        self.assertEqual(self.s(b, "a1d1"), "Rad1")
        b2 = Board("4k3/8/8/8/R7/8/8/R3K3 w - - 0 1")
        self.assertEqual(self.s(b2, "a1a3"), "R1a3")

    def test_parse_san_round_trip(self):
        b = Board()
        m = parse_san(b, "Nf3")
        self.assertEqual(m, parse_uci(b, "g1f3"))
        with self.assertRaises(ValueError):
            parse_san(b, "Nf6")

    def test_pgn_export(self):
        st = build_state(None, ["e2e4", "e7e5", "g1f3", "b8c6"])
        pgn = export_pgn(st["san"], "*", "Player", "Computer")
        self.assertIn('[White "Player"]', pgn)
        self.assertIn('[Black "Computer"]', pgn)
        self.assertIn("1. e4 e5 2. Nf3 Nc6 *", pgn)

    def test_pgn_round_trip_with_comments(self):
        text = '[Event "t"]\n[White "A"]\n[Black "B"]\n\n1. e4 {best} e5 (1... c5) 2. Nf3 $1 Nc6 3. Bb5 a6 1/2-1/2\n'
        headers, start, ucis, result = parse_pgn(text)
        self.assertEqual(headers["White"], "A")
        self.assertEqual(ucis, ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"])
        self.assertEqual(result, "1/2-1/2")

    def test_pgn_with_fen_header(self):
        fen = "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"
        st = build_state(fen, ["e2e4"])
        pgn = export_pgn(st["san"], "*", start_fen=fen)
        self.assertIn('[FEN "%s"]' % fen, pgn)
        _, start, ucis, _ = parse_pgn(pgn)
        self.assertEqual((start, ucis), (fen, ["e2e4"]))

    def test_pgn_errors(self):
        with self.assertRaises(ValueError):
            parse_pgn("1. e4 e5 2. Qh6")
        with self.assertRaises(ValueError):
            parse_pgn("")


if __name__ == "__main__":
    unittest.main()
