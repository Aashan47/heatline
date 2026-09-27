/* heatline UI.
   Reads the same endpoints anyone can curl. No number is computed here: the
   browser formats what the service already decided. */

const $ = (id) => document.getElementById(id);

const ICON = {
  under: '<svg viewBox="0 0 24 24"><path d="M20 6.5 9.6 17 4 11.4"/></svg>',
  undetermined: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/>'
    + '<path d="M9.2 9.3a2.9 2.9 0 1 1 4 2.7c-.8.4-1.2 1-1.2 1.9v.4"/>'
    + '<path d="M12 17.8h.01"/></svg>',
  over: '<svg viewBox="0 0 24 24"><path d="M12 3.6 2.6 19.4h18.8L12 3.6z"/>'
    + '<path d="M12 9.6v4.2"/><path d="M12 17h.01"/></svg>',
};

const WORD = { under: 'Under', undetermined: 'Cannot tell', over: 'Over' };

const SUB = {
  under: (a) => `Exposure is ${fmt(a.wbgt_c)} degrees WBGT, below the limit for every `
    + `effort level in the moderate band. Air temperature is ${fmt(a.air_c)}.`,
  undetermined: (a) => `Exposure is ${fmt(a.wbgt_c)} degrees WBGT, inside the limit band `
    + `of ${fmt(a.limit_c[0])} to ${fmt(a.limit_c[1])}. Whether this rider is over `
    + `depends on how hard they are working, and a forecast cannot know that.`,
  over: (a) => `Exposure is ${fmt(a.wbgt_c)} degrees WBGT, above the limit for every `
    + `effort level in the moderate band. Air temperature is only ${fmt(a.air_c)}.`,
};

const fmt = (n) => (n === null || n === undefined ? '--' : Number(n).toFixed(1));

async function get(path) {
  const r = await fetch(path);
  return { status: r.status, body: await r.json() };
}

/* ---------- verdict ---------- */

function paintVerdict(a) {
  const el = $('verdict');
  el.className = 'verdict is-' + (a.verdict === 'undetermined' ? 'undet' : a.verdict);
  $('v-mark').innerHTML = ICON[a.verdict];
  $('v-word').textContent = WORD[a.verdict];
  $('v-sub').textContent = SUB[a.verdict](a);
  $('r-air').innerHTML = fmt(a.air_c) + '<em>&deg;C</em>';
  $('r-wbgt').innerHTML = fmt(a.wbgt_c) + '<em>&deg;C</em>';
  $('r-limit').innerHTML = fmt(a.limit_c[0]) + '<em>to</em>' + fmt(a.limit_c[1])
    + '<em>&deg;C</em>';
}

function paintRefusal(body) {
  const el = $('verdict');
  el.className = 'verdict is-over';
  $('v-mark').innerHTML = ICON.over;
  $('v-word').textContent = 'No advice';
  $('v-sub').textContent = body.reason;
  for (const id of ['r-air', 'r-wbgt', 'r-limit']) {
    $(id).innerHTML = '<em style="margin:0">withheld</em>';
  }
  $('c-verdict').classList.add('refusal');
}

/* ---------- band chart ---------- */

function drawChart(hours, limit) {
  const svg = $('chart');
  const W = 860, H = 210, PL = 44, PR = 14, PT = 14, PB = 26;
  const vals = hours.flatMap((h) => [h.wbgt_c, h.air_c]);
  const lo = Math.floor(Math.min(...vals, limit[0]) - 1.2);
  const hi = Math.ceil(Math.max(...vals, limit[1]) + 1.2);
  const x = (i) => PL + (i / Math.max(1, hours.length - 1)) * (W - PL - PR);
  const y = (v) => PT + (1 - (v - lo) / (hi - lo)) * (H - PT - PB);

  const path = (key) => hours.map((h, i) =>
    `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(h[key]).toFixed(1)}`).join(' ');

  const gridY = [];
  for (let v = lo; v <= hi; v += 2) {
    gridY.push(`<line x1="${PL}" x2="${W - PR}" y1="${y(v)}" y2="${y(v)}"
        stroke="var(--border)" stroke-width="1"/>
      <text x="${PL - 9}" y="${y(v) + 4}" text-anchor="end"
        font-family="Fira Code" font-size="11" fill="var(--text-3)">${v}</text>`);
  }

  const ticks = hours.map((h, i) => (i % 3 === 0
    ? `<text x="${x(i)}" y="${H - 7}" text-anchor="middle"
         font-family="Fira Code" font-size="11" fill="var(--text-3)">${h.time.slice(11, 16)}</text>`
    : '')).join('');

  const crossings = hours.map((h, i) => (h.verdict === 'over'
    ? `<circle cx="${x(i)}" cy="${y(h.wbgt_c)}" r="4.5" fill="var(--over)"
         stroke="var(--bg)" stroke-width="2"/>` : '')).join('');

  svg.innerHTML = `
    <defs>
      <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--data)" stop-opacity=".26"/>
        <stop offset="100%" stop-color="var(--data)" stop-opacity="0"/>
      </linearGradient>
    </defs>
    ${gridY.join('')}
    <rect x="${PL}" y="${y(limit[1])}" width="${W - PL - PR}"
          height="${Math.max(1, y(limit[0]) - y(limit[1]))}"
          fill="var(--undet)" fill-opacity=".14"
          stroke="var(--undet)" stroke-opacity=".45" stroke-width="1"
          stroke-dasharray="4 3"/>
    <text x="${W - PR - 6}" y="${y(limit[1]) - 6}" text-anchor="end"
          font-family="Fira Sans" font-size="11.5" font-weight="600"
          fill="var(--undet)">NIOSH limit band</text>
    <path d="${path('air_c')}" fill="none" stroke="var(--text-3)"
          stroke-width="1.6" stroke-dasharray="5 4"/>
    <path d="${path('wbgt_c')} L${x(hours.length - 1)} ${y(lo)} L${x(0)} ${y(lo)} Z"
          fill="url(#fade)" stroke="none"/>
    <path id="exposure" d="${path('wbgt_c')}" fill="none" stroke="var(--data)"
          stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>
    ${crossings}
    ${ticks}`;

  const line = svg.querySelector('#exposure');
  const len = line.getTotalLength();
  line.style.strokeDasharray = len;
  line.style.strokeDashoffset = len;
  line.getBoundingClientRect();
  line.style.transition = 'stroke-dashoffset 1.15s cubic-bezier(.22,.61,.36,1)';
  line.style.strokeDashoffset = 0;
}

/* ---------- hour strip ---------- */

function drawStrip(hours, limit) {
  const max = Math.max(...hours.map((h) => h.wbgt_c), limit[1]) + 1;
  const min = Math.min(...hours.map((h) => h.wbgt_c), limit[0]) - 2;
  $('strip').innerHTML = hours.map((h) => {
    const pct = Math.round(((h.wbgt_c - min) / (max - min)) * 100);
    return `<div class="hrow" data-v="${h.verdict}">
      <div class="t">${h.time.slice(11, 16)}</div>
      <div class="hbar"><i style="width:${pct}%;transform:scaleX(0)"></i></div>
      <div class="v">${WORD[h.verdict]}</div>
    </div>`;
  }).join('');
  requestAnimationFrame(() => {
    $('strip').querySelectorAll('.hbar i').forEach((bar, i) => {
      bar.style.transition = `transform .5s ${0.035 * i}s cubic-bezier(.22,.61,.36,1)`;
      bar.style.transform = 'scaleX(1)';
    });
  });
}

/* ---------- advisory ---------- */

function paintAdvice(text, chain) {
  const lines = String(text).split('\n').map((s) => s.trim()).filter(Boolean);
  const ur = lines.filter((l) => /[؀-ۿ]/.test(l)).join(' ');
  const en = lines.filter((l) => !/[؀-ۿ]/.test(l)).join(' ');
  $('adv-en-t').textContent = en || text;
  $('adv-ur-t').textContent = ur;
  $('adv-ur').style.display = ur ? '' : 'none';
  $('chain').innerHTML = (chain || []).map((c, i) =>
    (i ? '<span>&rarr;</span>' : '') + `<code>${c}</code>`).join('');
}

/* ---------- freshness ---------- */

function paintFreshness(s) {
  const dot = $('freshness').querySelector('i');
  if (!s.ok) {
    dot.style.background = 'var(--over)';
    $('fresh-txt').textContent = 'stale';
    return;
  }
  dot.style.background = 'var(--under)';
  const m = s.fetch_age_minutes;
  $('fresh-txt').textContent = m < 1 ? 'live' : `${Math.round(m)} min old`;
}

/* ---------- boot ---------- */

function reveal() {
  document.querySelectorAll('.rise').forEach((el, i) => {
    setTimeout(() => el.classList.add('in'), 70 * i);
  });
}

async function load(hour, fromHour) {
  const status = await get('/status');
  paintFreshness(status.body);

  const one = await get('/assess' + (hour ? `?hour=${encodeURIComponent(hour)}` : ''));
  if (one.status === 409) {
    paintRefusal(one.body);
  } else {
    paintVerdict(one.body);
    $('c-verdict').classList.remove('refusal');
  }

  const q = new URLSearchParams({ hours: '11' });
  if (fromHour) q.set('from_hour', fromHour);
  const day = await get('/day?' + q);
  if (day.status === 200) {
    drawChart(day.body.hours, day.body.hours[0].limit_c);
    drawStrip(day.body.hours, day.body.hours[0].limit_c);
  }
  return { one, day };
}

window.heatline = { load, paintAdvice, paintRefusal, paintVerdict, get, reveal,
                    drawChart, drawStrip };

if (!location.search.includes('demo=1')) {
  reveal();
  load().then(async () => {
    const a = await get('/advise?q=' + encodeURIComponent('Should I take orders right now?'));
    if (a.status === 200) paintAdvice(a.body.answer, a.body.tools_called);
    else $('adv-en-t').textContent = 'The model is unavailable. The numbers above do not depend on it.';
  });
}
