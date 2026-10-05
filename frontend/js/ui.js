// Shared UI helpers: DOM shortcuts, modals, toasts, screen switching, move lists.
import { GLYPH } from './board.js';

export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];
export function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
export const go = (screen, data) => document.dispatchEvent(new CustomEvent('navigate', { detail: { screen, data } }));

let toastTimer = 0;
export function toast(msg, ms = 2800) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), ms);
}

let current = null;
export const isModalOpen = () => !!current;

/** Generic modal. Resolves with the clicked button's value (or `dismissValue` on Esc). */
export function modal({ title, html = '', node = null, buttons = [{ label: 'OK', value: true, primary: true }], dismissValue = null, onOpen = null }) {
  if (current) current.close(dismissValue);
  return new Promise(resolve => {
    const prevFocus = document.activeElement;
    const overlay = document.createElement('div'); overlay.className = 'overlay';
    const dlg = document.createElement('div'); dlg.className = 'dialog'; dlg.setAttribute('role', 'dialog'); dlg.setAttribute('aria-modal', 'true');
    const id = 'dlg' + Math.random().toString(36).slice(2, 7); dlg.setAttribute('aria-labelledby', id);
    dlg.innerHTML = `<h2 id="${id}">${esc(title)}</h2><div class="body">${html}</div><div class="actions"></div>`;
    if (node) $('.body', dlg).appendChild(node);
    const actions = $('.actions', dlg);
    const close = v => { overlay.remove(); document.removeEventListener('keydown', onKey, true); current = null; prevFocus && prevFocus.focus && prevFocus.focus(); resolve(v); };
    for (const b of buttons) {
      const btn = document.createElement('button'); btn.className = 'btn' + (b.primary ? ' primary' : '') + (b.danger ? ' danger' : '');
      btn.textContent = b.label;
      btn.addEventListener('click', async () => { if (b.beforeClose && (await b.beforeClose(dlg)) === false) return; close(typeof b.value === 'function' ? b.value(dlg) : b.value); });
      actions.appendChild(btn);
    }
    const onKey = e => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); close(dismissValue); }
      else if (e.key === 'Tab') {
        const f = $$('button, input, textarea, select', dlg).filter(x => !x.disabled);
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', onKey, true);
    overlay.appendChild(dlg); $('#modal-root').appendChild(overlay);
    current = { close };
    if (onOpen) onOpen(dlg);
    const focusEl = $('textarea, input', dlg) || $('.btn.primary', dlg) || $('.btn, .promo-btn', dlg);
    focusEl && focusEl.focus();
  });
}

export const confirmBox = (msg, yes = 'YES', no = 'CANCEL', title = 'Please confirm') =>
  modal({ title, html: `<p>${esc(msg)}</p>`, buttons: [{ label: yes, value: true, primary: true }, { label: no, value: false }], dismissValue: false });

export const notice = (title, msg) => modal({ title, html: `<p>${esc(msg)}</p>` });

/** Text prompt. `validate(text)` may return an error string (keeps dialog open). */
export function promptBox({ title, label, value = '', multiline = false, ok = 'OK', validate = null, readonly = false, extra = [] }) {
  const field = document.createElement('div'); field.className = 'field';
  const id = 'f' + Math.random().toString(36).slice(2, 7);
  field.innerHTML = `<label for="${id}">${esc(label)}</label>` + (multiline ? `<textarea id="${id}" spellcheck="false"></textarea>` : `<input id="${id}" autocomplete="off" spellcheck="false">`) + '<p class="error" role="alert"></p>';
  const input = $('#' + id, field); input.value = value; input.readOnly = readonly;
  const buttons = [{ label: ok, primary: true, value: () => input.value, beforeClose: async () => {
    if (!validate) return true;
    const err = await validate(input.value);
    if (err) { $('.error', field).textContent = err; return false; }
    return true; } }];
  for (const x of extra) buttons.push({ label: x.label, value: null, beforeClose: async () => { await x.action(input.value); return false; } });
  buttons.push({ label: 'CANCEL', value: null });
  return modal({ title, node: field, buttons, dismissValue: null });
}

export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch {
    const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch { /* */ } ta.remove(); return ok;
  }
}

export function downloadText(name, text) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' })); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/** Show PGN in a dialog with copy / download. */
export function showPgn(pgn) {
  return promptBox({ title: 'EXPORT PGN', label: 'PGN', value: pgn, multiline: true, readonly: true, ok: 'CLOSE',
    extra: [{ label: 'COPY', action: async t => toast((await copyText(t)) ? 'PGN copied' : 'Copy failed') },
            { label: 'DOWNLOAD .pgn', action: t => { downloadText('local-chess-arena.pgn', t); toast('PGN downloaded'); } }] });
}

/** Promotion chooser. Resolves 'q'|'r'|'b'|'n' or null if cancelled. */
export function choosePromotion(color) {
  return new Promise(resolve => {
    const items = [['q', 'QUEEN', 'Q'], ['r', 'ROOK', 'R'], ['b', 'BISHOP', 'B'], ['n', 'KNIGHT', 'N']];
    const wrap = document.createElement('div'); wrap.className = 'promo';
    for (const [v, label, letter] of items) {
      const b = document.createElement('button'); b.className = 'promo-btn'; b.setAttribute('aria-label', 'Promote to ' + label.toLowerCase());
      b.innerHTML = `<span class="pc ${color}">${GLYPH[letter]}\uFE0E</span><span>${label}</span>`;
      b.addEventListener('click', () => { picked = v; $$('.btn', b.closest('.dialog'))[0].click(); });
      wrap.appendChild(b);
    }
    let picked = null;
    modal({ title: 'PROMOTE PAWN', node: wrap, buttons: [{ label: 'CANCEL', value: () => picked }], dismissValue: null }).then(resolve);
  });
}

/** Render a SAN list as numbered rows. `onPick(ply)` makes moves clickable. */
export function renderMoveList(ol, st, activePly = -1, onPick = null) {
  ol.textContent = '';
  const rows = new Map();
  const blackFirst = st.start_turn === 'b';
  st.san.forEach((s, p) => {
    const white = (p % 2 === 0) !== blackFirst;
    const num = st.start_fullmove + Math.floor((p + (blackFirst ? 1 : 0)) / 2);
    if (!rows.has(num)) rows.set(num, { num, w: null, b: null });
    rows.get(num)[white ? 'w' : 'b'] = p;
  });
  for (const r of rows.values()) {
    const li = document.createElement('li');
    li.innerHTML = `<span class="n">${r.num}.</span>`;
    for (const side of ['w', 'b']) {
      const cell = document.createElement(onPick ? 'button' : 'span');
      if (r[side] !== null) {
        cell.textContent = st.san[r[side]];
        if (onPick) { cell.type = 'button'; cell.addEventListener('click', () => onPick(r[side] + 1)); }
        if (r[side] + 1 === activePly) { cell.classList.add('cur'); cell.setAttribute('aria-current', 'true'); }
      } else cell.textContent = side === 'w' && r.w === null ? '...' : '';
      li.appendChild(cell);
    }
    ol.appendChild(li);
  }
  const cur = ol.querySelector('.cur');
  if (cur) cur.scrollIntoView({ block: 'nearest' }); else ol.scrollTop = ol.scrollHeight;
}

export function formatResult(result, termination) {
  const who = result === '1-0' ? 'WHITE WINS' : result === '0-1' ? 'BLACK WINS' : result === '1/2-1/2' ? 'DRAW' : 'NO RESULT';
  const reason = (termination || '').toUpperCase();
  return { who, reason };
}
