const sidebar = document.querySelector('.sidebar');
const menuToggle = document.querySelector('.menu-toggle');

if (sidebar && menuToggle) {
  const SIDEBAR_KEY = 'terravia-sidebar-expanded';

  // Keep the button's state in sync and (optionally) remember it so the
  // sidebar stays open across page/tab navigation until the user collapses it.
  const applyExpanded = (expanded, persist = true) => {
    sidebar.classList.toggle('is-expanded', expanded);
    menuToggle.setAttribute('aria-expanded', String(expanded));
    menuToggle.setAttribute('aria-label', expanded ? 'Collapse navigation' : 'Expand navigation');
    if (persist) {
      try {
        localStorage.setItem(SIDEBAR_KEY, expanded ? '1' : '0');
      } catch (err) {
        /* storage unavailable (private mode): state just won't persist */
      }
    }
  };

  // Restore the remembered state on load. Skip persisting on compact screens so
  // the sidebar never starts open as an overlay on small viewports.
  let remembered = false;
  try {
    remembered = localStorage.getItem(SIDEBAR_KEY) === '1';
  } catch (err) {
    /* storage unavailable: default to collapsed */
  }
  const startCompact = window.matchMedia('(max-width: 650px)').matches;
  if (remembered && !startCompact) {
    applyExpanded(true, false);
  }

  menuToggle.addEventListener('click', () => {
    applyExpanded(!sidebar.classList.contains('is-expanded'));
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('is-expanded')) {
      applyExpanded(false);
      menuToggle.focus();
    }
  });

  document.addEventListener('click', (event) => {
    const compact = window.matchMedia('(max-width: 650px)').matches;
    if (compact && sidebar.classList.contains('is-expanded') && !sidebar.contains(event.target)) {
      applyExpanded(false);
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

  const starters = document.getElementById('chat-starters');
  const missionGrid = document.getElementById('mission-grid');
  const MISSION_KEY = 'terravia-field-guide-v1';
  let exploredMissions = [];
  try {
    exploredMissions = JSON.parse(localStorage.getItem(MISSION_KEY) || '[]');
    if (!Array.isArray(exploredMissions)) exploredMissions = [];
    exploredMissions = exploredMissions.filter((id) => ['diabetes', 'access', 'data'].includes(id));
  } catch (err) {
    exploredMissions = [];
  }

  const renderMissionProgress = () => {
    if (!missionGrid) return;
    missionGrid.querySelectorAll('[data-mission]').forEach((card) => {
      card.classList.toggle('is-complete', exploredMissions.includes(card.dataset.mission));
    });
    const count = document.getElementById('mission-count');
    if (count) count.textContent = `${exploredMissions.length} of 3`;
  };
  const completeMission = (id) => {
    if (!id || exploredMissions.includes(id)) return;
    exploredMissions.push(id);
    try { localStorage.setItem(MISSION_KEY, JSON.stringify(exploredMissions)); } catch (err) { /* progress stays for this visit */ }
    renderMissionProgress();
  };
  renderMissionProgress();

  const ask = async (question, missionId = null) => {
    question = (question || '').trim();
    if (!question) return;

    if (starters) starters.hidden = true;   // hide examples once chatting
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
      completeMission(missionId);
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
  };

  chatForm.addEventListener('submit', (event) => {
    event.preventDefault();
    ask(input.value);
  });

  // Clickable example questions so users know what they can ask.
  if (starters) {
    starters.querySelectorAll('.chat-starter').forEach((btn) => {
      btn.addEventListener('click', () => ask(btn.textContent));
    });
  }

  if (missionGrid) {
    missionGrid.querySelectorAll('.mission-action').forEach((btn) => {
      btn.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('terravia:mission', { detail: { measure: btn.dataset.measure } }));
        ask(btn.dataset.question, btn.closest('[data-mission]').dataset.mission);
      });
    });
  }
}


/* ---------------------------------------------------------------------------
 * Interactive choropleth map (D3, SVG only: no tiles, no API key, no watermark)
 * Draws MA county polygons from the API and colors them by a chosen condition.
 * ------------------------------------------------------------------------- */
function initTerraviaMap() {
  const mapSvgEl = document.getElementById('map-svg');
  if (!mapSvgEl) return;
  const caption = document.getElementById('map-caption');
  const tooltip = document.getElementById('map-tooltip');
  const legend = document.getElementById('map-legend');
  const selectEl = document.getElementById('map-measure');
  const selectionCopy = document.getElementById('map-selection-copy');
  const askCounty = document.getElementById('map-ask-county');

  const W = 680, H = 420;
  const NS = 'http://www.w3.org/2000/svg';
  mapSvgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
  mapSvgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');

  let geo = null;
  let currentRows = new Map();
  let currentLabel = '';
  let selectedCounty = null;
  let pendingMeasure = null;
  let offlineMeasures = new Map();
  const gamePanel = document.getElementById('map-game');
  const gamePrompt = document.getElementById('game-prompt');
  const gameScore = document.querySelector('#game-score strong');
  const gameBest = document.getElementById('game-best');
  const gameButton = document.getElementById('game-button');
  const gameFeedback = document.getElementById('game-feedback');
  const gameRounds = document.getElementById('game-rounds');
  const GAME_BEST_KEY = 'terravia-map-scout-best-v1';
  let challengeActive = false;
  let challengeAwaitingPick = false;
  let challengeRounds = 0;
  let challengePoints = 0;
  let challengeMeasure = null;
  let challengeLoading = false;
  let availableMeasures = [];
  let personalBest = 0;
  try { personalBest = Number(localStorage.getItem(GAME_BEST_KEY)) || 0; } catch (err) { /* best score is optional */ }
  if (gameBest) gameBest.textContent = `Personal best: ${personalBest}`;

  const updateRoundProgress = () => {
    if (!gameRounds) return;
    gameRounds.querySelectorAll('li').forEach((step, index) => {
      const complete = index < challengeRounds;
      const current = challengeActive && (challengeAwaitingPick || challengeLoading) && index === challengeRounds;
      step.classList.toggle('is-complete', complete);
      step.classList.toggle('is-current', current);
      step.setAttribute('aria-current', current ? 'step' : 'false');
    });
  };

  const colorFor = (v, lo, hi) => {
    const t = Math.max(0, Math.min(1, hi > lo ? (v - lo) / (hi - lo) : 0.5));
    const start = [234, 242, 233], end = [47, 107, 71];
    return `rgb(${start.map((value, i) => Math.round(value + (end[i] - value) * t)).join(',')})`;
  };

  const parseCsv = (text) => {
    const records = [];
    let row = [], cell = '', quoted = false;
    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      if (quoted && char === '"' && text[i + 1] === '"') { cell += '"'; i += 1; }
      else if (char === '"') quoted = !quoted;
      else if (char === ',' && !quoted) { row.push(cell); cell = ''; }
      else if ((char === '\n' || char === '\r') && !quoted) {
        if (char === '\r' && text[i + 1] === '\n') i += 1;
        row.push(cell); records.push(row); row = []; cell = '';
      } else cell += char;
    }
    if (cell || row.length) { row.push(cell); records.push(row); }
    const [headers, ...lines] = records;
    return lines.filter((line) => line.length === headers.length).map((line) =>
      Object.fromEntries(headers.map((header, i) => [header, line[i]])));
  };

  const loadOfflineSnapshot = async () => {
    const [geometryResponse, csvResponse] = await Promise.all([
      fetch('data/ma_counties.geojson'),
      fetch('data/snapshot_places_ma.csv'),
    ]);
    if (!geometryResponse.ok || !csvResponse.ok) throw new Error('Local map snapshot is unavailable.');
    const [geometry, csv] = await Promise.all([geometryResponse.json(), csvResponse.text()]);
    const sourceRows = parseCsv(csv).filter((row) => row.measure_kind === 'condition');
    const labels = {
      DIABETES: 'Diabetes', CASTHMA: 'Current asthma', BPHIGH: 'High blood pressure',
      COPD: 'COPD', OBESITY: 'Obesity', MHLTH: 'Frequent mental distress', CSMOKING: 'Current smoking',
    };
    const measures = Array.from(new Set(sourceRows.map((row) => row.measureid))).map((id) => ({ id, label: labels[id] || id }));
    const rowsByMeasure = new Map();
    sourceRows.forEach((row) => {
      if (!rowsByMeasure.has(row.measureid)) rowsByMeasure.set(row.measureid, []);
      rowsByMeasure.get(row.measureid).push({
        locationid: row.locationid, county: row.locationname, value: Number(row.data_value),
        low: Number(row.low_ci), high: Number(row.high_ci), population: Number(row.total_population),
      });
    });
    offlineMeasures = new Map(Array.from(rowsByMeasure, ([id, rows]) => [id, {
      measureid: id, label: labels[id] || id, source: 'CDC PLACES snapshot', data_year: 2023,
      min: Math.min(...rows.map((row) => row.value)), max: Math.max(...rows.map((row) => row.value)), rows,
    }]));
    return { geometry, measures };
  };

  const drawLegend = (lo, hi) => {
    legend.innerHTML =
      `<span class="map-legend-label">${lo.toFixed(1)}%</span>` +
      '<span class="map-legend-bar"></span>' +
      `<span class="map-legend-label">${hi.toFixed(1)}%</span>`;
  };

  const showTip = (evt, county, d) => {
    tooltip.hidden = false;
    tooltip.textContent = `${county} · ${d.label}: ${d.value.toFixed(1)}% (95% CI ${d.low.toFixed(1)}–${d.high.toFixed(1)})`;
    const r = mapSvgEl.getBoundingClientRect();
    const x = evt.clientX ?? r.left + r.width / 2;
    const y = evt.clientY ?? r.top + r.height / 2;
    tooltip.style.left = `${Math.max(4, Math.min(r.width - 240, x - r.left + 10))}px`;
    tooltip.style.top = `${Math.max(4, Math.min(r.height - 56, y - r.top + 10))}px`;
  };
  const hideTip = () => { tooltip.hidden = true; };

  const coordinatesOf = (geometry) => {
    if (!geometry) return [];
    const nested = geometry.coordinates;
    const result = [];
    const visit = (value) => {
      if (Array.isArray(value) && typeof value[0] === 'number') result.push(value);
      else if (Array.isArray(value)) value.forEach(visit);
    };
    visit(nested);
    return result;
  };

  const makeProjection = () => {
    const all = geo.features.flatMap((f) => coordinatesOf(f.geometry));
    const bounds = all.reduce((b, p) => ({
      minX: Math.min(b.minX, p[0]), maxX: Math.max(b.maxX, p[0]),
      minY: Math.min(b.minY, p[1]), maxY: Math.max(b.maxY, p[1]),
    }), { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });
    const { minX, maxX, minY, maxY } = bounds;
    const pad = 16;
    const scale = Math.min((W - pad * 2) / (maxX - minX), (H - pad * 2) / (maxY - minY));
    const offsetX = (W - (maxX - minX) * scale) / 2;
    const offsetY = (H - (maxY - minY) * scale) / 2;
    return ([x, y]) => [offsetX + (x - minX) * scale, H - offsetY - (y - minY) * scale];
  };

  const featurePath = (geometry, project) => {
    if (!geometry) return '';
    const polygons = geometry.type === 'Polygon' ? [geometry.coordinates]
      : geometry.type === 'MultiPolygon' ? geometry.coordinates : [];
    return polygons.flatMap((rings) => rings.map((ring) => ring.map((point, i) => {
      const [x, y] = project(point);
      return `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(' ') + ' Z')).join(' ');
  };

  const selectFeature = (evt, feature) => {
    const row = currentRows.get(String(feature.properties.locationid));
    if (!row) return;
    if (challengeActive && challengeAwaitingPick) {
      const highest = Math.max(...Array.from(currentRows.values(), (item) => item.value));
      challengeAwaitingPick = false;
      challengeRounds += 1;
      if (Math.abs(row.value - highest) < 0.0001) {
        challengePoints += 1;
        gameFeedback.textContent = `Correct! ${row.county} has the highest ${currentLabel} estimate (${row.value.toFixed(1)}%). Trail mark earned.`;
      } else {
        const answer = Array.from(currentRows.values()).find((item) => Math.abs(item.value - highest) < 0.0001);
        gameFeedback.textContent = `Good try. ${answer.county} is highest for ${currentLabel} at ${highest.toFixed(1)}%. Take that pattern with you to the next round.`;
        mapSvgEl.querySelector(`[data-locationid="${answer.locationid}"]`)?.classList.add('is-game-answer');
      }
      mapSvgEl.querySelector(`[data-locationid="${row.locationid}"]`)?.classList.add(
        Math.abs(row.value - highest) < 0.0001 ? 'is-game-correct' : 'is-game-miss'
      );
      gameScore.textContent = `${challengePoints} / 3`;
      gameButton.textContent = challengeRounds < 3 ? `Next round (${challengeRounds + 1}/3) →` : 'See results →';
      gameButton.disabled = false;
      updateRoundProgress();
      gamePanel.classList.toggle('is-playing', challengeRounds < 3);
    }
    selectedCounty = row;
    mapSvgEl.querySelectorAll('.county').forEach((path) => path.classList.toggle('is-selected', path.dataset.locationid === String(row.locationid)));
    selectionCopy.textContent = `${row.county}: ${currentLabel} is estimated at ${row.value.toFixed(1)}% (95% CI ${row.low.toFixed(1)}–${row.high.toFixed(1)}%).`;
    askCounty.hidden = false;
    showTip(evt, row.county, { ...row, label: currentLabel });
  };

  const advanceChallenge = () => {
    if (challengeRounds >= 3) {
      challengeActive = false;
      gamePanel.classList.remove('is-playing');
      const newRecord = challengePoints > personalBest;
      if (newRecord) {
        personalBest = challengePoints;
        try { localStorage.setItem(GAME_BEST_KEY, String(personalBest)); } catch (err) { /* best score is optional */ }
        gameBest.textContent = `Personal best: ${personalBest}`;
      }
      gamePrompt.textContent = `Challenge complete: ${challengePoints} of 3 trail marks${newRecord ? ' — a new personal best!' : '.'}`;
      gameFeedback.textContent = challengePoints === 3
        ? 'Brilliant map reading. You spotted every county hotspot.'
        : 'Nice exploring. Try again to beat your personal best.';
      gameButton.textContent = 'Play again →';
      gameButton.disabled = false;
      selectEl.disabled = false;
      challengeAwaitingPick = false;
      updateRoundProgress();
      return;
    }
    challengeActive = true;
    challengeAwaitingPick = false;
    challengeLoading = true;
    gamePanel.classList.add('is-playing');
    gameButton.disabled = true;
    gameButton.textContent = 'Loading round…';
    selectEl.disabled = true;
    updateRoundProgress();
    challengeMeasure = availableMeasures[Math.floor(Math.random() * availableMeasures.length)].id;
    selectEl.value = challengeMeasure;
    render(challengeMeasure).then((loaded) => {
      challengeLoading = false;
      if (loaded && challengeAwaitingPick) {
        gameButton.textContent = 'Pick a county on the map ↑';
        gameButton.disabled = true;
      } else {
        challengeActive = false;
        selectEl.disabled = false;
        gameButton.disabled = false;
        gameButton.textContent = 'Try this round again →';
        gameFeedback.textContent = 'The county map did not load. Try the round again in a moment.';
      }
      updateRoundProgress();
    });
    document.getElementById('map-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (gameButton) {
    gameButton.addEventListener('click', () => {
      if (challengeActive && !challengeAwaitingPick) {
        if (challengeRounds >= 3) {
          advanceChallenge();
        } else {
          gamePrompt.textContent = `Round ${challengeRounds + 1}: find the county with the highest estimate. Click a county on the map.`;
          advanceChallenge();
        }
      } else if (!challengeActive && challengeRounds >= 3) {
        challengeRounds = 0;
        challengePoints = 0;
        gameScore.textContent = '0 / 3';
        gamePrompt.textContent = 'Round 1: find the county with the highest estimate. Click a county on the map.';
        gameFeedback.textContent = 'Choose carefully—each round maps a different health measure.';
        gameButton.textContent = 'Loading round…';
        advanceChallenge();
      } else if (!challengeActive && !challengeAwaitingPick) {
        if (challengeRounds === 0) {
          challengePoints = 0;
          gameScore.textContent = '0 / 3';
          gamePrompt.textContent = 'Round 1: find the county with the highest estimate. Click a county on the map.';
          gameFeedback.textContent = 'Choose carefully—each round maps a different health measure.';
        }
        gameButton.textContent = 'Loading round…';
        advanceChallenge();
      }
    });
  }

  const render = async (measureid) => {
    try {
      let data;
      try {
        const res = await fetch(`${TERRAVIA_API}/measures/${measureid}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        data = await res.json();
      } catch (apiError) {
        data = offlineMeasures.get(measureid);
        if (!data) throw apiError;
      }
      currentRows = new Map(data.rows.map((r) => [String(r.locationid), r]));
      currentLabel = data.label;
      if (challengeActive && data.measureid === challengeMeasure) {
        challengeAwaitingPick = true;
        gamePrompt.textContent = `Round ${challengeRounds + 1}: click the county with the highest ${currentLabel} estimate.`;
        gameButton.textContent = 'Pick a county on the map ↑';
        gameButton.disabled = true;
        updateRoundProgress();
      }
      const project = makeProjection();
      mapSvgEl.replaceChildren();
      geo.features.forEach((feature) => {
        const id = String(feature.properties.locationid);
        const row = currentRows.get(id);
        const path = document.createElementNS(NS, 'path');
        path.setAttribute('class', `county${selectedCounty && String(selectedCounty.locationid) === id ? ' is-selected' : ''}`);
        path.setAttribute('d', featurePath(feature.geometry, project));
        path.setAttribute('fill', row ? colorFor(row.value, data.min, data.max) : '#e6e8e4');
        path.setAttribute('stroke', '#fff');
        path.setAttribute('stroke-width', '1.5');
        path.setAttribute('tabindex', '0');
        path.setAttribute('role', 'button');
        path.setAttribute('aria-label', row ? `${row.county}: ${data.label} ${row.value.toFixed(1)} percent. Select for details.` : feature.properties.name);
        path.dataset.locationid = id;
        path.addEventListener('mousemove', (evt) => row && showTip(evt, row.county, { ...row, label: data.label }));
        path.addEventListener('mouseleave', hideTip);
        path.addEventListener('click', (evt) => selectFeature(evt, feature));
        path.addEventListener('focus', (evt) => row && showTip(evt, row.county, { ...row, label: data.label }));
        path.addEventListener('blur', hideTip);
        path.addEventListener('keydown', (evt) => {
          if (evt.key === 'Enter' || evt.key === ' ') { evt.preventDefault(); selectFeature(evt, feature); }
        });
        mapSvgEl.append(path);
      });
      if (selectedCounty) {
        const fresh = currentRows.get(String(selectedCounty.locationid));
        if (fresh) {
          selectedCounty = fresh;
          selectionCopy.textContent = `${fresh.county}: ${currentLabel} is estimated at ${fresh.value.toFixed(1)}% (95% CI ${fresh.low.toFixed(1)}–${fresh.high.toFixed(1)}%).`;
        }
      }

      drawLegend(data.min, data.max);
      caption.textContent =
        `${data.label}: ${data.source}, ${data.data_year}. Shades run county low to high; values are model-based estimates.`;
      return true;
    } catch (err) {
      caption.textContent = `Map data error: ${err.message}`;
      console.error('Terravia map render error:', err);
      return false;
    }
  };

  const init = async () => {
    caption.textContent = 'Loading map…';
    try {
      let gj, ms;
      try {
        [gj, ms] = await Promise.all([
          fetch(`${TERRAVIA_API}/geojson`).then((r) => {
          if (!r.ok) throw new Error(`geojson HTTP ${r.status}`);
          return r.json();
          }),
          fetch(`${TERRAVIA_API}/measures`).then((r) => {
          if (!r.ok) throw new Error(`measures HTTP ${r.status}`);
          return r.json();
          }),
        ]);
      } catch (apiError) {
        const local = await loadOfflineSnapshot();
        gj = local.geometry;
        ms = local;
        caption.textContent = 'Using the included CDC snapshot while the live map service is unavailable.';
      }
      geo = gj;
      availableMeasures = ms.measures;
      selectEl.innerHTML = ms.measures
        .map((m) => `<option value="${m.id}">${m.label}</option>`)
        .join('');
      selectEl.addEventListener('change', () => render(selectEl.value));
      const initialMeasure = pendingMeasure && ms.measures.some((m) => m.id === pendingMeasure)
        ? pendingMeasure : ms.measures[0].id;
      pendingMeasure = null;
      selectEl.value = initialMeasure;
      gameButton.disabled = false;
      updateRoundProgress();
      await render(initialMeasure);
    } catch (err) {
      caption.textContent = `Map unavailable: ${err.message}`;
      console.error('Terravia map init error:', err);
    }
  };

  askCounty.addEventListener('click', () => {
    if (!selectedCounty) return;
    const input = document.getElementById('chat-input');
    if (input) input.value = `Tell me about ${selectedCounty.county}`;
    document.querySelector('.chat-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    input?.focus({ preventScroll: true });
  });

  window.addEventListener('terravia:mission', (evt) => {
    const measure = evt.detail?.measure;
    if (!measure || !selectEl) return;
    if (!Array.from(selectEl.options).some((option) => option.value === measure)) {
      pendingMeasure = measure;
      return;
    }
    selectEl.value = measure;
    selectEl.dispatchEvent(new Event('change'));
    document.getElementById('map-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  init();
}

// Run after everything (including the deferred D3) has loaded.
if (document.readyState === 'complete') {
  initTerraviaMap();
} else {
  window.addEventListener('load', initTerraviaMap);
}
