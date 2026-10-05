// Analysis mode: step through any move list with FIRST / PREVIOUS / NEXT / LAST.
import { api } from './api.js';
import { BoardView, fenToPieces, sqIndex } from './board.js';
import { $, toast, copyText, renderMoveList, promptBox, showPgn } from './ui.js';

export class Analysis {
  constructor() {
    this.view = new BoardView($('#a-board'), { label: 'Analysis board' });
    this.state = null; this.idx = 0; this.meta = { white: 'White', black: 'Black' };
    $('#a-first').onclick = () => this.go(0);
    $('#a-prev').onclick = () => this.go(this.idx - 1);
    $('#a-next').onclick = () => this.go(this.idx + 1);
    $('#a-last').onclick = () => this.go(this.state ? this.state.ply : 0);
    $('#a-flip').onclick = () => this.view.flip();
    $('#a-copy').onclick = async () => toast((await copyText($('#a-fen').value)) ? 'FEN copied' : 'Copy failed');
    $('#a-loadpgn').onclick = () => this.loadPgn();
    $('#a-export').onclick = () => this.exportPgn();
    document.addEventListener('keydown', e => {
      if ($('#screen-analysis').hidden || e.target.matches('input, textarea, select') || document.querySelector('.overlay')) return;
      if (e.key === 'ArrowLeft' && !e.target.closest('#a-board')) { this.go(this.idx - 1); e.preventDefault(); }
      else if (e.key === 'ArrowRight' && !e.target.closest('#a-board')) { this.go(this.idx + 1); e.preventDefault(); }
      else if (e.key === 'Home') { this.go(0); } else if (e.key === 'End') { this.go(this.state.ply); }
    });
  }

  async open({ startFen = null, moves = [], white = 'White', black = 'Black', ply = null, title = 'Analysis' }) {
    try { this.state = await api.position(startFen, moves); } catch (e) { toast(e.message, 5000); return false; }
    this.meta = { white, black };
    $('#a-title').textContent = title === 'Analysis' ? `Analysis: ${white} vs ${black}` : title;
    this.view.setOrientation('w');
    this.go(ply == null ? this.state.ply : ply);
    return true;
  }

  go(i) {
    const s = this.state; if (!s) return;
    this.idx = Math.max(0, Math.min(s.ply, i));
    const fen = s.fens[this.idx];
    this.view.setPieces(fenToPieces(fen));
    const lm = this.idx ? s.moves[this.idx - 1] : null;
    this.view.setLast(lm ? sqIndex(lm.slice(0, 2)) : null, lm ? sqIndex(lm.slice(2, 4)) : null);
    this.view.setCheck(this.idx === s.ply && s.check_square ? sqIndex(s.check_square) : null);
    $('#a-fen').value = fen;
    let label = 'Start position';
    if (this.idx) {
      const p = this.idx - 1, blackFirst = s.start_turn === 'b', white = (p % 2 === 0) !== blackFirst;
      const num = s.start_fullmove + Math.floor((p + (blackFirst ? 1 : 0)) / 2);
      label = `${num}${white ? '.' : '...'} ${s.san[p]}`;
    }
    $('#a-info').textContent = `Position ${this.idx} of ${s.ply}: ${label}`;
    renderMoveList($('#a-moves'), s, this.idx, p => this.go(p));
    $('#a-first').disabled = $('#a-prev').disabled = this.idx === 0;
    $('#a-next').disabled = $('#a-last').disabled = this.idx === s.ply;
  }

  async loadPgn() {
    let parsed = null;
    const v = await promptBox({ title: 'LOAD PGN', label: 'Paste a PGN game', multiline: true, ok: 'LOAD',
      validate: async t => { try { parsed = await api.parsePgn(t); return null; } catch (e) { return e.message; } } });
    if (v == null || !parsed) return;
    const h = parsed.headers;
    await this.open({ startFen: parsed.start_fen, moves: parsed.moves, white: h.White || 'White', black: h.Black || 'Black', ply: 0 });
  }

  async exportPgn() {
    if (!this.state) return;
    try {
      const r = await api.exportPgn({ start_fen: this.state.start_fen, moves: this.state.moves, white: this.meta.white, black: this.meta.black });
      await showPgn(r.pgn);
    } catch (e) { toast(e.message); }
  }
}
