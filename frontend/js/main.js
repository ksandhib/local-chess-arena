// Application entry: screen routing, menu keyboard navigation and game setup.
import { api } from './api.js';
import { applySettings, settings } from './settings.js';
import { GameScreen } from './game.js';
import { Puzzles } from './puzzles.js';
import { Analysis } from './analysis.js';
import { Practice } from './practice.js';
import { parseClock } from './clock.js';
import { refreshSaved, refreshHistory, initSettings } from './screens.js';
import { $, $$, toast, isModalOpen, go } from './ui.js';

applySettings();
const NAMES = ['menu', 'setup', 'game', 'puzzle', 'practice', 'analysis', 'saved', 'history', 'settings'];
let current = 'menu';
let setupMode = 'pvc';
const game = new GameScreen();
const puzzles = new Puzzles();
const analysis = new Analysis();
const practice = new Practice();
const syncSettings = initSettings();

function reveal(name) {
  for (const n of NAMES) $('#screen-' + n).hidden = n !== name;
  current = name; document.body.dataset.screen = name; window.scrollTo(0, 0);
}

async function show(name, data) {
  if (name !== 'game' && name !== 'analysis') {
    if (current === 'game' && !(await game.confirmLeave())) return;
    await game.abandon();
  }
  switch (name) {
    case 'menu': reveal('menu'); $('#menu-list .menu-btn').focus(); break;
    case 'setup-pvc': case 'setup-pvp': openSetup(name.endsWith('pvc') ? 'pvc' : 'pvp'); break;
    case 'game': reveal('game'); await game.start(data); break;
    case 'puzzle': reveal('puzzle'); await puzzles.open(); break;
    case 'practice': reveal('practice'); practice.open(); break;
    case 'analysis': reveal('analysis'); if (!(await analysis.open(data || {}))) reveal('menu'); break;
    case 'saved': reveal('saved'); refreshSaved(); break;
    case 'history': reveal('history'); refreshHistory(); break;
    case 'settings': reveal('settings'); syncSettings(); break;
  }
}

document.addEventListener('navigate', e => show(e.detail.screen, e.detail.data));
document.addEventListener('click', e => {
  const b = e.target.closest('[data-go]'); if (b) show(b.dataset.go);
});

// ---- keyboard: menu navigation and Esc ----
document.addEventListener('keydown', e => {
  if (isModalOpen()) return;
  if (current === 'menu' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    const items = $$('#menu-list .menu-btn'); let i = items.indexOf(document.activeElement);
    i = e.key === 'ArrowDown' ? (i + 1) % items.length : (i - 1 + items.length) % items.length;
    items[i < 0 ? 0 : i].focus(); e.preventDefault();
  } else if (e.key === 'Escape' && current !== 'menu') {
    if (e.target.matches && e.target.matches('input, select, textarea')) e.target.blur();
    show('menu');
  }
});

// ---- setup screen ----
function openSetup(mode) {
  setupMode = mode;
  reveal('setup');
  $$('.only-pvc').forEach(x => x.hidden = mode !== 'pvc');
  $$('.only-pvp').forEach(x => x.hidden = mode !== 'pvp');
  $('#setup-title').textContent = mode === 'pvc' ? 'Play vs computer' : 'Local 2 player';
  $('#su-name').value = settings.playerName; $('#su-error').textContent = '';
  $('#su-name').focus();
}
$('#su-clock').onchange = e => { $('#su-custom').hidden = e.target.value !== 'custom'; };
const validName = v => /^[^\x00-\x1f\x7f<>&"'`]{1,32}$/.test(v.trim());

$('#su-start').onclick = () => {
  const err = m => { $('#su-error').textContent = m; return null; };
  let clock = null;
  const c = $('#su-clock').value;
  if (c === 'custom') {
    const w = parseClock($('#su-wt').value), b = parseClock($('#su-bt').value);
    if (!w || !b) return err('Enter times as HH:MM:SS between 00:00:01 and 24:00:00.');
    clock = { w, b, baseSec: w, inc: +$('#su-inc').value };
  } else if (c !== 'none') {
    const [m, inc] = c.split('+').map(Number); clock = { w: m * 60, b: m * 60, baseSec: m * 60, inc };
  }
  if (setupMode === 'pvc') {
    const name = $('#su-name').value.trim() || 'Player';
    if (!validName(name)) return err('Names must be 1-32 characters and cannot contain < > & or quotes.');
    const pick = document.querySelector('input[name=color]:checked').value;
    const human = pick === 'random' ? (Math.random() < .5 ? 'w' : 'b') : pick;
    const level = document.querySelector('input[name=level]:checked').value;
    const comp = 'Computer (' + level[0].toUpperCase() + level.slice(1) + ')';
    show('game', { mode: 'pvc', humanColor: human, randomColor: pick === 'random', difficulty: level,
      white: human === 'w' ? name : comp, black: human === 'b' ? name : comp, clock, moves: [] });
  } else {
    const w = $('#su-wname').value.trim() || 'White', b = $('#su-bname').value.trim() || 'Black';
    if (!validName(w) || !validName(b)) return err('Names must be 1-32 characters and cannot contain < > & or quotes.');
    if (w === b) return err('Please use two different names.');
    show('game', { mode: 'pvp', white: w, black: b, clock, moves: [] });
  }
};

// ---- boot ----
api.health().then(() => show('menu')).catch(() => { reveal('menu'); toast('Server not reachable. Run start.bat first.', 8000); });
