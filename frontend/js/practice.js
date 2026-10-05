// Practice board: set up any position, then play it.
import { api } from './api.js';
import { BoardView, fenToPieces, pieceHtml, sqName } from './board.js';
import { $, $$, toast, go } from './ui.js';

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const TOOLS = [['move', 'MOVE'], ['erase', 'ERASE'], ...'KQRBNPkqrbnp'.split('').map(p => [p, p])];

export class Practice {
  constructor() {
    this.view = new BoardView($('#e-board'), { label: 'Practice board' });
    this.tool = 'move'; this.from = null; this.fen = null;
    const pal = $('#e-palette');
    for (const [id, label] of TOOLS) {
      const b = document.createElement('button'); b.type = 'button'; b.dataset.tool = id;
      b.setAttribute('aria-pressed', id === 'move'); b.setAttribute('aria-label', id.length === 1 ? (id === id.toUpperCase() ? 'White ' : 'Black ') + { k: 'king', q: 'queen', r: 'rook', b: 'bishop', n: 'knight', p: 'pawn' }[id.toLowerCase()] : label);
      b.innerHTML = id.length === 1 ? pieceHtml(id) : label;
      b.onclick = () => this.setTool(id);
      pal.appendChild(b);
    }
    this.view.el.addEventListener('click', e => { const s = e.target.closest('.sq'); if (s) this.click(+s.dataset.i); });
    this.view.onActivate = i => this.click(i);
    $('#e-clear').onclick = () => { this.edit(Array(64).fill('.')); this.msg('Board cleared. Add both kings before setting the position.', ''); };
    $('#e-reset').onclick = () => this.loadFen(START);
    $('#e-set').onclick = () => this.setPosition();
    $('#e-play').onclick = () => this.play();
    $('#e-load').onclick = () => this.loadFen($('#e-fen').value.trim());
    $('#e-flip').onclick = () => this.view.flip();
    $('#e-turn').onchange = () => this.syncFen();
    for (const c of 'KQkq') $('#e-c' + c).onchange = () => this.syncFen();
  }

  open() { this.loadFen(START); this.view.setOrientation('w'); }
  setTool(id) { this.tool = id; this.from = null; this.view.setSelection(null, []); $$('#e-palette button').forEach(b => b.setAttribute('aria-pressed', b.dataset.tool === id)); }
  msg(t, cls) { const m = $('#e-msg'); m.textContent = t; m.className = 'status ' + cls; }

  edit(arr) { this.view.setPieces(arr); this.syncFen(); }
  pieces() { return this.view.pieces.slice(); }

  click(i) {
    const arr = this.pieces();
    if (this.tool === 'erase') arr[i] = '.';
    else if (this.tool === 'move') {
      if (this.from == null) { if (arr[i] !== '.') { this.from = i; this.view.setSelection(i, []); } return; }
      if (this.from !== i) { arr[i] = arr[this.from]; arr[this.from] = '.'; }
      this.from = null; this.view.setSelection(null, []);
    } else {
      if (this.tool.toUpperCase() === 'K') arr.forEach((p, k) => { if (p === this.tool) arr[k] = '.'; });
      arr[i] = this.tool;
    }
    this.edit(arr);
  }

  feasibleCastling(arr) {
    return { K: arr[60] === 'K' && arr[63] === 'R', Q: arr[60] === 'K' && arr[56] === 'R',
             k: arr[4] === 'k' && arr[7] === 'r', q: arr[4] === 'k' && arr[0] === 'r' };
  }
  buildFen() {
    const arr = this.pieces(), feas = this.feasibleCastling(arr);
    let rows = [];
    for (let r = 0; r < 8; r++) {
      let s = '', n = 0;
      for (let c = 0; c < 8; c++) { const p = arr[r * 8 + c]; if (p === '.') n++; else { if (n) { s += n; n = 0; } s += p; } }
      rows.push(s + (n || ''));
    }
    let cast = '';
    for (const c of 'KQkq') { const box = $('#e-c' + c); box.disabled = !feas[c]; if (!feas[c]) box.checked = false; if (box.checked) cast += c; }
    return `${rows.join('/')} ${$('#e-turn').value} ${cast || '-'} - 0 1`;
  }
  syncFen() { $('#e-fen').value = this.buildFen(); this.fen = null; }

  async loadFen(fen) {
    try {
      const r = await api.validateFen(fen);
      if (!r.valid) { this.msg('Invalid FEN: ' + r.error, 'bad'); return false; }
      const [, turn, cast] = r.fen.split(' ');
      this.view.setPieces(fenToPieces(r.fen));
      $('#e-turn').value = turn;
      for (const c of 'KQkq') { $('#e-c' + c).checked = cast.includes(c); }
      this.syncFen(); this.msg('Position loaded.', 'good'); return true;
    } catch (e) { this.msg(e.message, 'bad'); return false; }
  }

  async setPosition() {
    try {
      const r = await api.validateFen(this.buildFen());
      if (!r.valid) { this.msg('Cannot set position: ' + r.error, 'bad'); return null; }
      this.fen = r.fen; $('#e-fen').value = r.fen; this.msg('Position is valid and set.', 'good'); return r.fen;
    } catch (e) { this.msg(e.message, 'bad'); return null; }
  }

  async play() {
    const fen = await this.setPosition(); if (!fen) return;
    go('game', { mode: 'practice', white: 'White', black: 'Black', startFen: fen, moves: [], clock: null });
  }
}
