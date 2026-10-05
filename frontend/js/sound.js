// Sound effects: uses assets/sounds/<name>.mp3|wav if present, otherwise Web Audio tones.
import { settings } from './settings.js';

let ctx = null;
const files = {};          // name -> Audio | false
const TONES = {
  move: [[420, .06, 'sine']], capture: [[200, .1, 'square']], check: [[660, .09, 'triangle'], [880, .12, 'triangle']],
  castle: [[330, .07, 'sine'], [440, .09, 'sine']], promotion: [[440, .07, 'sine'], [554, .07, 'sine'], [659, .1, 'sine']],
  start: [[523, .08, 'sine'], [659, .12, 'sine']], end: [[392, .15, 'triangle'], [262, .3, 'triangle']],
};

async function findFile(name) {
  if (name in files) return files[name];
  files[name] = false;
  for (const ext of ['mp3', 'wav', 'ogg']) {
    try {
      const r = await fetch(`assets/sounds/${name}.${ext}`, { method: 'HEAD' });
      if (r.ok && (r.headers.get('content-type') || '').startsWith('audio')) { files[name] = new Audio(`assets/sounds/${name}.${ext}`); break; }
    } catch { /* ignore */ }
  }
  return files[name];
}

function tones(seq) {
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === 'suspended') ctx.resume();
    let t = ctx.currentTime;
    for (const [freq, dur, type] of seq) {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = type; o.frequency.value = freq;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.18, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g); g.connect(ctx.destination); o.start(t); o.stop(t + dur + 0.02);
      t += dur * 0.9;
    }
  } catch { /* audio unavailable */ }
}

export async function play(name) {
  if (!settings.sound) return;
  const f = await findFile(name);
  if (f) { try { f.currentTime = 0; await f.play(); return; } catch { /* fall through */ } }
  tones(TONES[name] || TONES.move);
}

export function soundForSan(san, over) {
  if (!san) return 'move';
  if (over) return 'end';
  if (san.includes('#')) return 'end';
  if (san.includes('+')) return 'check';
  if (san.startsWith('O-O')) return 'castle';
  if (san.includes('=')) return 'promotion';
  if (san.includes('x')) return 'capture';
  return 'move';
}
