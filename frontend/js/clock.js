// Chess clock with Fischer increment. Times are in milliseconds.
export function formatClock(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), s = total % 60;
  const p = n => String(n).padStart(2, '0');
  return h ? `${h}:${p(m)}:${p(s)}` : `${p(m)}:${p(s)}`;
}

/** Parse "HH:MM:SS", "MM:SS" or "SS" to seconds; returns null if invalid. */
export function parseClock(text) {
  const parts = String(text).trim().split(':');
  if (parts.length > 3 || parts.some(p => !/^\d{1,2}$/.test(p))) return null;
  const n = parts.map(Number).reverse();
  const secs = (n[0] || 0) + (n[1] || 0) * 60 + (n[2] || 0) * 3600;
  return secs >= 1 && secs <= 86400 ? secs : null;
}

export class ChessClock {
  constructor({ w, b, inc = 0, onTick = () => {}, onFlag = () => {} }) {
    this.t = { w, b }; this.inc = inc; this.active = null; this.running = false; this.last = 0;
    this.onTick = onTick; this.onFlag = onFlag; this.timer = null; this.flagged = false;
  }
  start(side) { this.active = side; this.resume(); }
  resume() {
    if (this.running || !this.active || this.flagged) return;
    this.running = true; this.last = performance.now();
    this.timer = setInterval(() => this.tick(), 100);
  }
  pause() { this.tick(); this.running = false; clearInterval(this.timer); }
  stop() { this.pause(); this.active = null; }
  tick() {
    if (!this.running) return;
    const now = performance.now(), dt = now - this.last; this.last = now;
    this.t[this.active] -= dt;
    if (this.t[this.active] <= 0 && !this.flagged) {
      this.t[this.active] = 0; this.flagged = true; const side = this.active;
      this.running = false; clearInterval(this.timer); this.onTick(); this.onFlag(side); return;
    }
    this.onTick();
  }
  /** Side `side` has just completed a move: add increment and hand the clock over. */
  moved(side) {
    this.tick();
    if (this.flagged) return;
    this.t[side] += this.inc;
    this.active = side === 'w' ? 'b' : 'w';
    this.last = performance.now();
    this.onTick();
  }
  setActive(side) { this.tick(); this.active = side; this.last = performance.now(); this.onTick(); }
  times() { return { w: Math.max(0, Math.round(this.t.w)), b: Math.max(0, Math.round(this.t.b)) }; }
}
