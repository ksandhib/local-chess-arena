// Chessboard rendering (HTML/CSS + Unicode pieces). Logical squares: 0 = a8 ... 63 = h1.
export const FILES = 'abcdefgh';
export const GLYPH = { K: '\u265A', Q: '\u265B', R: '\u265C', B: '\u265D', N: '\u265E', P: '\u265F' };
const NAMES = { K: 'king', Q: 'queen', R: 'rook', B: 'bishop', N: 'knight', P: 'pawn' };
export const sqName = i => FILES[i & 7] + (8 - (i >> 3));
export const sqIndex = n => FILES.indexOf(n[0]) + (8 - parseInt(n[1], 10)) * 8;
export const isWhitePiece = p => p !== '.' && p === p.toUpperCase();

export function fenToPieces(fen) {
  const out = [];
  for (const ch of fen.split(' ')[0]) {
    if (ch === '/') continue;
    if (ch >= '1' && ch <= '8') for (let k = 0; k < +ch; k++) out.push('.'); else out.push(ch);
  }
  while (out.length < 64) out.push('.');
  return out.slice(0, 64);
}

export function pieceHtml(p) {
  return `<span class="pc ${isWhitePiece(p) ? 'w' : 'b'}" aria-hidden="true">${GLYPH[p.toUpperCase()]}\uFE0E</span>`;
}

export class BoardView {
  constructor(host, { label = 'Chessboard' } = {}) {
    this.el = document.createElement('div');
    this.el.className = 'board'; this.el.setAttribute('role', 'grid'); this.el.setAttribute('aria-label', label);
    this.sq = []; this.pieces = Array(64).fill('.'); this.orientation = 'w';
    this.selected = null; this.targets = new Map(); this.last = []; this.checkSq = null; this.hintSq = [];
    this.cursor = 60; this.onActivate = null; this.onEscape = null;
    for (let i = 0; i < 64; i++) {
      const d = document.createElement('div');
      d.className = 'sq ' + ((((i >> 3) + (i & 7)) & 1) ? 'dark' : 'light');
      d.dataset.i = i; d.setAttribute('role', 'gridcell'); d.tabIndex = -1;
      d.innerHTML = '<i class="cr"></i><i class="cf"></i>';
      this.sq.push(d);
    }
    this.sq[this.cursor].tabIndex = 0;
    this.layout();
    host.appendChild(this.el);
    this.updateLabels();
    new ResizeObserver(() => this.el.style.setProperty('--sq', (this.el.clientWidth / 8) + 'px')).observe(this.el);
    this.el.addEventListener('keydown', e => this.onKey(e));
  }

  layout() {
    const order = this.orientation === 'w' ? [...Array(64).keys()] : [...Array(64).keys()].reverse();
    order.forEach((i, v) => {
      const d = this.sq[i];
      this.el.appendChild(d);
      d.querySelector('.cf').textContent = (v >> 3) === 7 ? FILES[i & 7] : '';
      d.querySelector('.cr').textContent = (v & 7) === 0 ? String(8 - (i >> 3)) : '';
    });
  }

  setOrientation(o) { if (o !== this.orientation) { this.orientation = o; this.layout(); } }
  flip() { this.setOrientation(this.orientation === 'w' ? 'b' : 'w'); }

  setPieces(arr) {
    for (let i = 0; i < 64; i++) {
      if (arr[i] === this.pieces[i]) continue;
      this.pieces[i] = arr[i];
      const d = this.sq[i];
      const old = d.querySelector('.pc'); if (old) old.remove();
      if (arr[i] !== '.') d.insertAdjacentHTML('beforeend', pieceHtml(arr[i]));
    }
    this.updateLabels();
  }

  pulse(i) { const p = this.sq[i].querySelector('.pc'); if (p) { p.classList.add('pop'); setTimeout(() => p.classList.remove('pop'), 250); } }

  updateLabels() {
    for (let i = 0; i < 64; i++) {
      const p = this.pieces[i];
      let t = p === '.' ? `Empty square ${sqName(i)}` : `${isWhitePiece(p) ? 'White' : 'Black'} ${NAMES[p.toUpperCase()]} on ${sqName(i)}`;
      if (i === this.selected) t += ', selected';
      if (this.targets.has(i)) t += this.targets.get(i) ? ', capture available' : ', legal move';
      if (i === this.checkSq) t += ', king in check';
      this.sq[i].setAttribute('aria-label', t);
    }
  }

  applyMarks() {
    this.sq.forEach((d, i) => {
      d.classList.toggle('sel', i === this.selected);
      d.classList.toggle('target', this.targets.has(i) && !this.targets.get(i));
      d.classList.toggle('capture', this.targets.has(i) && this.targets.get(i));
      d.classList.toggle('last', this.last.includes(i));
      d.classList.toggle('check', i === this.checkSq);
      d.classList.toggle('hint', this.hintSq.includes(i));
    });
    this.updateLabels();
  }
  setSelection(sel, targets = [], show = true) {
    this.selected = sel;
    this.targets = new Map(show ? targets.map(t => [t.sq, t.capture]) : []);
    this.applyMarks();
  }
  setLast(a, b) { this.last = a == null ? [] : [a, b]; this.applyMarks(); }
  setCheck(i) { this.checkSq = i; this.applyMarks(); }
  setHint(list) { this.hintSq = list; this.applyMarks(); }

  setCursor(i, focus = true) {
    this.sq[this.cursor].tabIndex = -1; this.cursor = i; this.sq[i].tabIndex = 0;
    if (focus) this.sq[i].focus({ preventScroll: true });
  }

  onKey(e) {
    const keys = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    if (keys[e.key]) {
      const f = this.orientation === 'w' ? 1 : -1;
      const r = Math.min(7, Math.max(0, (this.cursor >> 3) + keys[e.key][0] * f));
      const c = Math.min(7, Math.max(0, (this.cursor & 7) + keys[e.key][1] * f));
      this.setCursor(r * 8 + c); e.preventDefault(); e.stopPropagation();
    } else if ((e.key === 'Enter' || e.key === ' ') && this.onActivate) {
      e.preventDefault(); e.stopPropagation(); this.onActivate(this.cursor);
    } else if (e.key === 'Escape' && this.onEscape && this.onEscape()) {
      e.stopPropagation();
    }
  }

  squareAt(x, y) {
    const t = document.elementFromPoint(x, y);
    const s = t && t.closest && t.closest('.sq');
    return s && this.el.contains(s) ? +s.dataset.i : null;
  }

  startGhost(i) {
    const p = this.pieces[i]; if (p === '.') return;
    this.ghost = document.createElement('span');
    this.ghost.className = `pc ghost ${isWhitePiece(p) ? 'w' : 'b'}`;
    this.ghost.style.setProperty('--sq', this.el.clientWidth / 8 + 'px');
    this.ghost.textContent = GLYPH[p.toUpperCase()] + '\uFE0E';
    document.body.appendChild(this.ghost);
    this.sq[i].classList.add('drag-src'); this.dragSrc = i;
  }
  moveGhost(x, y) { if (this.ghost) { this.ghost.style.left = x + 'px'; this.ghost.style.top = y + 'px'; } }
  endGhost() {
    if (this.ghost) { this.ghost.remove(); this.ghost = null; }
    if (this.dragSrc != null) { this.sq[this.dragSrc].classList.remove('drag-src'); this.dragSrc = null; }
  }
}
