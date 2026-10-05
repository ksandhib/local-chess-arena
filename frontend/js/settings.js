// User preferences stored in localStorage (theme, sound, motion, promotion, etc.).
const KEY = 'localChessArena.settings.v1';
const DEFAULTS = { theme: 'classic', sound: true, reduceMotion: false, autoQueen: false, showMoves: true, playerName: 'Player' };
export const THEMES = ['classic', 'wood', 'green', 'blue', 'dark'];

function load() {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { return { ...DEFAULTS }; }
}
export const settings = load();

export function applySettings() {
  if (!THEMES.includes(settings.theme)) settings.theme = 'classic';
  document.body.dataset.theme = settings.theme;
  document.body.classList.toggle('reduce-motion', !!settings.reduceMotion);
}

export function setSetting(key, value) {
  settings[key] = value;
  try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch { /* storage unavailable */ }
  applySettings();
}
