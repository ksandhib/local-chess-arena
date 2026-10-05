"""Request models with strict validation."""
import re
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

_NAME_RE = re.compile(r"^[^\x00-\x1f\x7f<>&\"'`]{1,32}$")
UCI_PATTERN = r"^[a-h][1-8][a-h][1-8][qrbn]?$"


def clean_name(v):
    v = " ".join(str(v).split())
    if not _NAME_RE.match(v):
        raise ValueError("Names must be 1-32 characters and cannot contain < > & quotes.")
    return v


class TimeControl(BaseModel):
    base: int = Field(ge=0, le=86400)      # seconds per side
    inc: int = Field(default=0, ge=0, le=300)


class GameCreate(BaseModel):
    mode: Literal["pvc", "pvp", "practice"]
    white: str = "White"
    black: str = "Black"
    human_color: Optional[Literal["w", "b"]] = None
    difficulty: Optional[Literal["easy", "medium", "hard", "expert"]] = None
    start_fen: Optional[str] = Field(default=None, max_length=100)
    moves: List[str] = Field(default_factory=list, max_length=1000)
    time_control: Optional[TimeControl] = None

    @field_validator("white", "black")
    @classmethod
    def _names(cls, v):
        return clean_name(v)

    @field_validator("moves")
    @classmethod
    def _moves(cls, v):
        for m in v:
            if not re.match(UCI_PATTERN, m):
                raise ValueError("Bad move format: %r" % m)
        return v


class MoveIn(BaseModel):
    uci: str = Field(pattern=UCI_PATTERN)


class UndoIn(BaseModel):
    count: int = Field(default=1, ge=1, le=1000)


class FinishIn(BaseModel):
    termination: Literal["resignation", "time", "agreement", "abandoned"]
    loser: Optional[Literal["w", "b"]] = None


class PositionIn(BaseModel):
    start_fen: Optional[str] = Field(default=None, max_length=100)
    moves: List[str] = Field(default_factory=list, max_length=1000)

    @field_validator("moves")
    @classmethod
    def _moves(cls, v):
        for m in v:
            if not re.match(UCI_PATTERN, m):
                raise ValueError("Bad move format: %r" % m)
        return v


class FenIn(BaseModel):
    fen: str = Field(max_length=200)


class PgnIn(BaseModel):
    pgn: str = Field(max_length=200000)


class PgnExportIn(PositionIn):
    white: str = "Player"
    black: str = "Computer"
    result: Literal["1-0", "0-1", "1/2-1/2", "*"] = "*"

    @field_validator("white", "black")
    @classmethod
    def _names(cls, v):
        return clean_name(v)


class SaveIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    game_id: int = Field(ge=1)
    clocks: Optional[Dict[str, int]] = None

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = " ".join(v.split())
        if not v or re.search(r"[\x00-\x1f<>]", v):
            raise ValueError("Invalid save name.")
        return v

    @field_validator("clocks")
    @classmethod
    def _clocks(cls, v):
        if v is None:
            return v
        for k, val in v.items():
            if k not in ("w", "b") or not (0 <= val <= 86400 * 1000):
                raise ValueError("Invalid clock values.")
        return v


class PuzzleIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    fen: str = Field(max_length=100)
    goal: Literal["mate", "tactic"] = "tactic"
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium"
    solution: List[str] = Field(min_length=1, max_length=21)

    @field_validator("solution")
    @classmethod
    def _sol(cls, v):
        for m in v:
            if not re.match(UCI_PATTERN, m):
                raise ValueError("Bad move format: %r" % m)
        return v


class AttemptIn(BaseModel):
    moves: List[str] = Field(min_length=1, max_length=21)

    @field_validator("moves")
    @classmethod
    def _m(cls, v):
        for m in v:
            if not re.match(UCI_PATTERN, m):
                raise ValueError("Bad move format: %r" % m)
        return v


class HintIn(BaseModel):
    moves: List[str] = Field(default_factory=list, max_length=21)
    level: int = Field(default=1, ge=1, le=2)


class AiMoveIn(BaseModel):
    game_id: Optional[int] = Field(default=None, ge=1)
    fen: Optional[str] = Field(default=None, max_length=100)
    difficulty: Optional[Literal["easy", "medium", "hard", "expert"]] = None
