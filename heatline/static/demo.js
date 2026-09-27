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
  <!-- No figure on the slate. It read "31 degrees" while the take that
       followed showed 30.5 for a different day, and the opening card is
       drawn before any data has loaded, so it cannot honestly carry one. -->
  <div class="slate" id="slate-open">
    <h1>The number your weather app shows you<br>is not the number that
      <span class="hl">hurts you</span></h1>
    <p>Occupational heat exposure, for one delivery rider in Karachi.</p>
  </div>
  <div class="slate" id="slate-close">
    <h1>Open it on your phone</h1>
    <div class="repo big">heat.aashanjaved.com</div>
    <p>Every formula quoted from its primary document. WBGT by Liljegren via
      ECMWF thermofeel, limits from NIOSH 2016-106.</p>
    <div class="foot">Code at github.com/Aashan47/heatline &nbsp;&middot;&nbsp;
      Built with Gemini and the Agent Development Kit &nbsp;&middot;&nbsp;
      Weather data by Open-Meteo.com, CC BY 4.0</div>
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

  // Layout geometry, not rendered geometry. getBoundingClientRect returns the
  // box *after* transforms, so reading it here measured the previous beat's
  // own zoom and fed it back in. Every framing after the first zoom was
  // computed from the wrong numbers.
  let x = 0;
  let y = 0;
  for (let n = node; n && n !== win; n = n.offsetParent) {
    x += n.offsetLeft;
    y += n.offsetTop;
  }
  const cx = (x + node.offsetWidth / 2) - win.offsetWidth / 2;
  const cy = (y + node.offsetHeight / 2) - win.offsetHeight / 2;

  // Centring a card in the right hand column pushed the window far enough
  // left that the last third of the frame was bare background. So pan, but
  // not past the window's own edges: the shot stays inside the product.
  const slack = (span, view) => Math.max(0, (span * scale - view) / (2 * scale));
  const clamp = (v, m) => Math.max(-m, Math.min(m, v));
  const tx = clamp(-cx / scale, slack(win.offsetWidth, window.innerWidth));
  const ty = clamp(-cy / scale, slack(win.offsetHeight, window.innerHeight));
  win.style.transform = `scale(${scale}) translate(${tx}px, ${ty}px)`;
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
async function until(what, fn, timeout = 25000) {
  // A predicate that never comes true used to return false and let the scene
  // carry on. That shipped: the agent was rate limited, the tool chain never
  // appeared, this gave up after eight seconds, and the caption "the agent
  // works" then played over a quota notice for twenty seconds. A beat whose
  // picture never arrived is a broken take, so say so and stop.
  const t0 = performance.now();
  while (performance.now() - t0 < timeout) {
    try { if (fn()) return true; } catch (e) { /* not ready */ }
    await sleep(80);
  }
  throw new Error(
    `beat "${what}" waited ${(timeout / 1000).toFixed(0)}s and its picture `
    + 'never arrived, so the take is broken');
}

const seen = (sel, re) => {
  const n = document.querySelector(sel);
  if (!n) return false;
  // An input's textContent is always empty: what the visitor typed is in
  // value. This read textContent only, so the beat that waits for the typed
  // question could never be satisfied, and only the old eight second shrug in
  // until() hid it.
  const text = ('value' in n && n.tagName !== 'DIV') ? n.value : n.textContent;
  return re.test(text || '');
};

/* ---------- the scene ---------- */

const HOUR = '2026-09-28T13:00';
const FROM = '2026-09-28T08:00';

let pending = null;

const BEATS = [
  { id: 'open', window: 5.8, run: async () => {
      slate('slate-open', true);
      caption('Karachi, 28 September', 'A delivery rider wants to know about this afternoon.');
    } },

  { id: 'ask', window: 14.3, run: async () => {
      slate('slate-open', false);
      window.heatline.reveal();
      const loaded = await window.heatline.load(HOUR, FROM);
      if (loaded?.day?.body?.counts) window.__demoCounts = loaded.day.body.counts;
      caption('The question', 'They ask the agent, in the words they would actually use.');
      await point('#ask-in', { tap: true });
      // Name the date. Asking about "1pm today" put the agent on a different
      // hour from the one the dashboard is pinned to, so the answer quoted
      // 31.3 and 30.4 beside a card reading 30.5 and 29.4. Two sets of
      // numbers on one screen is a viewer's problem even when both are right.
      await type('#ask-in', 'Can I work at 1pm on 28 September?');
      await point('#ask-go', { tap: true });
      window.heatline.ask('Can I work at 1pm on 28 September?');
      // The second half of this beat is narrated as what the agent is doing,
      // so the caption has to change with it. Fired on a timer because run()
      // returns before the beat's window is up.
      setTimeout(() => caption('The agent works',
        'It resolves the hour, reads the forecast, and computes the exposure.'),
        4800);
    },
    at: () => seen('#ask-in', /28 September/) },

  { id: 'verdict', window: 13.6, zoom: '.readings', scale: 1.5, run: async () => {
      // tools and verdict used to be two beats. Their pictures arrive together,
      // so the first was left with under a second of room and its line ran into
      // the second. One moment, one beat.
      caption('The number the limit is set against',
        'The thermometer is not what decides this. The exposure index is.');
    },
    at: () => {
      if (!seen('#chain', /assess_hour/) || !seen('#r-wbgt', /\d/)) return false;
      const num = (id) => ($(id).textContent || '').replace(/[^\d.]/g, '');
      window.__demoFacts = {
        air_c: num('r-air'),
        wbgt_c: num('r-wbgt'),
        limit: ($('r-limit').textContent || '').replace(/\s+/g, ' ').trim(),
        verdict: ($('v-word').textContent || '').trim(),
      };
      return true;
    } },

  { id: 'band', window: 11.9, zoom: '#c-band', scale: 1.42, run: async () => {
      caption('Against the limit',
        'Blue is exposure. The amber band is the NIOSH limit, which depends '
        + 'on how hard the work is.');
    } },

  { id: 'strip', window: 12.7, zoom: '#c-strip', scale: 1.45, run: async () => {
      caption('It says when it cannot tell',
        'Inside the band, whether this rider is over depends on how hard they are working.');
      // The second agent answer takes 7 to 20 seconds. Asking for it here, two
      // beats before it is shown, keeps that latency off the camera. The wait
      // is real either way.
      pending = window.heatline.get('/advise?q='
        + encodeURIComponent('What about 2pm on 29 September?'));
    } },

  { id: 'refuse', window: 5.8, zoom: '#c-verdict', scale: 1.45, run: async () => {
      camera(null);
      caption('A question it will not answer',
        'Now they ask about an hour further out than it will answer for.');
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

  { id: 'withheld', window: 6.2, zoom: '#c-adv', scale: 1.4, run: async () => {
      caption('It declines, in both languages',
        'Past the horizon it answers for, every reading is withheld and the agent says so.');
    },
    at: () => seen('#adv-ur-t', /\S/) },

  { id: 'close', window: 6.9, run: async () => {
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
    try {
      await b.run();
      if (b.at) await until(b.id, b.at);
    } catch (err) {
      // Surface it and stop. The recorder reads this and refuses to write a
      // file, rather than leaving a take that looks fine until someone
      // watches it.
      window.__demoError = String(err && err.message ? err.message : err);
      window.__demoDone = true;
      window.__demoElapsed = (performance.now() - t0) / 1000;
      throw err;
    }
    if (b.zoom) camera(b.zoom, b.scale);
    const ready = (performance.now() - t0) / 1000;
    marks.push({ id: b.id, at: +start.toFixed(2), ready: +ready.toFixed(2) });

    // A window from the beat's own start, not a hold after its picture
    // arrives. Narration is written against these windows, so the timeline
    // has to be the same whether the agent answered in half a second or in
    // eight, and holding *after* the wait made the whole film stretch by
    // however long the model took. If the beat has already overrun its own
    // window there is no time left for its lines, which is a broken take.
    const left = b.window - ((performance.now() - t0) / 1000 - start);
    if (left < -0.2) {
      throw new Error(
        `beat "${b.id}" took ${(b.window - left).toFixed(1)}s of its `
        + `${b.window.toFixed(1)}s window, so its narration has nowhere to go`);
    }
    if (left > 0) await sleep(left * 1000);
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

window.__demoTotal = BEATS.reduce((a, b) => a + b.window, 0);
window.__demoPlay = play;
})();
