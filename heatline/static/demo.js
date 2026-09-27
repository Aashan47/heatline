/* The demo tour.
   It drives the real dashboard against the real endpoints. Nothing is mocked:
   every number that appears came from the service, and the refusal scene is the
   service actually returning 409.

   Timings are declared once, in SCENES, so the narration, the captions and the
   recorder all agree on the same clock. */

const stage = document.createElement('div');
stage.className = 'stage';
stage.innerHTML = `
  <div class="slate" id="slate-open">
    <h1>31 degrees is not a<br>safe afternoon in <span class="hl">Karachi</span></h1>
    <p>Six hours of it were over the occupational heat limit for a delivery rider.</p>
  </div>
  <div class="slate" id="slate-limits">
    <h1>What it does not do</h1>
    <ul>
      <li>more than one city, one worker group</li>
      <li>measure the street; a forecast is a grid cell</li>
      <li>give medical advice</li>
      <li>ship reviewed Urdu</li>
      <li>know your own metabolic rate</li>
    </ul>
  </div>
  <div class="slate" id="slate-close">
    <h1>Every number has a<br>primary source</h1>
    <p>WBGT by Liljegren via ECMWF thermofeel. Limits from NIOSH 2016-106.</p>
    <div class="repo">github.com/Aashan47/heatline</div>
    <div class="foot">Built with Gemini and the Agent Development Kit.
      Weather data by Open-Meteo.com, CC BY 4.0.</div>
  </div>
  <div class="spot" id="spot"></div>
  <div class="cap" id="cap"><div class="kicker" id="cap-k"></div>
    <div class="line" id="cap-l"></div></div>
  <div class="prog" id="prog"></div>`;
document.body.appendChild(stage);

const el = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function caption(kicker, line) {
  const c = el('cap');
  if (!line) { c.classList.remove('on'); return; }
  const swap = () => { el('cap-k').textContent = kicker; el('cap-l').textContent = line; };
  if (c.classList.contains('on')) {
    c.classList.remove('on');
    setTimeout(() => { swap(); c.classList.add('on'); }, 260);
  } else { swap(); c.classList.add('on'); }
}

function slate(id, on) { el(id).classList.toggle('on', on); }

function spotlight(sel) {
  const s = el('spot');
  if (!sel) { s.classList.remove('on'); return; }
  const t = document.querySelector(sel);
  if (!t) { s.classList.remove('on'); return; }
  const r = t.getBoundingClientRect();
  const pad = 12;
  s.style.top = `${r.top - pad}px`;
  s.style.left = `${r.left - pad}px`;
  s.style.width = `${r.width + pad * 2}px`;
  s.style.height = `${r.height + pad * 2}px`;
  s.classList.add('on');
}

/* The window the demo shows: a real daytime shift, where the interesting
   things happen. At night every hour is correctly and uninterestingly under. */
const HOUR = '2026-09-28T12:00';
const FROM = '2026-09-28T08:00';
const PAST_HORIZON = '2026-09-29T14:00';

/* The agent takes around ten seconds to answer, which is longer than the scene
   that shows it. So the request is started early, during the refusal scene, and
   the result is painted when its own scene arrives. The latency is real either
   way; this only stops the camera watching a spinner. */
let advicePromise = null;

const SCENES = [
  { at: 0.0, dur: 6.0, run: async () => {
      slate('slate-open', true);
      caption('Karachi, 27 September 2026', 'Air temperature peaked at 31.3 degrees.');
    } },

  { at: 6.0, dur: 6.5, run: async () => {
      slate('slate-open', false);
      document.body.classList.add('demo');
      caption('The gap', 'Nobody issues a warning about 31 degrees.');
      window.heatline.reveal();
      await window.heatline.load(HOUR, FROM);
    } },

  { at: 12.5, dur: 7.5, run: async () => {
      spotlight('.readings');
      caption('Two different numbers',
        'The thermometer says 30.8. The exposure index says 29.7, and that is the '
        + 'one the limit is defined on.');
    } },

  { at: 20.0, dur: 8.0, run: async () => {
      spotlight('#c-band');
      caption('Crossing the limit',
        'The blue line is exposure. The amber band is the NIOSH limit. At noon it '
        + 'is inside it.');
    } },

  { at: 28.0, dur: 8.0, run: async () => {
      spotlight('.readings .reading:last-child');
      caption('Why the limit is a band',
        'NIOSH says metabolic rate estimates can be thirty percent out, so the '
        + 'limit spans two full degrees.');
    } },

  { at: 36.0, dur: 9.0, run: async () => {
      // Fire the agent request here, not in the scene that displays it. The
      // observed latency runs from 7 to 20 seconds, and a scene that begins
      // 10 seconds later sometimes filmed a spinner. The wait is still real;
      // this only stops the camera watching it.
      advicePromise = window.heatline.get('/advise?q='
        + encodeURIComponent('What about 2pm on 29 September?'));
      spotlight('#c-strip');
      caption('The third answer',
        'Seven of these hours it will not call either way. Inside the band, whether '
        + 'this rider is over depends on how hard they are working.');
    } },

  { at: 45.0, dur: 10.0, run: async () => {
      spotlight(null);
      caption('It refuses', 'Ask about an hour past the horizon it will answer for, '
        + 'and it declines. HTTP 409, and no numbers at all.');
      const r = await window.heatline.get(
        '/assess?hour=' + encodeURIComponent(PAST_HORIZON));
      window.heatline.paintRefusal(r.body);
      window.heatline.paintAdvice('Asking the agent the same question.', []);
    } },

  { at: 55.0, dur: 11.0, run: async () => {
      spotlight('#c-adv');
      caption('The refusal survives the model',
        'Put to the Gemini agent, it relays the refusal in English and Urdu, with '
        + 'not one number in it.');
      const a = await (advicePromise || window.heatline.get('/advise?q='
        + encodeURIComponent('What about 2pm on 29 September?')));
      if (a.status === 200) {
        window.heatline.paintAdvice(a.body.answer, a.body.tools_called);
      } else {
        window.heatline.paintAdvice(
          'The model is unavailable. The refusal above did not depend on it.', []);
      }
    } },

  { at: 66.0, dur: 9.0, run: async () => {
      spotlight(null);
      slate('slate-limits', true);
      caption('Said out loud', 'One city, one worker group, and no reviewed Urdu.');
    } },

  { at: 75.0, dur: 9.0, run: async () => {
      slate('slate-limits', false);
      slate('slate-close', true);
      caption('Open source, MIT',
        'Every formula quoted from its primary document, with a URL.');
    } },
];

const TOTAL = 84.0;

async function play() {
  const started = performance.now();
  const tick = () => {
    const t = (performance.now() - started) / 1000;
    el('prog').style.width = `${Math.min(100, (t / TOTAL) * 100)}%`;
    if (t < TOTAL) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  for (const s of SCENES) {
    const wait = s.at * 1000 - (performance.now() - started);
    if (wait > 0) await sleep(wait);
    try { await s.run(); } catch (e) { console.error('scene failed', s.at, e); }
  }
  await sleep(Math.max(0, TOTAL * 1000 - (performance.now() - started)));
  caption(null, null);
  window.__demoDone = true;
}

window.__demoPlay = play;
window.__demoTotal = TOTAL;
