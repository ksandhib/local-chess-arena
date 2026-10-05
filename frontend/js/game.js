// Play modes: player vs computer, local two-player, and games started from the practice board.
import { api } from './api.js';
import { BoardView, fenToPieces, sqIndex, sqName, pieceHtml, isWhitePiece } from './board.js';
import { Input } from './input.js';
import { ChessClock, formatClock } from './clock.js';
import { settings } from './settings.js';
import { play, soundForSan } from './sound.js';
import { $, toast, modal, confirmBox, promptBox, choosePromotion, renderMoveList, showPgn, copyText, formatResult, go, esc } from './ui.js';

const TERMS = { checkmate: 'CHECKMATE', stalemate: 'STALEMATE', resignation: 'RESIGNATION', time: 'TIME', agreement: 'DRAW AGREEMENT' };

export class GameScreen {
  constructor() {
    this.view = new BoardView($('#game-board'), { label: 'Chessboard' });
    this.input = new Input(this.view, {
      enabled: () => this.canMove(),
      canSelect: i => this.canSelect(i),
      targets: i => this.targetsFor(i),
      showHints: () => settings.showMoves,
      move: (f, t) => this.tryMove(f, t),
    });
    this.id = null; this.state = null; this.cfg = null; this.redo = []; this.gen = 0;
    this.over = false; this.thinking = false; this.busy = false; this.paused = false; this.clock = null;
    const b = id => $('#' + id);
    b('b-undo').onclick = () => this.undo();
    b('b-redo').onclick = () => this.redoMove();
    b('b-draw').onclick = () => this.offerDraw();
    b('b-resign').onclick = () => this.resign();
    b('b-pause').onclick = () => this.togglePause();
    b('b-flip').onclick = () => this.view.flip();
    b('b-save').onclick = () => this.save();
    b('b-new').onclick = () => this.newGame();
    b('b-copyfen').onclick = async () => toast((await copyText(this.state.fen)) ? 'FEN copied' : 'Copy failed');
    b('b-loadfen').onclick = () => this.loadFen();
    b('b-pgn').onclick = () => this.exportPgn();
    b('b-analyze').onclick = () => this.analyze();
    b('g-toggle').onclick = () => {
      const col = $('#g-toggle').closest('.panel-col'); const c = col.classList.toggle('collapsed');
      $('#g-toggle').setAttribute('aria-expanded', String(!c));
    };
  }

  get mode() { return this.cfg.mode; }
  get isPvc() { return this.cfg && this.cfg.mode === 'pvc'; }
  get human() { return this.cfg.humanColor; }
  isAiTurn() { return this.isPvc && !this.over && this.state.turn !== this.human; }
  hasActiveGame() { return this.id != null && !this.over; }

  // ---------- lifecycle ----------
  async start(cfg) {
    await this.abandon();
    this.gen++;
    if (this.clock) { this.clock.stop(); this.clock = null; }
    this.cfg = { ...cfg };
    const body = { mode: cfg.mode, white: cfg.white, black: cfg.black, human_color: cfg.humanColor || null,
      difficulty: cfg.difficulty || null, start_fen: cfg.startFen || null, moves: cfg.moves || [],
      time_control: cfg.clock ? { base: Math.round(cfg.clock.baseSec ?? 0), inc: cfg.clock.inc } : null };
    let res;
    try { res = await api.createGame(body); } catch (e) { toast(e.message, 5000); go('menu'); return; }
    this.id = res.game.id; this.state = res.state; this.redo = []; this.over = false; this.thinking = false; this.paused = false;
    this.cfg.startFen = res.state.start_fen;
    this.view.setOrientation(this.isPvc ? this.human : 'w');
    if (cfg.clock) {
      const ms = cfg.clock.times || { w: cfg.clock.w * 1000, b: cfg.clock.b * 1000 };
      this.clock = new ChessClock({ w: ms.w, b: ms.b, inc: cfg.clock.inc * 1000, onTick: () => this.renderClocks(), onFlag: s => this.onFlag(s) });
      if (cfg.paused) this.paused = true; else if (!this.state.status.game_over) this.clock.start(this.state.turn);
    }
    $('#g-white-name').textContent = cfg.white; $('#g-black-name').textContent = cfg.black;
    this.render(); play('start');
    if (this.state.status.game_over) { this.over = true; await this.handleOver(res.game); return; }
    if (this.paused) toast('Game loaded. Press RESUME to start the clock.', 4000);
    else this.maybeAI();
    this.view.setCursor(this.view.orientation === 'w' ? 52 : 11, false);
  }

  async abandon() {
    if (this.id == null || this.over) { this.id = this.over ? this.id : null; return; }
    const id = this.id; this.gen++; this.id = null;
    try { if (this.state && this.state.ply === 0) await api.deleteGame(id); else await api.finish(id, 'abandoned'); } catch { /* already gone */ }
    if (this.clock) this.clock.stop();
  }

  async confirmLeave() {
    if (!this.hasActiveGame() || !this.state || this.state.ply === 0) return true;
    return confirmBox('Leave this game? It will be kept in Game History (save it first to continue later).', 'LEAVE', 'STAY');
  }

  async newGame() {
    if (this.hasActiveGame() && !(await confirmBox('Start a new game?'))) return;
    const c = this.cfg;
    const cfg = { ...c, moves: [], paused: false };
    if (c.mode === 'pvc' && c.randomColor) cfg.humanColor = Math.random() < .5 ? 'w' : 'b';
    if (c.clock) cfg.clock = { ...c.clock, times: null };
    await this.start(cfg);
  }

  // ---------- input controller ----------
  canMove() {
    return !!this.state && !this.over && !this.paused && !this.thinking && !this.busy && (!this.isPvc || this.state.turn === this.human);
  }
  canSelect(i) {
    const p = this.view.pieces[i];
    if (p === '.' || isWhitePiece(p) !== (this.state.turn === 'w')) return false;
    const f = sqName(i);
    return this.state.legal.some(m => m.startsWith(f));
  }
  targetsFor(i) {
    const f = sqName(i), seen = new Map();
    for (const m of this.state.legal) {
      if (!m.startsWith(f)) continue;
      const t = sqIndex(m.slice(2, 4));
      const cap = this.view.pieces[t] !== '.' || (this.view.pieces[i].toUpperCase() === 'P' && (t & 7) !== (i & 7));
      seen.set(t, cap);
    }
    return [...seen].map(([sq, capture]) => ({ sq, capture }));
  }
  async tryMove(from, to) {
    const f = sqName(from), t = sqName(to);
    const cands = this.state.legal.filter(m => m.startsWith(f + t));
    if (!cands.length) return;
    let uci = cands[0];
    if (cands.length > 1) {
      const promo = settings.autoQueen ? 'q' : await choosePromotion(this.state.turn);
      if (!promo) return;
      uci = f + t + promo;
    }
    await this.submit(uci);
  }

  // ---------- moves ----------
  async submit(uci, fromRedo = false) {
    const gen = this.gen, mover = this.state.turn;
    this.busy = true;
    try {
      const res = await api.postMove(this.id, uci);
      if (gen !== this.gen) return;
      this.state = res.state;
      if (!fromRedo) this.redo = [];
      const over = res.state.status.game_over;
      if (this.clock) { this.clock.moved(mover); if (over) this.clock.stop(); }
      this.render(true);
      play(soundForSan(res.state.san[res.state.san.length - 1], false));
      if (over) { this.over = true; await this.handleOver(res.game); }
      else if (!fromRedo) this.maybeAI();
    } catch (e) { toast(e.message, 4000); } finally { this.busy = false; this.renderButtons(); }
  }

  async maybeAI() {
    if (!this.isAiTurn() || this.paused || this.thinking) return;
    const gen = this.gen;
    this.thinking = true; this.render();
    try {
      const r = await api.aiMove(this.id);
      this.thinking = false;
      if (gen !== this.gen) return;
      await this.submit(r.move);
    } catch (e) {
      this.thinking = false; this.render();
      if (gen === this.gen) toast('Computer error: ' + e.message, 5000);
    }
  }

  async undo() {
    if (this.thinking || this.busy || this.over) return;
    const n = this.undoCount(); if (!n) return;
    this.gen++; this.busy = true;
    try {
      const r = await api.undo(this.id, n);
      this.state = r.state;
      this.redo.push(...r.undone.slice().reverse());
      if (this.clock) this.clock.setActive(this.state.turn);
      this.render();
    } catch (e) { toast(e.message); } finally { this.busy = false; this.renderButtons(); }
    this.maybeAI();
  }
  undoCount() {
    const len = this.state ? this.state.ply : 0;
    if (this.isPvc) return len >= 2 ? 2 : 0;
    return len >= 1 ? 1 : 0;
  }
  async redoMove() {
    if (this.thinking || this.busy || this.over || !this.redo.length) return;
    const n = this.isPvc ? Math.min(2, this.redo.length) : 1;
    for (let k = 0; k < n && !this.over; k++) await this.submit(this.redo.pop(), true);
    this.maybeAI();
  }

  // ---------- results ----------
  async onFlag(side) {
    if (this.over || this.id == null) return;
    this.gen++;
    try { const r = await api.finish(this.id, 'time', side); this.over = true; this.state = r.state; this.render(); await this.handleOver(r.game); }
    catch (e) { toast(e.message); }
  }

  async resign() {
    if (this.over || !this.state) return;
    const loser = this.isPvc ? this.human : this.state.turn;
    const name = loser === 'w' ? this.cfg.white : this.cfg.black;
    if (!(await confirmBox(`${this.isPvc ? '' : name + ': '}Are you sure you want to resign?`))) return;
    this.gen++; this.thinking = false;
    try { const r = await api.finish(this.id, 'resignation', loser); this.over = true; if (this.clock) this.clock.stop(); this.render(); await this.handleOver(r.game); }
    catch (e) { toast(e.message); }
  }

  async offerDraw() {
    if (this.over || !this.state || this.thinking) return;
    const side = this.state.turn, name = side === 'w' ? this.cfg.white : this.cfg.black;
    let accept = false;
    if (this.isPvc) {
      try {
        const r = await api.aiDraw(this.id);
        accept = r.accept;
        if (!accept) { await modal({ title: 'DRAW DECLINED', html: `<p>${esc(r.reason)}</p>` }); return; }
        await modal({ title: 'DRAW ACCEPTED', html: `<p>${esc(r.reason)}</p>` });
      } catch (e) { toast(e.message); return; }
    } else {
      accept = await modal({ title: 'DRAW OFFER', html: `<p>${esc(name)} offers a draw. Does the opponent accept?</p>`,
        buttons: [{ label: 'ACCEPT', value: true, primary: true }, { label: 'DECLINE', value: false }], dismissValue: false });
      if (!accept) { toast('Draw declined'); return; }
    }
    this.gen++;
    try { const r = await api.finish(this.id, 'agreement'); this.over = true; if (this.clock) this.clock.stop(); this.render(); await this.handleOver(r.game); }
    catch (e) { toast(e.message); }
  }

  async handleOver(game) {
    if (this.clock) this.clock.stop();
    this.over = true; this.lastResult = game.result; this.lastTerm = game.termination; this.render(); play('end');
    const { who, reason } = formatResult(game.result, game.termination);
    const term = game.termination || '';
    const title = term === 'checkmate' ? 'CHECKMATE' : term === 'stalemate' ? 'STALEMATE' : game.result === '1/2-1/2' ? 'DRAW' : (TERMS[term] || 'GAME OVER');
    const showReason = !['checkmate'].includes(term);
    const choice = await modal({ title, html: `<div class="big">${who}</div>${showReason ? `<p>Reason:<br><strong>${esc(reason)}</strong></p>` : ''}`,
      buttons: [{ label: 'NEW GAME', value: 'new', primary: true }, { label: 'ANALYZE', value: 'analyze' }, { label: 'MAIN MENU', value: 'menu' }], dismissValue: 'stay' });
    if (choice === 'new') await this.newGame();
    else if (choice === 'analyze') this.analyze();
    else if (choice === 'menu') go('menu');
  }

  // ---------- save / FEN / PGN ----------
  async save() {
    if (this.id == null) return;
    const def = `${this.cfg.white} vs ${this.cfg.black} - move ${this.state.fullmove}`;
    const name = await promptBox({ title: 'SAVE GAME', label: 'Name', value: def.slice(0, 60), ok: 'SAVE',
      validate: v => (v.trim() ? null : 'Please enter a name.') });
    if (!name) return;
    try {
      const clocks = this.clock ? this.clock.times() : null;
      await api.saveGame({ name: name.trim(), game_id: this.id, clocks });
      toast('Game saved');
    } catch (e) { toast(e.message, 4000); }
  }
  async loadFen() {
    let normalized = null;
    const v = await promptBox({ title: 'LOAD FEN', label: 'Paste a FEN to start a new game from that position', value: '', ok: 'START',
      validate: async t => { try { const r = await api.validateFen(t.trim()); if (!r.valid) return r.error; normalized = r.fen; return null; } catch (e) { return e.message; } } });
    if (v == null || !normalized) return;
    await this.start({ ...this.cfg, startFen: normalized, moves: [], paused: false, clock: this.cfg.clock ? { ...this.cfg.clock, times: null } : null });
  }
  async exportPgn() {
    try {
      const r = await api.exportPgn({ start_fen: this.state.start_fen, moves: this.state.moves, white: this.cfg.white, black: this.cfg.black });
      await showPgn(r.pgn);
    } catch (e) { toast(e.message); }
  }
  analyze() {
    go('analysis', { startFen: this.state.start_fen, moves: this.state.moves, white: this.cfg.white, black: this.cfg.black, ply: this.state.ply });
  }
  togglePause() {
    if (!this.clock || this.over) return;
    this.paused = !this.paused;
    if (this.paused) this.clock.pause(); else { if (!this.clock.active) this.clock.active = this.state.turn; this.clock.resume(); }
    this.render();
    if (!this.paused) this.maybeAI();
  }

  // ---------- rendering ----------
  render(pulse = false) {
    const s = this.state; if (!s) return;
    this.view.setPieces(fenToPieces(s.fen));
    const lm = s.last_move;
    this.view.setLast(lm ? sqIndex(lm.slice(0, 2)) : null, lm ? sqIndex(lm.slice(2, 4)) : null);
    this.view.setCheck(s.check_square ? sqIndex(s.check_square) : null);
    this.view.setSelection(null, []);
    this.input.clear();
    if (pulse && lm) this.view.pulse(sqIndex(lm.slice(2, 4)));
    const white = s.turn === 'w';
    $('#g-turn').textContent = this.over ? 'GAME OVER' : (white ? 'WHITE TO MOVE' : 'BLACK TO MOVE');
    $('#g-movenum').textContent = `Move ${s.fullmove}`;
    const st = $('#g-status'); st.className = 'status';
    let text = '';
    if (this.over) {
      const { who, reason } = formatResult(this.finalResult(), this.finalTermination());
      text = `${who}${reason ? ' - ' + reason : ''}`; st.classList.add('good');
    } else if (this.thinking) text = 'COMPUTER THINKING...';
    else if (this.paused) text = 'PAUSED';
    else if (s.check) { text = 'CHECK!'; st.classList.add('bad'); }
    st.textContent = text;
    $('#g-prow-w').classList.toggle('active', !this.over && white);
    $('#g-prow-b').classList.toggle('active', !this.over && !white);
    for (const side of ['w', 'b']) $('#g-cap-' + side).innerHTML = s.captured[side].map(pieceHtml).join('');
    const m = s.material;
    $('#g-material').textContent = m === 0 ? 'Material: even' : `Material: ${m > 0 ? 'White' : 'Black'} +${Math.abs(m)}`;
    renderMoveList($('#g-moves'), s, s.ply);
    this.renderClocks(); this.renderButtons();
  }
  finalResult() { const s = this.state.status; return s.game_over ? s.result : (this.lastResult || '*'); }
  finalTermination() { const s = this.state.status; return s.game_over ? s.termination : (this.lastTerm || ''); }
  renderClocks() {
    const t = this.clock ? this.clock.times() : null;
    for (const side of ['w', 'b']) {
      const el = $(`#g-${side === 'w' ? 'white' : 'black'}-clock`);
      if (!t) { el.textContent = 'no clock'; el.className = 'clock none'; continue; }
      el.textContent = formatClock(t[side]); el.className = 'clock' + (t[side] < 10000 ? ' low' : '');
    }
  }
  renderButtons() {
    const live = !this.over && !!this.state;
    $('#b-undo').disabled = !live || this.thinking || this.busy || !this.undoCount();
    $('#b-redo').disabled = !live || this.thinking || this.busy || !this.redo.length;
    $('#b-draw').disabled = !live || this.thinking; $('#b-resign').disabled = !live;
    $('#b-pause').hidden = !this.clock; $('#b-pause').textContent = this.paused ? 'RESUME' : 'PAUSE'; $('#b-pause').disabled = !live;
    $('#b-save').disabled = this.id == null || this.over; $('#b-analyze').disabled = !this.state || this.state.ply === 0;
    $('#b-loadfen').disabled = this.thinking;
  }
}
