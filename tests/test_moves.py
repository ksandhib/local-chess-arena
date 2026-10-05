import unittest
from backend.chess.board import Board
from backend.chess.moves import legal_moves, parse_uci, is_attacked, is_king_in_check
from backend.chess.pieces import square_index
from .helpers import play, ucis, moves_from


def perft(b, d):
    if d == 0:
        return 1
    n = 0
    for m in legal_moves(b):
        b.push(m)
        n += perft(b, d - 1)
        b.pop()
    return n


class MoveTests(unittest.TestCase):
    def test_start_has_20_moves(self):
        self.assertEqual(len(legal_moves(Board())), 20)

    def test_pawn_moves(self):
        b = Board()
        self.assertEqual(moves_from(b, "e2"), ["e3", "e4"])
        play(b, "e2e4", "a7a6")
        self.assertEqual(moves_from(b, "e4"), ["e5"])
        b2 = Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
        self.assertEqual(moves_from(b2, "e4"), ["d5", "e5"])      # capture + push

    def test_knight_moves(self):
        self.assertEqual(moves_from(Board(), "g1"), ["f3", "h3"])
        b = Board("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1")
        self.assertEqual(len(moves_from(b, "d4")), 8)

    def test_bishop_moves(self):
        b = Board("4k3/8/8/8/3B4/8/8/4K3 w - - 0 1")
        self.assertEqual(len(moves_from(b, "d4")), 13)
        self.assertEqual(moves_from(Board(), "c1"), [])

    def test_rook_moves(self):
        b = Board("4k3/8/8/8/3R4/8/8/4K3 w - - 0 1")
        self.assertEqual(len(moves_from(b, "d4")), 14)

    def test_queen_moves(self):
        b = Board("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1")
        self.assertEqual(len(moves_from(b, "d4")), 27)

    def test_king_moves(self):
        b = Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        self.assertEqual(len(moves_from(b, "e1")), 5)

    def test_pinned_piece_cannot_move(self):
        b = Board("4r1k1/8/8/8/8/8/4N3/4K3 w - - 0 1")
        self.assertEqual(moves_from(b, "e2"), [])

    def test_cannot_move_into_check(self):
        b = Board("4k3/8/8/8/8/8/3r4/4K3 w - - 0 1")
        self.assertNotIn("d1", moves_from(b, "e1"))

    def test_illegal_move_rejected(self):
        with self.assertRaises(ValueError):
            parse_uci(Board(), "e2e5")
        with self.assertRaises(ValueError):
            parse_uci(Board(), "zz")

    def test_perft_matches_reference_counts(self):
        self.assertEqual(perft(Board(), 3), 8902)
        self.assertEqual(perft(Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"), 2), 2039)
        self.assertEqual(perft(Board("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"), 3), 2812)
        self.assertEqual(perft(Board("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1"), 3), 9467)

    def test_promotion_offers_four_pieces(self):
        b = Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        self.assertEqual(moves_from(b, "a7"), ["a8b", "a8n", "a8q", "a8r"])
        with self.assertRaises(ValueError):
            parse_uci(b, "a7a8")

    def test_promotion_with_capture(self):
        b = Board("1n2k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        self.assertIn("b8q", moves_from(b, "a7"))
        play(b, "a7b8n")
        self.assertEqual(b.sq[square_index("b8")], "N")

    def test_en_passant(self):
        b = play(Board(), "e2e4", "a7a6", "e4e5", "d7d5")
        self.assertEqual(b.ep, square_index("d6"))
        self.assertIn("d6", moves_from(b, "e5"))
        play(b, "e5d6")
        self.assertEqual(b.sq[square_index("d5")], ".")      # captured pawn disappears
        self.assertEqual(b.sq[square_index("d6")], "P")
        b.pop()
        self.assertEqual(b.sq[square_index("d5")], "p")

    def test_en_passant_only_immediately(self):
        b = play(Board(), "e2e4", "a7a6", "e4e5", "d7d5", "h2h3", "h7h6")
        self.assertNotIn("d6", moves_from(b, "e5"))

    def test_kingside_and_queenside_castling(self):
        b = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        self.assertIn("g1", moves_from(b, "e1"))
        self.assertIn("c1", moves_from(b, "e1"))
        play(b, "e1g1")
        self.assertEqual((b.sq[square_index("g1")], b.sq[square_index("f1")]), ("K", "R"))
        play(b, "e8c8")
        self.assertEqual((b.sq[square_index("c8")], b.sq[square_index("d8")]), ("k", "r"))
        self.assertEqual(b.castling, "")

    def test_castling_illegal_through_or_out_of_check(self):
        through = Board("4k3/8/8/8/8/8/5r2/R3K2R w KQ - 0 1")     # f1 attacked
        self.assertNotIn("g1", moves_from(through, "e1"))
        self.assertIn("c1", moves_from(through, "e1"))
        in_check = Board("4k3/8/8/8/8/8/4r3/R3K2R w KQ - 0 1")
        self.assertEqual([m for m in moves_from(in_check, "e1") if m in ("g1", "c1")], [])
        onto = Board("4k3/8/8/8/8/8/6r1/R3K2R w KQ - 0 1")        # g1 attacked
        self.assertNotIn("g1", moves_from(onto, "e1"))

    def test_castling_blocked_or_rights_lost(self):
        blocked = Board("4k3/8/8/8/8/8/8/RN2K2R w KQ - 0 1")
        self.assertNotIn("c1", moves_from(blocked, "e1"))
        self.assertIn("g1", moves_from(blocked, "e1"))
        b = play(Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"), "e1e2", "a8a7", "e2e1", "a7a8")
        self.assertNotIn("g1", moves_from(b, "e1"))

    def test_queenside_castling_allows_attacked_b_file(self):
        b = Board("1r2k3/8/8/8/8/8/8/R3K3 w Q - 0 1")
        self.assertIn("c1", moves_from(b, "e1"))

    def test_is_square_attacked(self):
        b = Board("4r1k1/8/8/8/8/8/8/4K3 w - - 0 1")
        self.assertTrue(is_attacked(b, square_index("e1"), "b"))
        self.assertTrue(is_king_in_check(b))


if __name__ == "__main__":
    unittest.main()
