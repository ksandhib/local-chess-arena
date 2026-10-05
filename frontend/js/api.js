// Thin wrapper around the local FastAPI backend.
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function req(method, url, body) {
  let res;
  try {
    res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (e) {
    throw new ApiError('Cannot reach the local server. Is start.bat still running?', 0);
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    let msg = res.statusText;
    if (data && data.detail) {
      msg = typeof data.detail === 'string' ? data.detail : data.detail.map(d => d.msg).join('; ');
    }
    throw new ApiError(msg, res.status);
  }
  return data;
}

export const api = {
  health: () => req('GET', '/api/health'),
  listGames: (limit = 50) => req('GET', `/api/games?limit=${limit}`),
  createGame: b => req('POST', '/api/games', b),
  getGame: id => req('GET', `/api/games/${id}`),
  postMove: (id, uci) => req('POST', `/api/games/${id}/moves`, { uci }),
  undo: (id, count) => req('POST', `/api/games/${id}/undo`, { count }),
  finish: (id, termination, loser) => req('POST', `/api/games/${id}/finish`, { termination, loser }),
  deleteGame: id => req('DELETE', `/api/games/${id}`),
  position: (start_fen, moves) => req('POST', '/api/position', { start_fen, moves }),
  validateFen: fen => req('POST', '/api/fen/validate', { fen }),
  parsePgn: pgn => req('POST', '/api/pgn/parse', { pgn }),
  exportPgn: b => req('POST', '/api/pgn/export', b),
  listSaved: () => req('GET', '/api/saved-games'),
  getSaved: id => req('GET', `/api/saved-games/${id}`),
  saveGame: b => req('POST', '/api/saved-games', b),
  deleteSaved: id => req('DELETE', `/api/saved-games/${id}`),
  statistics: () => req('GET', '/api/statistics'),
  puzzles: () => req('GET', '/api/puzzles'),
  puzzleAttempt: (id, moves) => req('POST', `/api/puzzles/${id}/attempt`, { moves }),
  puzzleHint: (id, moves, level) => req('POST', `/api/puzzles/${id}/hint`, { moves, level }),
  aiMove: (game_id, difficulty) => req('POST', '/api/ai/move', { game_id, difficulty }),
  aiDraw: game_id => req('POST', '/api/ai/draw-response', { game_id }),
};
