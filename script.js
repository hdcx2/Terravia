const sidebar = document.querySelector('.sidebar');
const menuToggle = document.querySelector('.menu-toggle');

if (sidebar && menuToggle) {
  menuToggle.addEventListener('click', () => {
    const expanded = sidebar.classList.toggle('is-expanded');
    menuToggle.setAttribute('aria-expanded', String(expanded));
    menuToggle.setAttribute('aria-label', expanded ? 'Collapse navigation' : 'Expand navigation');
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('is-expanded')) {
      sidebar.classList.remove('is-expanded');
      menuToggle.setAttribute('aria-expanded', 'false');
      menuToggle.setAttribute('aria-label', 'Expand navigation');
      menuToggle.focus();
    }
  });

  document.addEventListener('click', (event) => {
    const compact = window.matchMedia('(max-width: 650px)').matches;
    if (compact && sidebar.classList.contains('is-expanded') && !sidebar.contains(event.target)) {
      sidebar.classList.remove('is-expanded');
      menuToggle.setAttribute('aria-expanded', 'false');
      menuToggle.setAttribute('aria-label', 'Expand navigation');
    }
  });
}

// Base URL of the Terravia chatbot API. Override before this script loads with
//   <script>window.TERRAVIA_API = 'https://your-host';</script>
// Empty string = same origin (when the API also serves the site).
const TERRAVIA_API = (window.TERRAVIA_API || '').replace(/\/$/, '');

const chatForm = document.querySelector('.chat-form');
if (chatForm) {
  const input = chatForm.querySelector('input');
  const sendBtn = chatForm.querySelector('button');
  const messages = document.querySelector('.chat-messages');

  const scrollToEnd = () => { messages.scrollTop = messages.scrollHeight; };

  const addMessage = (text, who) => {
    const el = document.createElement('p');
    el.className = `chat-message ${who === 'user' ? 'user-message' : 'bot-message'}`;
    el.textContent = text;
    el.style.whiteSpace = 'pre-wrap';   // preserve line breaks (CI lists, profiles)
    messages.append(el);
    scrollToEnd();
    return el;
  };

  // Split the API answer into the body and its "Source:" citation so the
  // citation renders as a small muted footnote rather than part of the blob.
  const renderBotAnswer = (el, answer) => {
    const idx = answer.indexOf('Source:');
    const body = idx >= 0 ? answer.slice(0, idx).trim() : answer.trim();
    const source = idx >= 0 ? answer.slice(idx).trim() : '';
    el.classList.remove('is-pending');
    el.textContent = body;
    el.style.whiteSpace = 'pre-wrap';
    if (source) {
      const cite = document.createElement('span');
      cite.className = 'chat-source';
      cite.textContent = source;
      el.append(document.createElement('br'), cite);
    }
    scrollToEnd();
  };

  chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    addMessage(question, 'user');
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;

    const pending = addMessage('Thinking…', 'bot');
    pending.classList.add('is-pending');
    try {
      const res = await fetch(`${TERRAVIA_API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      if (res.status === 422) {
        // Validation error (e.g. question too long): tell the user plainly.
        pending.classList.remove('is-pending');
        pending.textContent =
          'That question is too long. Please shorten it to under 500 characters.';
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderBotAnswer(pending, data.answer);
    } catch (err) {
      pending.classList.remove('is-pending');
      pending.textContent =
        'Sorry, the health data assistant is unavailable right now. Please try again shortly.';
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
      scrollToEnd();
    }
  });
}


/* ---------------------------------------------------------------------------
 * Interactive choropleth map (D3, SVG only — no tiles, no API key, no watermark)
 * Draws MA county polygons from the API and colors them by a chosen condition.
 * ------------------------------------------------------------------------- */
const mapSvgEl = document.getElementById('map-svg');
if (mapSvgEl && window.d3) {
  const svg = d3.select('#map-svg');
  const tooltip = document.getElementById('map-tooltip');
  const legend = document.getElementById('map-legend');
  const caption = document.getElementById('map-caption');
  const selectEl = document.getElementById('map-measure');

  const W = 680, H = 420;
  svg.attr('viewBox', `0 0 ${W} ${H}`).attr('preserveAspectRatio', 'xMidYMid meet');

  let geo = null;

  const colorFor = (v, lo, hi) => {
    // Sequential green ramp (matches the site palette). Guard a flat range.
    const t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
    return d3.interpolate('#eaf2e9', '#2f6b47')(t);
  };

  const drawLegend = (lo, hi) => {
    legend.innerHTML =
      `<span class="map-legend-label">${lo.toFixed(1)}%</span>` +
      '<span class="map-legend-bar"></span>' +
      `<span class="map-legend-label">${hi.toFixed(1)}%</span>`;
  };

  const showTip = (evt, county, d) => {
    tooltip.hidden = false;
    tooltip.innerHTML =
      `<strong>${county}</strong><br>${d.label}: ${d.value.toFixed(1)}%` +
      `<br><span class="map-tip-ci">95% CI ${d.low.toFixed(1)}–${d.high.toFixed(1)}</span>`;
    const r = mapSvgEl.getBoundingClientRect();
    tooltip.style.left = `${evt.clientX - r.left + 12}px`;
    tooltip.style.top = `${evt.clientY - r.top + 12}px`;
  };
  const hideTip = () => { tooltip.hidden = true; };

  const render = async (measureid) => {
    try {
      const res = await fetch(`${TERRAVIA_API}/measures/${measureid}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const byId = new Map(data.rows.map((r) => [String(r.locationid), r]));

      const projection = d3.geoMercator().fitSize([W, H], geo);
      const path = d3.geoPath(projection);

      const counties = svg.selectAll('path.county').data(geo.features, (f) => f.properties.locationid);
      counties.join(
        (enter) => enter.append('path').attr('class', 'county').attr('d', path),
        (update) => update,
      )
        .attr('d', path)
        .attr('fill', (f) => {
          const row = byId.get(String(f.properties.locationid));
          return row ? colorFor(row.value, data.min, data.max) : '#e6e8e4';
        })
        .attr('stroke', '#ffffff')
        .attr('stroke-width', 0.8)
        .style('cursor', 'pointer')
        .on('mousemove', (evt, f) => {
          const row = byId.get(String(f.properties.locationid));
          if (row) showTip(evt, row.county, { ...row, label: data.label });
        })
        .on('mouseleave', hideTip);

      drawLegend(data.min, data.max);
      caption.textContent =
        `${data.label} — ${data.source}, ${data.data_year}. Shades run county low to high; values are model-based estimates.`;
    } catch (err) {
      caption.textContent = 'Map data is unavailable right now.';
    }
  };

  const init = async () => {
    try {
      const [gj, ms] = await Promise.all([
        fetch(`${TERRAVIA_API}/geojson`).then((r) => r.json()),
        fetch(`${TERRAVIA_API}/measures`).then((r) => r.json()),
      ]);
      geo = gj;
      selectEl.innerHTML = ms.measures
        .map((m) => `<option value="${m.id}">${m.label}</option>`)
        .join('');
      selectEl.addEventListener('change', () => render(selectEl.value));
      await render(ms.measures[0].id);
    } catch (err) {
      caption.textContent = 'Map is unavailable right now.';
    }
  };

  init();
}
