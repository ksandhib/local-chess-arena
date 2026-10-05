import unittest
from backend.chess.board import Board, START_FEN
from backend.chess.fen import FenError, validate_fen


class FenTests(unittest.TestCase):
    def test_round_trip(self):
        for fen in (START_FEN, "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
                    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2"):
            self.assertEqual(Board(fen).fen(), fen)

    def test_four_field_fen_accepted(self):
        self.assertEqual(Board("8/8/4k3/8/8/3K4/8/8 w - -").fen(), "8/8/4k3/8/8/3K4/8/8 w - - 0 1")

    def test_invalid_fens_have_clear_errors(self):
        bad = {
            "": "6 fields",
            "8/8/8/8/8/8/8 w - - 0 1": "8 ranks",
            "9/8/8/8/8/8/8/8 w - - 0 1": "invalid",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBN w KQkq - 0 1": "exactly 8",
            "8/8/8/8/8/8/8/8 w - - 0 1": "one king",
            "4k3/8/8/8/8/8/8/4K2X w - - 0 1": "invalid character",
            "P3k3/8/8/8/8/8/8/4K3 w - - 0 1": "Pawns cannot",
            "4k3/8/8/8/8/8/8/4K3 x - - 0 1": "Side to move",
            "4k3/8/8/8/8/8/8/4K3 w K - 0 1": "does not match",
            "4k3/8/8/8/8/8/8/4K3 w - e3 0 1": "wrong rank",
            "4k3/8/8/8/8/8/8/4K3 w - - a 1": "integers",
            "4k3/8/8/8/8/8/8/4K3 w - - 0 0": "Fullmove",
            "4k3/8/8/8/8/8/4R3/4K3 w - - 0 1": "check, which is impossible",
        }
        for fen, fragment in bad.items():
            norm, err = validate_fen(fen)
            self.assertIsNone(norm, fen)
            self.assertIn(fragment.lower(), (err or "").lower(), fen)

    def test_error_type(self):
        with self.assertRaises(FenError):
            Board("nonsense")


if __name__ == "__main__":
    unittest.main()
