// Click-to-move, drag-and-drop (mouse + touch via pointer events) and keyboard input.
export class Input {
  /** ctrl: { enabled(), canSelect(i), targets(i)->[{sq,capture}], move(from,to) } */
  constructor(view, ctrl) {
    this.view = view; this.ctrl = ctrl; this.sel = null; this.targets = []; this.drag = null; this.busy = false;
    view.el.addEventListener('pointerdown', e => this.down(e));
    window.addEventListener('pointermove', e => this.moving(e));
    window.addEventListener('pointerup', e => this.up(e));
    window.addEventListener('pointercancel', () => this.cancel());
    view.onActivate = i => this.activate(i);
    view.onEscape = () => { if (this.sel != null) { this.clear(); return true; } return false; };
  }
  isTarget(i) { return this.targets.some(t => t.sq === i); }
  select(i) { this.sel = i; this.targets = this.ctrl.targets(i); this.view.setSelection(i, this.targets, this.ctrl.showHints ? this.ctrl.showHints() : true); }
  clear() { this.sel = null; this.targets = []; this.view.setSelection(null, []); }
  async commit(from, to) {
    this.clear(); this.busy = true;
    try { await this.ctrl.move(from, to); } finally { this.busy = false; }
  }
  activate(i) {
    if (this.busy || !this.ctrl.enabled()) return;
    if (this.sel != null && this.isTarget(i)) this.commit(this.sel, i);
    else if (this.ctrl.canSelect(i) && i !== this.sel) this.select(i);
    else this.clear();
  }
  down(e) {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    const el = e.target.closest('.sq'); if (!el) return;
    const i = +el.dataset.i;
    this.view.setCursor(i, false);
    if (this.busy || !this.ctrl.enabled()) return;
    if (this.sel != null && this.isTarget(i)) { this.commit(this.sel, i); return; }
    if (this.ctrl.canSelect(i)) {
      const was = this.sel === i;
      this.select(i);
      this.drag = { from: i, x: e.clientX, y: e.clientY, active: false, was };
    } else this.clear();
  }
  moving(e) {
    const d = this.drag; if (!d) return;
    if (!d.active) {
      if (Math.hypot(e.clientX - d.x, e.clientY - d.y) < 6) return;
      d.active = true; this.view.startGhost(d.from);
    }
    this.view.moveGhost(e.clientX, e.clientY);
  }
  up(e) {
    const d = this.drag; if (!d) return;
    this.drag = null;
    if (d.active) {
      this.view.endGhost();
      const to = this.view.squareAt(e.clientX, e.clientY);
      if (to != null && to !== d.from && this.isTarget(to)) this.commit(d.from, to);
      else if (to !== d.from) this.clear();
    } else if (d.was) this.clear();
  }
  cancel() { if (this.drag) { this.view.endGhost(); this.drag = null; } }
}
