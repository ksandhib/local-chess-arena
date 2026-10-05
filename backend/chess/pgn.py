"""PGN export and import."""
import re
from datetime import date

from .board import Board, START_FEN
from .moves import move_to_uci
from .notation import parse_san, san
from .moves import legal_moves

MAX_PGN = 200_000
_TAG = re.compile(r'^\s*\[(\w+)\s+"((?:[^"\\]|\\.)*)"\]\s*$')
_RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}


def _esc(v):
    return str(v).replace("\\", "\\\\").replace('"', '\\"')


def export_pgn(sans, result="*", white="Player", black="Computer", event="Local Chess",
               start_fen=START_FEN, on_date=None, extra=None):
    d = (on_date or date.today()).strftime("%Y.%m.%d")
    tags = [("Event", event), ("Site", "Local Chess Arena"), ("Date", d), ("Round", "-"),
            ("White", white), ("Black", black), ("Result", result)]
    if start_fen and start_fen.split()[:4] != START_FEN.split()[:4] or (start_fen and start_fen != START_FEN):
        tags += [("SetUp", "1"), ("FEN", start_fen)]
    for k, v in (extra or {}).items():
        tags.append((k, v))
    head = "\n".join('[%s "%s"]' % (k, _esc(v)) for k, v in tags)
    b = Board(start_fen or START_FEN)
    toks, num, black_first = [], b.fullmove, b.turn == "b"
    for i, s in enumerate(sans):
        white_move = (i % 2 == 0) != black_first
        if white_move:
            toks.append("%d. %s" % (num, s))
        else:
            toks.append(("%d... %s" % (num, s)) if i == 0 else s)
            num += 1
    toks.append(result)
    lines, cur = [], ""
    for t in toks:
        if cur and len(cur) + 1 + len(t) > 80:
            lines.append(cur)
            cur = t
        else:
            cur = (cur + " " + t) if cur else t
    lines.append(cur)
    return head + "\n\n" + "\n".join(lines) + "\n"


def parse_pgn(text):
    """Parse the first game of a PGN. Returns (headers, start_fen, ucis, result)."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("PGN is empty.")
    if len(text) > MAX_PGN:
        raise ValueError("PGN is too large.")
    headers, body = {}, []
    for line in text.replace("\r", "").split("\n"):
        m = _TAG.match(line)
        if m and not body:
            headers[m.group(1)] = m.group(2).replace('\\"', '"').replace("\\\\", "\\")
        elif line.strip().startswith("[") and not body and line.strip().endswith("]"):
            continue
        else:
            if line.strip() or body:
                body.append(line)
    movetext = "\n".join(body)
    movetext = re.sub(r"\{[^}]*\}", " ", movetext)
    movetext = re.sub(r";[^\n]*", " ", movetext)
    prev = None
    while prev != movetext:                       # strip (nested) variations
        prev = movetext
        movetext = re.sub(r"\([^()]*\)", " ", movetext)
    movetext = re.sub(r"\$\d+", " ", movetext)
    start_fen = START_FEN
    if headers.get("SetUp") == "1" or "FEN" in headers:
        start_fen = headers.get("FEN", START_FEN)
    b = Board(start_fen)          # raises FenError (a ValueError) when invalid
    start_fen = b.fen()
    result = headers.get("Result", "*")
    ucis = []
    for tok in movetext.split():
        if tok in _RESULTS:
            result = tok
            break
        tok = re.sub(r"^\d+\.+", "", tok)
        if not tok or tok in ("..", "..."):
            continue
        if len(ucis) >= 1000:
            raise ValueError("PGN has too many moves.")
        try:
            m = parse_san(b, tok)
        except ValueError as e:
            raise ValueError("Move %d: %s" % (len(ucis) + 1, e))
        ucis.append(move_to_uci(m))
        b.push(m)
    if not ucis and not headers:
        raise ValueError("No moves found in PGN.")
    return headers, start_fen, ucis, result
