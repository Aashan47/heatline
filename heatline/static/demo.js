/* The demo scene.

   Written to Hackathons/DEMO-RECORDING/SCENE-TEMPLATE.md. A beat is the agent
   visibly deciding something, not the screen changing. Each beat waits on an
   `at` predicate, which is text that appears only once that beat has actually
   happened, so the narration can never describe a screen that has not arrived.

   The unit of work the viewer follows: a rider asks whether they can work this
   afternoon, the agent resolves the hour, assesses it, and answers. Then they
   ask about a day further out, and the agent declines. */

(() => {
const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------- frame the app as a product window ---------- */

document.body.classList.add('demo');
const app = document.querySelector('.app');
const frame = document.createElement('div');
frame.className = 'frame';
frame.innerHTML = `<div class="win" id="win">
  <div class="titlebar">
    <i style="background:#ff5f57"></i><i style="background:#febc2e"></i>
    <i style="background:#28c840"></i>
    <span>heatline  ·  Karachi occupational heat exposure</span>
  </div>
</div>`;
document.body.appendChild(frame);
$('win').appendChild(app);

const chrome = document.createElement('div');
chrome.innerHTML = `
  <div class="cur" id="cur">
    <svg viewBox="0 0 22 22" width="22" height="22">
      <path d="M4 2.2 17.4 11.3l-5.7.7-2.9 5.3z" fill="#fff"
            stroke="#0a0f16" stroke-width="1.4" stroke-linejoin="round"/>
    </svg><div class="ring"></div>
  </div>
  <div class="slate" id="slate-open">
    <h1>31 degrees is not a<br>safe afternoon in <span class="hl">Karachi</span></h1>
    <p>An exposure limit most weather apps cannot see.</p>
  </div>
  <div class="slate" id="slate-close">
    <h1>Every number has a<br>primary source</h1>
    <p>WBGT by Liljegren via ECMWF thermofeel. Limits from NIOSH 2016-106.</p>
    <div class="repo">github.com/Aashan47/heatline</div>
    <div class="foot">Built with Gemini and the Agent Development Kit.
      Weather data by Open-Meteo.com, CC BY 4.0.</div>
  </div>
  <div class="cap" id="cap"><div class="kicker" id="cap-k"></div>
    <div class="line" id="cap-l"></div></div>
  <div class="prog" id="prog"></div>`;
document.body.appendChild(chrome);

/* ---------- camera ---------- */

function camera(target, scale) {
  const win = $('win');
  if (!target) { win.style.transform = 'scale(1)'; return; }
  const node = typeof target === 'string' ? document.querySelector(target) : target;
  if (!node) { win.style.transform = 'scale(1)'; return; }

  // Focus is computed from the live box, so a zoom cannot frame empty
  // wallpaper the way a hardcoded region can when the layout shifts.
  const w = win.getBoundingClientRect();
  const t = node.getBoundingClientRect();
  const cx = (t.left + t.width / 2) - (w.left + w.width / 2);
  const cy = (t.top + t.height / 2) - (w.top + w.height / 2);
  win.style.transform = `scale(${scale}) translate(${-cx / scale}px, ${-cy / scale}px)`;
}

/* ---------- synthetic cursor ---------- */

async function point(sel, { tap = false } = {}) {
  const node = document.querySelector(sel);
  if (!node) return;
  const r = node.getBoundingClientRect();
  const cur = $('cur');
  cur.classList.add('on');
  cur.style.transform = `translate(${r.left + r.width / 2}px, ${r.top + r.height / 2}px)`;
  await sleep(660);
  if (tap) {
    cur.classList.add('tap');
    setTimeout(() => cur.classList.remove('tap'), 480);
    await sleep(240);
  }
}

async function type(sel, text) {
  const input = document.querySelector(sel);
  input.focus();
  input.value = '';
  for (const ch of text) {
    input.value += ch;
    await sleep(34 + Math.random() * 26);
  }
}

/* ---------- captions ---------- */

function caption(kicker, line) {
  const c = $('cap');
  if (!line) { c.classList.remove('on'); return; }
  const set = () => { $('cap-k').textContent = kicker; $('cap-l').textContent = line; };
  if (c.classList.contains('on')) {
    c.classList.remove('on');
    setTimeout(() => { set(); c.classList.add('on'); }, 250);
  } else { set(); c.classList.add('on'); }
}

const slate = (id, on) => $(id).classList.toggle('on', on);

/* Wait for the picture to actually show something, with a ceiling so a stall
   cannot hang the recording. */
async function until(fn, timeout = 30000) {
  const t0 = performance.now();
  while (performance.now() - t0 < timeout) {
    try { if (fn()) return true; } catch (e) { /* not ready */ }
    await sleep(80);
  }
  return false;
}

const seen = (sel, re) => {
  const n = document.querySelector(sel);
  return !!n && re.test(n.textContent);
};

/* ---------- the scene ---------- */

const HOUR = '2026-09-28T13:00';
const FROM = '2026-09-28T08:00';

let pending = null;

const BEATS = [
  { id: 'open', hold: 3.6, run: async () => {
      slate('slate-open', true);
      caption('Karachi, 28 September', 'A delivery rider wants to know about this afternoon.');
    } },

  { id: 'ask', hold: 6.0, run: async () => {
      slate('slate-open', false);
      window.heatline.reveal();
      const loaded = await window.heatline.load(HOUR, FROM);
      if (loaded?.day?.body?.counts) window.__demoCounts = loaded.day.body.counts;
      caption('The question', 'They ask the agent, in the words they would actually use.');
      await point('#ask-in', { tap: true });
      await type('#ask-in', 'Can I work at 1pm today?');
      await point('#ask-go', { tap: true });
      window.heatline.ask('Can I work at 1pm today?');
    },
    at: () => seen('#c-adv', /calling tools|cannot|degrees|advisory/i) },

  { id: 'tools', hold: 8.0, zoom: '#chain', scale: 1.5, run: async () => {
      caption('The agent works',
        'It resolves which hour is meant, reads the forecast, and computes the exposure.');
    },
    at: () => seen('#chain', /assess_hour/) },

  { id: 'verdict', hold: 8.0, zoom: '.readings', scale: 1.55, run: async () => {
      caption('Two different numbers',
        'One is the air temperature. The other is the exposure the limit is defined on.');
    },
    at: () => {
      if (!seen('#r-wbgt', /\d/)) return false;
      const num = (id) => ($(id).textContent || '').replace(/[^\d.]/g, '');
      window.__demoFacts = {
        air_c: num('r-air'),
        wbgt_c: num('r-wbgt'),
        limit: ($('r-limit').textContent || '').replace(/\s+/g, ' ').trim(),
        verdict: ($('v-word').textContent || '').trim(),
      };
      return true;
    } },

  { id: 'band', hold: 7.2, zoom: '#c-band', scale: 1.42, run: async () => {
      caption('Against the limit',
        'Blue is exposure. The amber band is the NIOSH limit, and it is a band because the workload is.');
    } },

  { id: 'strip', hold: 5.8, zoom: '#c-strip', scale: 1.45, run: async () => {
      caption('It says when it cannot tell',
        'Inside the band, whether this rider is over depends on how hard they are working.');
      // The second agent answer takes 7 to 20 seconds. Asking for it here, two
      // beats before it is shown, keeps that latency off the camera. The wait
      // is real either way.
      pending = window.heatline.get('/advise?q='
        + encodeURIComponent('What about 2pm on 29 September?'));
    } },

  { id: 'refuse', hold: 7.2, zoom: '#c-verdict', scale: 1.45, run: async () => {
      camera(null);
      caption('A question it will not answer', 'Now they ask about the day after tomorrow.');
      await point('#ask-in', { tap: true });
      await type('#ask-in', 'What about 2pm on 29 September?');
      await point('#ask-go', { tap: true });
      window.heatline.thinking(true, 'calling tools');
      const r = await window.heatline.get('/assess?hour=2026-09-29T14:00');
      window.heatline.paintRefusal(r.body);
      pending.then((a) => {
        window.heatline.thinking(false);
        if (a.status === 200) {
          window.heatline.paintAdvice(a.body.answer, a.body.tools_called);
        }
      });
    },
    at: () => seen('#v-word', /No advice/) },

  { id: 'withheld', hold: 6.2, zoom: '#c-adv', scale: 1.4, run: async () => {
      caption('It declines, in both languages',
        'Past the horizon it answers for, every reading is withheld and the agent says so.');
    },
    at: () => seen('#adv-ur-t', /\S/) },

  { id: 'close', hold: 5.2, run: async () => {
      camera(null);
      $('cur').classList.remove('on');
      slate('slate-close', true);
      caption('Open source, MIT', 'Every formula quoted from its primary document.');
    } },
];

async function play() {
  const t0 = performance.now();
  const marks = [];
  const tick = () => {
    const t = (performance.now() - t0) / 1000;
    $('prog').style.width = `${Math.min(100, (t / window.__demoTotal) * 100)}%`;
    if (!window.__demoDone) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  for (const b of BEATS) {
    const start = (performance.now() - t0) / 1000;
    await b.run();
    if (b.at) await until(b.at);
    if (b.zoom) camera(b.zoom, b.scale);
    // The beat's hold begins once the picture is right, not when it was asked
    // for, so narration written against a beat always lands on its own screen.
    const spent = (performance.now() - t0) / 1000 - start;
    marks.push({ id: b.id, at: +start.toFixed(2), ready: +(start + spent).toFixed(2) });
    await sleep(Math.max(0, b.hold * 1000 - (performance.now() - t0 - start * 1000)));
  }
  caption(null, null);
  window.__demoMarks = marks;
  // The picture is live data. Narration that states a number must take it from
  // here, not from a value someone typed while writing the script, or the voice
  // and the screen will eventually disagree.
  window.__demoFacts = { ...(window.__demoFacts || {}),
                         counts: window.__demoCounts || null };
  window.__demoDone = true;
  window.__demoElapsed = (performance.now() - t0) / 1000;
}

window.__demoTotal = BEATS.reduce((a, b) => a + b.hold, 0);
window.__demoPlay = play;
})();
