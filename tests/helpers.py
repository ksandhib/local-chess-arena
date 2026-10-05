from backend.chess.board import Board
from backend.chess.moves import legal_moves, move_to_uci, parse_uci
from backend.chess.pieces import square_index


def play(board, *ucis):
    for u in ucis:
        board.push(parse_uci(board, u))
    return board


def ucis(board):
    return sorted(move_to_uci(m) for m in legal_moves(board))


def moves_from(board, sq):
    i = square_index(sq)
    return sorted(move_to_uci(m)[2:4] + move_to_uci(m)[4:] for m in legal_moves(board) if m[0] == i)
