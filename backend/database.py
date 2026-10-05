"""SQLite access layer (parameterised queries only)."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CHESS_DB", BASE_DIR / "data" / "chess.db"))
PUZZLE_FILE = BASE_DIR / "data" / "puzzles.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS players(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS games(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    white_player TEXT NOT NULL,
    black_player TEXT NOT NULL,
    mode TEXT NOT NULL,
    ai_difficulty TEXT,
    human_color TEXT,
    start_fen TEXT NOT NULL,
    time_control TEXT,
    result TEXT NOT NULL DEFAULT '*',
    termination TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL,
    ended_at TEXT);
CREATE TABLE IF NOT EXISTS moves(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply INTEGER NOT NULL,
    move_number INTEGER NOT NULL,
    side TEXT NOT NULL,
    uci TEXT NOT NULL,
    notation TEXT NOT NULL,
    fen TEXT NOT NULL,
    UNIQUE(game_id, ply));
CREATE TABLE IF NOT EXISTS saved_games(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    fen TEXT NOT NULL,
    pgn TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS puzzles(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    fen TEXT NOT NULL,
    goal TEXT NOT NULL DEFAULT 'tactic',
    solution TEXT NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'Medium',
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS statistics(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL UNIQUE,
    games_played INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_moves_game ON moves(game_id, ply);
"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(path=None):
    p = Path(path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db(path=None):
    """Open a connection; commit on success, roll back on error."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path=None):
    with db(path) as conn:
        conn.executescript(SCHEMA)
    seed_puzzles(path)


def seed_puzzles(path=None):
    """Import data/puzzles.json (skips slugs already stored and invalid entries)."""
    if not PUZZLE_FILE.exists():
        return
    from .chess.rules import validate_puzzle
    try:
        items = json.loads(PUZZLE_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        print("Could not read puzzles.json:", e)
        return
    with db(path) as conn:
        for p in items:
            slug = str(p.get("slug", "")).strip()
            if not slug:
                continue
            if conn.execute("SELECT 1 FROM puzzles WHERE slug=?", (slug,)).fetchone():
                continue
            try:
                validate_puzzle(p["fen"], p["solution"], p.get("goal", "tactic"))
            except (ValueError, KeyError) as e:
                print("Skipping invalid puzzle %r: %s" % (slug, e))
                continue
            conn.execute(
                "INSERT INTO puzzles(slug,title,description,fen,goal,solution,difficulty,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (slug, str(p.get("title", slug))[:80], str(p.get("description", ""))[:300], p["fen"],
                 p.get("goal", "tactic"), json.dumps(p["solution"]), str(p.get("difficulty", "Medium"))[:20], now()))
