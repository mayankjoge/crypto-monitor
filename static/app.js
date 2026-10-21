'use strict';

const $ = selector => document.querySelector(selector);
const $$ = selector => Array.from(document.querySelectorAll(selector));
const esc = value => String(value).replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[character]));
const usd = value => {
  if (value == null || !Number.isFinite(Number(value))) return 'n/a';
  const number = Number(value);
  return '$' + (number >= 1
    ? number.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : number.toPrecision(3));
};
const compactUsd = value => {
  if (value == null || !Number.isFinite(Number(value))) return 'n/a';
  return '$' + new Intl.NumberFormat('en', {
    notation: 'compact', maximumFractionDigits: 2
  }).format(Number(value));
};
// Keep labels, colors, and gainers/losers filters consistent with the displayed 2 decimals.
const displayedPct = value => value == null || !Number.isFinite(Number(value)) ? null : Number(Number(value).toFixed(2));
const pct = value => {
  const number = displayedPct(value);
  if (number == null) return 'n/a';
  if (number > 0) return `▲ +${number.toFixed(2)}%`;
  if (number < 0) return `▼ ${number.toFixed(2)}%`;
  return '— 0.00%';
};
const pctTone = value => {
  const number = displayedPct(value);
  return number == null || number === 0 ? '' : (number > 0 ? 'positive' : 'negative');
};

let coins = [];
let view = 'all';
let sortKey = 'market_cap';
let sortDir = -1;
let selectedCoinId = null;
let days = 30;
let historyPayload = null;
let showSma7 = true;
let showSma30 = true;
let marketRequest = 0;
let historyRequest = 0;
let signalRequest = 0;
let screenRequest = 0;
let chartGeometry = null;

let watch = new Set();
try {
  const saved = JSON.parse(localStorage.getItem('watch') || '[]');
  if (Array.isArray(saved)) {
    watch = new Set(saved.filter(id => typeof id === 'string' && /^[a-z0-9-]{1,64}$/.test(id)));
  }
} catch (_) {
  // Storage can be blocked or contain invalid JSON; the watchlist simply starts empty.
}

const columns = [
  ['★', null], ['Name', 'name'], ['Symbol', 'symbol'], ['Price', 'price'],
  ['24h %', 'change_24h'], ['24h volume', 'volume_24h'], ['Market cap', 'market_cap']
];
$('#head').innerHTML = columns.map(([label, key]) => key
  ? `<th scope="col" aria-sort="none"><button type="button" data-k="${key}">${label}</button></th>`
  : `<th scope="col">${label}</th>`).join('');

function refreshSortHeaders() {
  columns.forEach(([label, key]) => {
    if (!key) return;
    const header = $(`#head button[data-k="${key}"]`);
    const th = header.closest('th');
    const active = key === sortKey;
    th.setAttribute('aria-sort', active ? (sortDir === -1 ? 'descending' : 'ascending') : 'none');
    header.textContent = label + (active ? (sortDir === -1 ? ' ↓' : ' ↑') : '');
    header.setAttribute('aria-label', `Sort by ${label}${active ? (sortDir === -1 ? ', descending' : ', ascending') : ''}`);
  });
}
refreshSortHeaders();

async function api(path) {
  let response;
  try {
    response = await fetch(path, { headers: { Accept: 'application/json' } });
  } catch (_) {
    throw new Error('Cannot reach the server. Check that the app is running.');
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function banner(payload, error) {
  const status = $('#status');
  status.hidden = true;
  status.className = 'banner';
  if (error) {
    status.hidden = false;
    status.classList.add('err');
    status.textContent = `Market data unavailable: ${error}. No current market prices are shown.`;
    return;
  }
  const messages = [];
  if (payload.source === 'mock') messages.push('MOCK MODE: synthetic data, not real market prices.');
  if (payload.warning) messages.push(payload.warning);
  else if (payload.stale) messages.push('Data may be stale.');
  if (messages.length) {
    status.hidden = false;
    status.classList.add('warn');
    status.textContent = messages.join(' ');
  }
}

async function loadMarkets() {
  const requestId = ++marketRequest;
  if (!coins.length) $('#stamp').textContent = 'Loading market data…';
  try {
    const payload = await api('/api/markets');
    if (requestId !== marketRequest) return;
    if (!payload || !Array.isArray(payload.data)) throw new Error('The server returned an invalid market-data response.');
    coins = payload.data;
    banner(payload);
    $('#stamp').textContent = `Source: ${payload.source}. Fetched ${new Date(payload.fetched_at).toLocaleString()}${payload.stale ? ' (STALE)' : ''}.`;
    renderTable();
    loadSignals();
  } catch (error) {
    if (requestId !== marketRequest) return;
    coins = [];
    banner(null, error.message);
    $('#stamp').textContent = 'No current market data.';
    renderTable();
    $('#active').innerHTML = `<li>Unavailable: ${esc(error.message)}</li>`;
    $('#activerule').textContent = '';
    $('#screenrule').textContent = `Screen unavailable: ${error.message}`;
    $('#screen').innerHTML = '';
  }
}

function renderTable() {
  const query = $('#q').value.trim().toLowerCase();
  let visible = coins.filter(coin => !query
    || coin.name.toLowerCase().includes(query)
    || coin.symbol.toLowerCase().includes(query));

  if (view === 'watch') visible = visible.filter(coin => watch.has(coin.id));
  if (view === 'gain') visible = visible.filter(coin => displayedPct(coin.change_24h) > 0);
  if (view === 'lose') visible = visible.filter(coin => displayedPct(coin.change_24h) < 0);

  visible.sort((left, right) => {
    const a = left[sortKey];
    const b = right[sortKey];
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;
    const result = typeof a === 'string' ? a.localeCompare(b) : Number(a) - Number(b);
    return result * sortDir;
  });

  $('#rows').innerHTML = visible.map(coin => {
    const watching = watch.has(coin.id);
    return `<tr data-id="${esc(coin.id)}" tabindex="0" aria-label="Show price history for ${esc(coin.name)}" class="${coin.id === selectedCoinId ? 'sel' : ''}">
      <td><button type="button" class="star" data-w="${esc(coin.id)}" aria-pressed="${watching}" aria-label="${watching ? 'Remove' : 'Add'} ${esc(coin.name)} ${watching ? 'from' : 'to'} watchlist" title="${watching ? 'Remove from' : 'Add to'} watchlist">${watching ? '★' : '☆'}</button></td>
      <td>${esc(coin.name)}</td><td>${esc(coin.symbol)}</td><td>${usd(coin.price)}</td>
      <td class="${pctTone(coin.change_24h)}">${pct(coin.change_24h)}</td>
      <td>${compactUsd(coin.volume_24h)}</td><td>${compactUsd(coin.market_cap)}</td>
    </tr>`;
  }).join('');

  const empty = $('#empty');
  empty.hidden = visible.length > 0;
  if (visible.length) empty.textContent = '';
  else if (!coins.length) empty.textContent = 'No market data to display. Check the status message above.';
  else if (view === 'watch' && watch.size === 0 && !query) empty.textContent = 'Your watchlist is empty. Select ☆ beside any coin to add it.';
  else empty.textContent = 'No coins match the current search or filter.';
  refreshSortHeaders();
}

function saveWatchlist() {
  try { localStorage.setItem('watch', JSON.stringify([...watch])); } catch (_) {
    const status = $('#status');
    status.hidden = false;
    status.className = 'banner warn';
    status.textContent = 'Your browser blocked local storage, so watchlist changes may not persist after refresh.';
  }
}

function selectCoin(coinId) {
  selectedCoinId = coinId;
  renderTable();
  loadHistory();
}

$('#head').addEventListener('click', event => {
  const key = event.target.closest('button[data-k]')?.dataset.k;
  if (!key) return;
  sortDir = sortKey === key ? -sortDir : -1;
  sortKey = key;
  renderTable();
});

$('#rows').addEventListener('click', event => {
  const watchButton = event.target.closest('button[data-w]');
  if (watchButton) {
    const coinId = watchButton.dataset.w;
    if (watch.has(coinId)) watch.delete(coinId);
    else watch.add(coinId);
    saveWatchlist();
    renderTable();
    return;
  }
  const row = event.target.closest('tr[data-id]');
  if (row) selectCoin(row.dataset.id);
});

$('#rows').addEventListener('keydown', event => {
  if (event.target.closest('button') || !['Enter', ' '].includes(event.key)) return;
  const row = event.target.closest('tr[data-id]');
  if (!row) return;
  event.preventDefault();
  selectCoin(row.dataset.id);
});

$('#q').addEventListener('input', renderTable);
$$('.tabs button').forEach(button => button.addEventListener('click', () => {
  view = button.dataset.view;
  $$('.tabs button').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  renderTable();
}));

$$('#periods [data-d]').forEach(button => button.addEventListener('click', () => {
  days = Number(button.dataset.d);
  $$('#periods [data-d]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  if (selectedCoinId) loadHistory();
}));

for (const [selector, which] of [['#t7', 7], ['#t30', 30]]) {
  $(selector).addEventListener('click', event => {
    const on = event.currentTarget.getAttribute('aria-pressed') !== 'true';
    event.currentTarget.setAttribute('aria-pressed', String(on));
    if (which === 7) showSma7 = on;
    else showSma30 = on;
    drawChart();
  });
}

function historyIsValid(payload) {
  const data = payload && payload.data;
  if (!data || !['t', 'price', 'volume', 'sma7', 'sma30'].every(key => Array.isArray(data[key]))) return false;
  const length = data.t.length;
  return length > 1 && ['price', 'volume', 'sma7', 'sma30'].every(key => data[key].length === length)
    && data.t.every(Number.isFinite) && data.price.every(value => Number.isFinite(value) && value > 0);
}

async function loadHistory() {
  if (!selectedCoinId) return;
  const requestId = ++historyRequest;
  const requestedId = selectedCoinId;
  const requestedDays = days;
  const coin = coins.find(item => item.id === requestedId);
  $('#coinname').textContent = coin ? coin.name : requestedId;
  $('#chartnote').textContent = 'Loading daily price history…';
  historyPayload = null;
  drawChart();
  try {
    const payload = await api(`/api/history/${encodeURIComponent(requestedId)}?days=${requestedDays}`);
    if (requestId !== historyRequest || requestedId !== selectedCoinId || requestedDays !== days) return;
    if (!historyIsValid(payload)) throw new Error('The server returned invalid history data.');
    historyPayload = payload;
    drawChart();
    const data = payload.data;
    const volatility = data.volatility_pct == null ? 'n/a' : `${data.volatility_pct.toFixed(2)}%`;
    const warnings = [];
    if (payload.source === 'mock') warnings.push('MOCK data.');
    if (payload.stale) warnings.push(payload.warning || 'History may be stale.');
    $('#chartnote').textContent = `${warnings.length ? warnings.join(' ') + ' ' : ''}${data.points} daily points, last ${new Date(data.last_point_ts).toLocaleDateString(undefined, { timeZone: 'UTC' })}. Volatility (daily returns): ${volatility}.`;
  } catch (error) {
    if (requestId !== historyRequest || requestedId !== selectedCoinId || requestedDays !== days) return;
    historyPayload = null;
    drawChart();
    $('#chartnote').textContent = `Chart unavailable: ${error.message}`;
  }
}

function chartColor(name, fallback) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function drawLine(ctx, values, color, dashed, xAt, yAt) {
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = dashed ? 1.5 : 2.25;
  ctx.setLineDash(dashed ? [6, 4] : []);
  let drawing = false;
  values.forEach((value, index) => {
    if (value == null || !Number.isFinite(value)) {
      drawing = false;
      return;
    }
    const x = xAt(index);
    const y = yAt(value);
    if (!drawing) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
    drawing = true;
  });
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawChart() {
  const canvas = $('#chart');
  const ctx = canvas.getContext && canvas.getContext('2d');
  if (!ctx) {
    $('#chartnote').textContent = 'This browser does not support canvas charts.';
    return;
  }
  const bounds = canvas.getBoundingClientRect();
  const width = Math.max(1, bounds.width);
  const height = Math.max(240, bounds.height);
  const ratio = Math.max(1, window.devicePixelRatio || 1);
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const ink = chartColor('--ink', '#16202a');
  const muted = chartColor('--mute', '#5a6775');
  const grid = chartColor('--line', '#d9dee5');
  const accent = chartColor('--accent', '#0b5c6b');
  const sma7Color = chartColor('--chart-sma7', '#b8860b');
  const sma30Color = chartColor('--chart-sma30', '#8c63b8');
  const volumeColor = chartColor('--chart-volume', 'rgba(120,130,140,.28)');
  ctx.font = '12px system-ui, -apple-system, Segoe UI, sans-serif';
  ctx.fillStyle = muted;

  if (!historyPayload) {
    chartGeometry = null;
    $('#chartTooltip').hidden = true;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(selectedCoinId ? 'Loading chart…' : 'Select a coin from the market table to load its daily history.', width / 2, height / 2);
    return;
  }

  const data = historyPayload.data;
  const shownSmas = [];
  if (showSma7) shownSmas.push(...data.sma7.filter(Number.isFinite));
  if (showSma30) shownSmas.push(...data.sma30.filter(Number.isFinite));
  const allValues = data.price.concat(shownSmas).filter(Number.isFinite);
  let minimum = Math.min(...allValues);
  let maximum = Math.max(...allValues);
  if (minimum === maximum) {
    const pad = Math.max(Math.abs(minimum) * 0.02, 0.01);
    minimum -= pad;
    maximum += pad;
  } else {
    const pad = (maximum - minimum) * 0.08;
    minimum -= pad;
    maximum += pad;
  }

  const left = 72;
  const right = 78;
  const top = 22;
  const bottom = 40;
  const plotWidth = Math.max(1, width - left - right);
  const plotHeight = Math.max(1, height - top - bottom);
  const count = data.price.length;
  const xAt = index => left + (count <= 1 ? 0 : (index / (count - 1)) * plotWidth);
  const yAt = value => top + ((maximum - value) / (maximum - minimum)) * plotHeight;
  chartGeometry = { left, top, plotWidth, plotHeight, count, width, height };

  // Grid and price-axis labels.
  ctx.lineWidth = 1;
  ctx.strokeStyle = grid;
  ctx.fillStyle = muted;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (let tick = 0; tick <= 4; tick++) {
    const y = top + (plotHeight * tick / 4);
    const value = maximum - ((maximum - minimum) * tick / 4);
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(left + plotWidth, y);
    ctx.stroke();
    ctx.fillText(compactUsd(value), left - 9, y);
  }

  // Volume bars share the time axis and occupy the bottom fifth of the plot.
  const validVolumes = data.volume.filter(value => value != null && Number.isFinite(value) && value >= 0);
  const maxVolume = validVolumes.length ? Math.max(...validVolumes, 1) : 1;
  const barWidth = Math.max(1, Math.min(12, plotWidth / Math.max(count, 1) * 0.62));
  ctx.fillStyle = volumeColor;
  data.volume.forEach((volume, index) => {
    if (volume == null || !Number.isFinite(volume) || volume < 0) return;
    const barHeight = (volume / maxVolume) * (plotHeight * 0.18);
    ctx.fillRect(xAt(index) - barWidth / 2, top + plotHeight - barHeight, barWidth, barHeight);
  });

  drawLine(ctx, data.price, accent, false, xAt, yAt);
  if (showSma7) drawLine(ctx, data.sma7, sma7Color, true, xAt, yAt);
  if (showSma30) drawLine(ctx, data.sma30, sma30Color, true, xAt, yAt);

  // Show evenly spaced date labels without making small screens unreadable.
  ctx.fillStyle = muted;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  const labelCount = Math.min(6, count);
  const seen = new Set();
  for (let label = 0; label < labelCount; label++) {
    const index = Math.round(label * (count - 1) / Math.max(labelCount - 1, 1));
    if (seen.has(index)) continue;
    seen.add(index);
    const dateLabel = new Date(data.t[index]).toLocaleDateString(undefined, { timeZone: 'UTC', month: 'short', day: 'numeric' });
    ctx.fillText(dateLabel, xAt(index), top + plotHeight + 9);
  }
  ctx.save();
  ctx.translate(16, top + plotHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillStyle = ink;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('Price (USD)', 0, 0);
  ctx.restore();
  ctx.fillStyle = muted;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'top';
  ctx.fillText(`Vol max ${compactUsd(maxVolume)}`, width - 8, 4);
  $('#chartTooltip').hidden = true;
}

function showChartTooltip(event) {
  if (!historyPayload || !chartGeometry) return;
  const rect = $('#chart').getBoundingClientRect();
  const localX = event.clientX - rect.left;
  const { left, plotWidth, count, width } = chartGeometry;
  if (localX < left || localX > left + plotWidth) {
    $('#chartTooltip').hidden = true;
    return;
  }
  const index = Math.max(0, Math.min(count - 1, Math.round(((localX - left) / plotWidth) * (count - 1))));
  const data = historyPayload.data;
  const tooltip = $('#chartTooltip');
  const lines = [
    new Date(data.t[index]).toLocaleDateString(undefined, { timeZone: 'UTC' }),
    `Price: ${usd(data.price[index])}`,
    `Volume: ${compactUsd(data.volume[index])}`
  ];
  if (showSma7) lines.push(`SMA 7: ${usd(data.sma7[index])}`);
  if (showSma30) lines.push(`SMA 30: ${usd(data.sma30[index])}`);
  tooltip.textContent = lines.join('\n');
  tooltip.hidden = false;
  const tipWidth = tooltip.offsetWidth || 175;
  tooltip.style.left = `${Math.max(8, Math.min(width - tipWidth - 8, localX + 14))}px`;
  tooltip.style.top = '10px';
}

$('#chart').addEventListener('mousemove', showChartTooltip);
$('#chart').addEventListener('click', showChartTooltip);
$('#chart').addEventListener('mouseleave', () => { $('#chartTooltip').hidden = true; });
window.addEventListener('resize', () => window.requestAnimationFrame(drawChart));

async function loadSignals() {
  const requestId = ++signalRequest;
  $('#active').innerHTML = '<li>Loading activity ranking…</li>';
  try {
    const payload = await api('/api/active');
    if (requestId !== signalRequest) return;
    $('#activerule').textContent = payload.rule || 'Ranked by 24h trading volume, descending.';
    $('#active').innerHTML = (payload.data || []).map(coin =>
      `<li>${esc(coin.name)} (${esc(coin.symbol)}): 24h volume ${compactUsd(coin.volume_24h)}</li>`
    ).join('') || '<li>No activity data available.</li>';
    loadScreen();
  } catch (error) {
    if (requestId !== signalRequest) return;
    $('#active').innerHTML = `<li>Unavailable: ${esc(error.message)}</li>`;
    $('#activerule').textContent = '';
    $('#screenrule').textContent = `Screen unavailable: ${error.message}`;
  }
}

async function loadScreen() {
  const requestId = ++screenRequest;
  const parameters = new URLSearchParams({
    min_change_24h: $('#p1').value,
    min_turnover: $('#p2').value,
    min_market_cap: $('#p3').value
  });
  $('#screenrule').textContent = 'Running screen…';
  try {
    const payload = await api('/api/screen?' + parameters);
    if (requestId !== screenRequest) return;
    $('#screenrule').textContent = 'Rule: ' + payload.rule;
    $('#screen').innerHTML = (payload.data || []).map(coin =>
      `<tr><td>${esc(coin.name)} (${esc(coin.symbol)})</td><td class="${pctTone(coin.change_24h)}">${pct(coin.change_24h)}</td><td>${Number(coin.turnover).toFixed(3)}</td><td>${compactUsd(coin.market_cap)}</td></tr>`
    ).join('') || '<tr><td colspan="4">No coins meet this rule right now.</td></tr>';
  } catch (error) {
    if (requestId !== screenRequest) return;
    $('#screenrule').textContent = 'Screen unavailable: ' + error.message;
    $('#screen').innerHTML = '';
  }
}

$('#run').addEventListener('click', loadScreen);
loadMarkets();
window.setInterval(loadMarkets, 60_000);
