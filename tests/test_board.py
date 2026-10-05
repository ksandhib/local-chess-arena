import unittest
from backend.chess.board import Board, START_FEN
from backend.chess.pieces import square_index, square_name
from .helpers import play


class BoardTests(unittest.TestCase):
    def test_initial_board_has_32_pieces(self):
        b = Board()
        self.assertEqual(sum(1 for p in b.sq if p != "."), 32)
        self.assertEqual(b.fen(), START_FEN)
        self.assertEqual(b.sq[square_index("e1")], "K")
        self.assertEqual(b.sq[square_index("d8")], "q")

    def test_square_names(self):
        self.assertEqual(square_index("a8"), 0)
        self.assertEqual(square_index("h1"), 63)
        self.assertEqual(square_name(36), "e4")

    def test_push_pop_restores_everything(self):
        b = Board()
        before = b.fen(), b.key()
        play(b, "e2e4", "d7d5", "e4d5", "g8f6")
        for _ in range(4):
            b.pop()
        self.assertEqual((b.fen(), b.key()), before)

    def test_castling_rights_removed_after_rook_move(self):
        b = play(Board(), "a2a3", "a7a6", "a1a2")
        self.assertNotIn("Q", b.castling)
        self.assertIn("K", b.castling)

    def test_castling_rights_removed_when_rook_captured(self):
        b = Board("r3k2r/8/8/8/8/8/6B1/R3K2R w KQkq - 0 1")
        play(b, "g2a8")
        self.assertNotIn("q", b.castling)


if __name__ == "__main__":
    unittest.main()
