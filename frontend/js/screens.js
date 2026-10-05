// Saved games, game history and settings screens.
import { api } from './api.js';
import { settings, setSetting } from './settings.js';
import { $, esc, toast, confirmBox, go } from './ui.js';

const MODE = { pvc: 'Player vs Computer', pvp: 'Local 2 Player', practice: 'Practice position' };
const RESULT = { '1-0': 'White won', '0-1': 'Black won', '1/2-1/2': 'Draw', '*': 'Unfinished' };

export async function refreshSaved() {
  const box = $('#saved-list'); box.textContent = 'Loading...';
  let list;
  try { list = (await api.listSaved()).saved; } catch (e) { box.textContent = e.message; return; }
  if (!list.length) { box.innerHTML = '<p class="muted">No saved games yet. Use SAVE GAME during a game.</p>'; return; }
  box.innerHTML = '';
  for (const g of list) {
    const d = document.createElement('div'); d.className = 'item';
    d.innerHTML = `<div><strong>GAME #${g.id} - ${esc(g.name)}</strong><div class="meta">${MODE[g.mode] || esc(g.mode)}${g.difficulty ? ' (' + esc(g.difficulty) + ')' : ''} &middot; ${esc(g.created_at.slice(0, 10))} &middot; ${g.move_count} plies</div></div>
      <div class="btns"><button class="btn primary">LOAD</button><button class="btn danger">DELETE</button></div>`;
    d.querySelector('.primary').onclick = () => loadSaved(g.id);
    d.querySelector('.danger').onclick = async () => {
      if (!(await confirmBox(`Delete saved game #${g.id}?`, 'DELETE', 'CANCEL'))) return;
      try { await api.deleteSaved(g.id); toast('Deleted'); refreshSaved(); } catch (e) { toast(e.message); }
    };
    box.appendChild(d);
  }
}

async function loadSaved(id) {
  try {
    const s = await api.getSaved(id), d = s.data;
    const tc = d.time_control;
    let clock = null;
    if (tc) {
      const c = d.clocks || { w: tc.base * 1000, b: tc.base * 1000 };
      clock = { w: tc.base, b: tc.base, baseSec: tc.base, inc: tc.inc, times: c };
    }
    go('game', { mode: d.mode, white: d.white, black: d.black, humanColor: d.human_color, difficulty: d.difficulty,
      startFen: d.start_fen, moves: d.moves, clock, paused: !!clock });
  } catch (e) { toast(e.message, 4000); }
}

export async function refreshHistory() {
  const stats = $('#stats-box'), box = $('#history-list');
  box.textContent = 'Loading...';
  try {
    const [s, h] = await Promise.all([api.statistics(), api.listGames(100)]);
    const r = s.by_result;
    stats.innerHTML = `<div class="stat"><b>${s.total_games}</b>games finished</div>
      <div class="stat"><b>${r['1-0'] || 0}</b>White wins</div><div class="stat"><b>${r['0-1'] || 0}</b>Black wins</div>
      <div class="stat"><b>${r['1/2-1/2'] || 0}</b>draws</div><div class="stat"><b>${Math.round(s.average_plies / 2)}</b>avg. moves per game</div>`;
    let html = '';
    if (s.players.length) {
      html += '<table class="pl"><caption class="muted" style="text-align:left">Player statistics</caption><tr><th>Player</th><th>Played</th><th>Won</th><th>Lost</th><th>Drawn</th></tr>' +
        s.players.map(p => `<tr><td>${esc(p.player_name)}</td><td>${p.games_played}</td><td>${p.wins}</td><td>${p.losses}</td><td>${p.draws}</td></tr>`).join('') + '</table>';
    }
    box.innerHTML = html;
    if (!h.games.length) { box.insertAdjacentHTML('beforeend', '<p class="muted">No games played yet.</p>'); return; }
    for (const g of h.games) {
      const d = document.createElement('div'); d.className = 'item';
      const res = g.status === 'active' ? 'In progress' : g.status === 'abandoned' ? 'Abandoned' : `${RESULT[g.result] || g.result}${g.termination ? ' (' + esc(g.termination) + ')' : ''}`;
      d.innerHTML = `<div><strong>#${g.id} ${esc(g.white_player)} vs ${esc(g.black_player)}</strong><div class="meta">${MODE[g.mode] || esc(g.mode)}${g.ai_difficulty ? ' - ' + esc(g.ai_difficulty) : ''} &middot; ${esc(g.started_at.slice(0, 16))} &middot; ${g.move_count} plies &middot; ${res}</div></div>
        <div class="btns"><button class="btn rev">REVIEW</button><button class="btn danger del">DELETE</button></div>`;
      d.querySelector('.rev').onclick = async () => {
        try { const full = await api.getGame(g.id); go('analysis', { startFen: full.state.start_fen, moves: full.state.moves, white: g.white_player, black: g.black_player, ply: 0 }); }
        catch (e) { toast(e.message); }
      };
      d.querySelector('.del').onclick = async () => {
        if (!(await confirmBox(`Delete game #${g.id} from history?`, 'DELETE', 'CANCEL'))) return;
        try { await api.deleteGame(g.id); refreshHistory(); } catch (e) { toast(e.message); }
      };
      box.appendChild(d);
    }
  } catch (e) { box.textContent = e.message; }
}

export function initSettings() {
  const sync = () => {
    $('#s-theme').value = settings.theme; $('#s-name').value = settings.playerName;
    $('#s-sound').checked = settings.sound; $('#s-hints').checked = settings.showMoves;
    $('#s-autoq').checked = settings.autoQueen; $('#s-motion').checked = settings.reduceMotion;
  };
  const prev = $('#s-preview'); for (let i = 0; i < 8; i++) prev.appendChild(document.createElement('span'));
  $('#s-theme').onchange = e => setSetting('theme', e.target.value);
  $('#s-name').onchange = e => setSetting('playerName', (e.target.value.trim() || 'Player').slice(0, 32));
  $('#s-sound').onchange = e => setSetting('sound', e.target.checked);
  $('#s-hints').onchange = e => setSetting('showMoves', e.target.checked);
  $('#s-autoq').onchange = e => setSetting('autoQueen', e.target.checked);
  $('#s-motion').onchange = e => setSetting('reduceMotion', e.target.checked);
  return sync;
}
