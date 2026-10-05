// Puzzle mode. Solutions stay on the server; the client sends attempts for checking.
import { api } from './api.js';
import { BoardView, fenToPieces, sqIndex, sqName, isWhitePiece } from './board.js';
import { Input } from './input.js';
import { settings } from './settings.js';
import { play, soundForSan } from './sound.js';
import { $, toast, choosePromotion } from './ui.js';

const KEY = 'localChessArena.solved';
const loadSolved = () => { try { return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch { return new Set(); } };
const saveSolved = s => { try { localStorage.setItem(KEY, JSON.stringify([...s])); } catch { /* ignore */ } };

export class Puzzles {
  constructor() {
    this.view = new BoardView($('#p-board'), { label: 'Puzzle board' });
    this.list = []; this.idx = 0; this.moves = []; this.state = null; this.locked = false; this.done = false; this.hintLevel = 0;
    this.solved = loadSolved();
    this.input = new Input(this.view, {
      enabled: () => !!this.state && !this.locked && !this.done,
      canSelect: i => { const p = this.view.pieces[i]; return p !== '.' && isWhitePiece(p) === (this.state.turn === 'w') && this.state.legal.some(m => m.startsWith(sqName(i))); },
      targets: i => this.targets(i),
      showHints: () => settings.showMoves,
      move: (f, t) => this.attempt(f, t),
    });
    $('#p-next').onclick = () => this.load((this.idx + 1) % this.list.length);
    $('#p-prev').onclick = () => this.load((this.idx - 1 + this.list.length) % this.list.length);
    $('#p-reset').onclick = () => this.load(this.idx);
    $('#p-hint').onclick = () => this.hint();
    $('#p-select').onchange = e => this.load(+e.target.value);
  }

  async open() {
    try { this.list = (await api.puzzles()).puzzles; } catch (e) { toast(e.message); return; }
    const sel = $('#p-select'); sel.textContent = '';
    this.list.forEach((p, i) => { const o = document.createElement('option'); o.value = i; o.textContent = `${i + 1}. ${p.title} (${p.difficulty})`; sel.appendChild(o); });
    if (!this.list.length) { $('#p-title').textContent = 'No puzzles yet'; return; }
    const first = this.list.findIndex(p => !this.solved.has(p.id));
    await this.load(first < 0 ? 0 : first);
  }

  targets(i) {
    const f = sqName(i), out = new Map();
    for (const m of this.state.legal) if (m.startsWith(f)) { const t = sqIndex(m.slice(2, 4)); out.set(t, this.view.pieces[t] !== '.'); }
    return [...out].map(([sq, capture]) => ({ sq, capture }));
  }

  async load(i) {
    const p = this.list[i]; if (!p) return;
    this.idx = i; this.moves = []; this.done = false; this.locked = false; this.hintLevel = 0;
    $('#p-select').value = i;
    $('#p-title').textContent = p.title; $('#p-desc').textContent = p.description;
    const side = p.side === 'w' ? 'White' : 'Black';
    const n = Math.ceil(p.solution_length / 2);
    $('#p-goal strong').textContent = p.goal === 'mate' ? `${side} to move. Find checkmate in ${n}.` : `${side} to move. Find the best move.`;
    this.feedback('', '');
    $('#p-progress').textContent = `Puzzle ${i + 1} of ${this.list.length} - ${this.solved.size} solved`;
    this.view.setOrientation(p.side);
    await this.refresh();
  }

  async refresh() {
    const p = this.list[this.idx];
    this.state = await api.position(p.fen, this.moves);
    this.view.setPieces(fenToPieces(this.state.fen));
    const lm = this.state.last_move;
    this.view.setLast(lm ? sqIndex(lm.slice(0, 2)) : null, lm ? sqIndex(lm.slice(2, 4)) : null);
    this.view.setCheck(this.state.check_square ? sqIndex(this.state.check_square) : null);
    this.view.setHint([]); this.input.clear();
  }

  feedback(text, cls) { const f = $('#p-feedback'); f.textContent = text; f.className = 'status ' + cls; }

  async attempt(from, to) {
    const f = sqName(from), t = sqName(to);
    const cands = this.state.legal.filter(m => m.startsWith(f + t));
    if (!cands.length) return;
    let uci = cands[0];
    if (cands.length > 1) { const pr = settings.autoQueen ? 'q' : await choosePromotion(this.state.turn); if (!pr) return; uci = f + t + pr; }
    this.locked = true;
    try {
      const p = this.list[this.idx];
      const r = await api.puzzleAttempt(p.id, [...this.moves, uci]);
      if (!r.correct) { this.feedback(r.message, 'bad'); play('capture'); return; }
      this.moves.push(uci);
      await this.refresh(); play(soundForSan(this.state.san[this.state.san.length - 1]));
      if (r.complete) {
        this.done = true; this.feedback('Solved! Well done.', 'good');
        this.solved.add(p.id); saveSolved(this.solved); play('end');
        $('#p-progress').textContent = `Puzzle ${this.idx + 1} of ${this.list.length} - ${this.solved.size} solved`;
      } else {
        this.feedback(r.message, 'good');
        await new Promise(res => setTimeout(res, 450));
        this.moves.push(r.reply); await this.refresh(); play('move'); this.hintLevel = 0;
      }
    } catch (e) { toast(e.message); } finally { this.locked = false; }
  }

  async hint() {
    if (this.done || !this.state) return;
    this.hintLevel = Math.min(2, this.hintLevel + 1);
    try {
      const h = await api.puzzleHint(this.list[this.idx].id, this.moves, this.hintLevel);
      this.view.setHint([sqIndex(h.from), ...(h.to ? [sqIndex(h.to)] : [])]);
      this.feedback(this.hintLevel === 1 ? 'Hint: move this piece. Press HINT again to see where.' : 'Hint: this is the move.', '');
    } catch (e) { toast(e.message); }
  }
}
