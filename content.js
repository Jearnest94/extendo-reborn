/*
 * Extendo Reborn - ONE JOB: Show player stats in FACEIT match rooms
 */

let extendoPanel = null;
let extendoRunId = 0; // increments on each navigation so pending polls can cancel
let extendoCollapsed = false; // remember collapsed state across rerenders

// Extract match ID from FACEIT room URL
function getMatchId() {
  const url = window.location.href;
  // Match FACEIT room URLs and extract the full match ID
  const match = url.match(/\/room\/([^\/\?#]+)/);
  return match ? match[1] : null;
}

// Internal helper: sleep
function sleep(ms) { return new Promise(res => setTimeout(res, ms)); }

// Ensure panel exists and optionally set content
function ensurePanel(html) {
  if (!extendoPanel) {
    extendoPanel = document.createElement('div');
    extendoPanel.className = 'extendo-panel';
    document.body.appendChild(extendoPanel);
  }
  if (typeof html === 'string') {
    extendoPanel.innerHTML = html;
    // re-apply collapsed state if needed
    if (extendoCollapsed) extendoPanel.classList.add('collapsed');
    wirePanelInteractions();
  }
  return extendoPanel;
}

// Wire header interactions: collapse on header click, close button removes panel
function wirePanelInteractions() {
  if (!extendoPanel) return;
  const header = extendoPanel.querySelector('.extendo-header');
  const closeBtn = extendoPanel.querySelector('.extendo-close');
  if (header) {
    header.onclick = (e) => {
      // ignore clicks on the close button (it handles its own)
      if (e.target && e.target.classList && e.target.classList.contains('extendo-close')) return;
      extendoCollapsed = !extendoCollapsed;
      extendoPanel.classList.toggle('collapsed', extendoCollapsed);
    };
  }
  if (closeBtn) {
    closeBtn.onclick = (e) => {
      e.stopPropagation();
      if (extendoPanel && extendoPanel.parentElement) {
        extendoPanel.parentElement.removeChild(extendoPanel);
        extendoPanel = null;
      }
    };
  }
}

// One attempt to fetch player nicknames
async function fetchMatchPlayersOnce(matchId) {
  try {
    const response = await fetch(`http://localhost:5000/match/${matchId}/players`);
    const status = response.status;
    let body = null;
    try { body = await response.json(); } catch {}
    if (!response.ok) {
      return { ok: false, status, error: (body && body.error) || `HTTP ${status}` };
    }
    const nicknames = (body && body.nicknames) || [];
    const teams = (body && body.teams) || null;
    return { ok: true, status, nicknames, teams };
  } catch (e) {
    return { ok: false, status: 0, error: String(e) };
  }
}

// Get player nicknames with bounded exponential backoff (handles pre-match rooms)
async function getPlayerNicknamesWithBackoff(runId, {
  maxWaitMs = 60000,
  initialDelayMs = 2000,
  maxDelayMs = 8000
} = {}) {
  const matchId = getMatchId();
  if (!matchId) {
    console.log('Extendo: No match ID found in URL:', window.location.href);
    return { nicknames: [], teams: null };
  }
  console.log('Extendo: Found match ID:', matchId, 'from URL:', window.location.href);

  const start = Date.now();
  let delay = initialDelayMs;
  let attempt = 0;

  while (Date.now() - start < maxWaitMs) {
    // Cancel if a new navigation happened
    if (runId !== extendoRunId) return { nicknames: [], teams: null };

    const r = await fetchMatchPlayersOnce(matchId);
    if (r.ok && Array.isArray(r.nicknames) && r.nicknames.length > 0) {
      return { nicknames: r.nicknames, teams: r.teams || null };
    }
    if (r.status === 401) {
      // Auth problem on backend (likely invalid/expired FACEIT token)
      console.warn('Extendo: FACEIT auth error from backend');
      return { nicknames: [], teams: null };
    }
    // If backend returns 400/404 it likely means Data API doesn't have the match yet
    const shouldRetry = r.status === 400 || r.status === 404 || r.status === 503 || r.status === 0;
    if (!shouldRetry) {
      console.warn('Extendo: non-retryable error from backend:', r);
      return { nicknames: [], teams: null };
    }

    attempt += 1;
    // Update panel with waiting message if present
    if (extendoPanel) {
      extendoPanel.innerHTML = `
        <div class="extendo-header">
          <h3>Target Waiting for Match...</h3>
          <button class="extendo-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
        <div class="extendo-content">
          <div class="loading">Match room detected (${matchId}). Waiting for Data API to expose players...<br/>Attempt ${attempt}, retrying in ${Math.round(delay/1000)}s</div>
        </div>
      `;
    }

    await sleep(delay);
    delay = Math.min(delay * 2, maxDelayMs);
  }
  return { nicknames: [], teams: null };
}

// Check if we're in a match room
function isMatchRoom() {
  return getMatchId() !== null;
}

// Fetch player stats from our API
async function fetchPlayerStats(nicknames) {
  try {
    const response = await fetch('http://localhost:5000/players', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nicknames })
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Extendo API error:', error);
    return [];
  }
}

// Create the stats panel
function createStatsPanel(players, teams = null) {
  // Remove existing panel
  if (extendoPanel) {
    extendoPanel.remove();
  }
  
  extendoPanel = document.createElement('div');
  extendoPanel.className = 'extendo-panel';
  
  let html = `
    <div class="extendo-header">
      <h3>Target Player Stats</h3>
      <button class="extendo-close" onclick="this.parentElement.parentElement.remove()">×</button>
    </div>
    <div class="extendo-content">
  `;
  
  if (players.length === 0) {
    html += '<p>No player data available</p>';
  } else {
    // helpers for consistent presentation
    const fmt = (n, digits = 2) => (n == null || isNaN(n) ? '—' : Number(n).toFixed(digits));
    const chip = (label, value) => `<span class="chip"><span class="chip-k">${label}</span><span class="chip-v">${value}</span></span>`;
    const metricRow = (title, chipsHtml) => `
      <div class="metric-row">
        <div class="metric-label">${title}</div>
        <div class="metric-chips">${chipsHtml}</div>
      </div>`;
    // Map by nickname for quick lookup
    const byNick = Object.create(null);
    for (const p of players) if (p && p.nickname) byNick[p.nickname] = p;

    if (teams && teams.team1 && teams.team2) {
      const t1name = teams.team1.name || 'Team 1';
      const t2name = teams.team2.name || 'Team 2';
      const t1nicks = ((teams.team1.players || []).map(p => p.nickname)).filter(Boolean);
      const t2nicks = ((teams.team2.players || []).map(p => p.nickname)).filter(Boolean);
      const t1 = t1nicks.map(n => byNick[n]).filter(Boolean).sort((a, b) => (b.elo || 0) - (a.elo || 0));
      const t2 = t2nicks.map(n => byNick[n]).filter(Boolean).sort((a, b) => (b.elo || 0) - (a.elo || 0));

      const renderPlayerCard = (player) => {
        const winRate = player.wins && player.matches ? Math.round((player.wins / player.matches) * 100) : 0;
        const adr10 = player.adr_last_10;
        const adr30 = player.adr_last_30;
        const adr100 = player.adr_last_100;
        const wr10 = player.win_rate_last_10;
        const wr30 = player.win_rate_last_30;
        const wr100 = player.win_rate_last_100;
        const elo10 = player.elo_10_games_ago;
        const elo30 = player.elo_30_games_ago;
        const elo100 = player.elo_100_games_ago;
        const d10 = player.date_10_games_ago || '—';
        const d30 = player.date_30_games_ago || '—';
        const d100 = player.date_100_games_ago || '—';
        const g7 = player.games_per_day_7d;
        const g30 = player.games_per_day_30d;
        const g90 = player.games_per_day_90d;
        // Build compact map stats
        const mp = Array.isArray(player.top_maps_played) ? player.top_maps_played.slice(0,7) : [];
        const bw = Array.isArray(player.top_maps_wr) ? player.top_maps_wr.slice(0,7) : [];
        const abbr = (name) => {
          if (!name) return '';
          const map = String(name);
          // compact known long names
          const dict = { 'Ancient': 'Anc.', 'Anubis': 'Anu.', 'Overpass': 'Over.', 'Inferno': 'Inf.', 'Mirage': 'Mir.', 'Vertigo': 'Vert.', 'Nuke': 'Nuke', 'Dust2': 'D2', 'Dust II': 'D2', 'Train': 'Train' };
          return dict[map] || (map.length > 6 ? map.slice(0,6) + '.' : map);
        };
        // Determine WR class bucket
        const wrClass = (wr) => {
          if (wr == null || isNaN(wr)) return 'wr-unknown';
          const w = Number(wr);
          if (w >= 70) return 'wr-great wr-bold';
          if (w >= 60) return 'wr-good wr-bold';
          if (w >= 50) return 'wr-mid';
          return 'wr-bad';
        };
        // Build a map of WR by label for consistent styling across MP row
        const wrByLabel = Object.create(null);
        for (const m of bw) if (m && m.label != null) wrByLabel[m.label] = Math.round(m.wr);
        // Token builders
        const tokensMP = mp.map(m => {
          const label = abbr(m.label);
          const wr = wrByLabel[m.label];
          const cls = wrClass(wr);
          return `<span class="map-item ${cls}" title="${m.label} · ${m.matches} MP${wr!=null?` · ${wr}% WR`:''}">${label} ${m.matches}</span>`;
        }).join(' ');
        const tokensWR = bw.map(m => {
          const label = abbr(m.label);
          const wr = Math.round(m.wr);
          const cls = wrClass(wr);
          return `<span class="map-item ${cls}" title="${m.label} · ${wr}% WR">${label} ${wr}%</span>`;
        }).join(' ');

        return `
          <div class="player-card">
              <div class="player-header">
              <div class="player-name">${player.nickname}</div>
              <div class="map-stats">
                ${tokensMP ? `<div class="row"><span class="label">MP:</span><span class="val">${tokensMP}</span></div>` : ''}
                ${tokensWR ? `<div class="row"><span class="label">WR:</span><span class="val">${tokensWR}</span></div>` : ''}
              </div>
            </div>
            <div class="player-stats">
              <span class="elo">${player.elo}</span>
              <span class="level">Lvl ${player.level}</span>
              <span class="kd">K/D: ${player.kd || 'N/A'}</span>
              <span class="winrate">Win: ${winRate}%</span>
            </div>
            ${metricRow('ADR / Win %', [
              chip('ADR10', fmt(adr10)),
              chip('ADR30', fmt(adr30)),
              chip('ADR100', fmt(adr100)),
              '<span class="chip sep">|</span>',
              '<span class="chip sub">Win %</span>',
              chip('W10', fmt(wr10)),
              chip('W30', fmt(wr30)),
              chip('W100', fmt(wr100))
            ].join(''))}
            ${metricRow('Elo / Nth', [
              chip('E10', elo10 != null ? elo10 : '—'),
              chip('E30', elo30 != null ? elo30 : '—'),
              chip('E100', elo100 != null ? elo100 : '—'),
              '<span class="chip sep">|</span>',
              '<span class="chip sub">Nth.</span>',
              chip('10th', d10),
              chip('30th', d30),
              chip('100th', d100)
            ].join(''))}
            ${metricRow('Games/day', [
              chip('7d', fmt(g7)),
              chip('30d', fmt(g30)),
              chip('90d', fmt(g90))
            ].join(''))}
          </div>`;
      };

      html += '<div class="teams-grid">';
      html += `<div class="team-column"><div class="team-heading">${t1name}</div><div class="players-list">${t1.map(renderPlayerCard).join('')}</div></div>`;
      html += `<div class="team-column"><div class="team-heading">${t2name}</div><div class="players-list">${t2.map(renderPlayerCard).join('')}</div></div>`;
      html += '</div>';
    } else {
      // Fallback: sort and render in two-column generic grid
      const sorted = [...players].sort((a, b) => (b.elo || 0) - (a.elo || 0));
      html += '<div class="players-grid">';
      sorted.forEach(player => {
        if (player.error) {
          html += `<div class=\"player-card error\">X ${player.nickname}: ${player.error}</div>`;
        } else {
          const winRate = player.wins && player.matches ? Math.round((player.wins / player.matches) * 100) : 0;
          const adr10 = player.adr_last_10;
          const adr30 = player.adr_last_30;
          const adr100 = player.adr_last_100;
          const wr10 = player.win_rate_last_10;
          const wr30 = player.win_rate_last_30;
          const wr100 = player.win_rate_last_100;
          const elo10 = player.elo_10_games_ago;
          const elo30 = player.elo_30_games_ago;
          const elo100 = player.elo_100_games_ago;
          const d10 = player.date_10_games_ago || '—';
          const d30 = player.date_30_games_ago || '—';
          const d100 = player.date_100_games_ago || '—';
          const g7 = player.games_per_day_7d;
          const g30 = player.games_per_day_30d;
          const g90 = player.games_per_day_90d;
          const mp = Array.isArray(player.top_maps_played) ? player.top_maps_played.slice(0,7) : [];
          const bw = Array.isArray(player.top_maps_wr) ? player.top_maps_wr.slice(0,7) : [];
          const abbr = (name) => {
            if (!name) return '';
            const map = String(name);
            const dict = { 'Ancient': 'Anc.', 'Anubis': 'Anu.', 'Overpass': 'Over.', 'Inferno': 'Inf.', 'Mirage': 'Mir.', 'Vertigo': 'Vert.', 'Nuke': 'Nuke', 'Dust2': 'D2', 'Dust II': 'D2', 'Train': 'Train' };
            return dict[map] || (map.length > 6 ? map.slice(0,6) + '.' : map);
          };
          const wrClass = (wr) => {
            if (wr == null || isNaN(wr)) return 'wr-unknown';
            const w = Number(wr);
            if (w >= 70) return 'wr-great wr-bold';
            if (w >= 60) return 'wr-good wr-bold';
            if (w >= 50) return 'wr-mid';
            return 'wr-bad';
          };
          const wrByLabel = Object.create(null);
          for (const m of bw) if (m && m.label != null) wrByLabel[m.label] = Math.round(m.wr);
          const tokensMP = mp.map(m => {
            const label = abbr(m.label);
            const wr = wrByLabel[m.label];
            const cls = wrClass(wr);
            return `<span class=\"map-item ${cls}\" title=\"${m.label} · ${m.matches} MP${wr!=null?` · ${wr}% WR`:''}\">${label} ${m.matches}</span>`;
          }).join(' ');
          const tokensWR = bw.map(m => {
            const label = abbr(m.label);
            const wr = Math.round(m.wr);
            const cls = wrClass(wr);
            return `<span class=\"map-item ${cls}\" title=\"${m.label} · ${wr}% WR\">${label} ${wr}%</span>`;
          }).join(' ');

          html += `
            <div class=\"player-card\"> 
              <div class=\"player-header\">
                <div class=\"player-name\">${player.nickname}</div>
                <div class=\"map-stats\">
                  ${tokensMP ? `<div class=\"row\"><span class=\"label\">MP:</span><span class=\"val\">${tokensMP}</span></div>` : ''}
                  ${tokensWR ? `<div class=\"row\"><span class=\"label\">WR:</span><span class=\"val\">${tokensWR}</span></div>` : ''}
                </div>
                  ${fmtMP ? `<div class=\"row\"><span class=\"label\">MP:</span><span class=\"val\">${fmtMP}</span></div>` : ''}
                  ${fmtBW ? `<div class=\"row\"><span class=\"label\">WR:</span><span class=\"val\">${fmtBW}</span></div>` : ''}
                </div>
              </div>
              <div class=\"player-stats\"> 
                <span class=\"elo\">${player.elo}</span>
                <span class=\"level\">Lvl ${player.level}</span>
                <span class=\"kd\">K/D: ${player.kd || 'N/A'}</span>
                <span class=\"winrate\">Win: ${winRate}%</span>
              </div>
              ${metricRow('ADR / Win %', [
                chip('ADR10', fmt(adr10)),
                chip('ADR30', fmt(adr30)),
                chip('ADR100', fmt(adr100)),
                '<span class="chip sep">|</span>',
                '<span class="chip sub">Win %</span>',
                chip('W10', fmt(wr10)),
                chip('W30', fmt(wr30)),
                chip('W100', fmt(wr100))
              ].join(''))}
              ${metricRow('Elo / Nth', [
                chip('E10', elo10 != null ? elo10 : '—'),
                chip('E30', elo30 != null ? elo30 : '—'),
                chip('E100', elo100 != null ? elo100 : '—'),
                '<span class="chip sep">|</span>',
                '<span class="chip sub">Nth.</span>',
                chip('10th', d10),
                chip('30th', d30),
                chip('100th', d100)
              ].join(''))}
              ${metricRow('Games/day', [
                chip('7d', fmt(g7)),
                chip('30d', fmt(g30)),
                chip('90d', fmt(g90))
              ].join(''))}
            </div>
          `;
        }
      });
      html += '</div>';
    }
  }
  
  html += '</div>';
  extendoPanel.innerHTML = html;
  // respect persisted collapsed state
  if (extendoCollapsed) extendoPanel.classList.add('collapsed');
  
  // Add to page
  document.body.appendChild(extendoPanel);
  wirePanelInteractions();
}

// Main function to run Extendo
async function runExtendo() {
  console.log('Target Extendo Reborn checking page...');

  if (!isMatchRoom()) {
    console.log('Not a match room, skipping');
    return;
  }

  const runId = ++extendoRunId;

  // Show immediate waiting panel before polling starts
  const mId = getMatchId();
  ensurePanel(`
    <div class="extendo-header">
      <h3>Target Waiting for Match...</h3>
      <button class="extendo-close" onclick="this.parentElement.parentElement.remove()">×</button>
    </div>
    <div class="extendo-content">
      <div class="loading">Match room detected${mId ? ` (${mId})` : ''}. Preparing to fetch players...</div>
    </div>
  `);

  // Try to fetch players with graceful waiting for pre-match rooms
  const matchInfo = await getPlayerNicknamesWithBackoff(runId, { maxWaitMs: 60000, initialDelayMs: 2000, maxDelayMs: 8000 });
  console.log('Found players:', matchInfo.nicknames);

  if (matchInfo.nicknames.length === 0) {
    // Timed out or non-retryable error
    if (extendoPanel) {
      extendoPanel.innerHTML = `
        <div class="extendo-header">
          <h3>Target Waiting for Match...</h3>
          <button class="extendo-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
        <div class="extendo-content">
          <div class="loading">No players available yet. If the match hasn\'t started, try again once it goes live.</div>
        </div>
      `;
      wirePanelInteractions();
    }
    return;
  }

  // Show loading
  createStatsPanel([]);
  extendoPanel.innerHTML = `
    <div class="extendo-header">
      <h3>Target Loading Stats...</h3>
      <button class="extendo-close" onclick="this.parentElement.parentElement.remove()">×</button>
    </div>
    <div class="extendo-content">
      <div class="loading">Loading... Fetching data for ${matchInfo.nicknames.length} players...</div>
    </div>
  `;
  wirePanelInteractions();

  // Fetch and display stats
  const players = await fetchPlayerStats(matchInfo.nicknames);
  createStatsPanel(players, matchInfo.teams || null);
}

// Run when page loads or changes
function initialize() {
  console.log('Target Extendo Reborn initialized');
  
  // Run initially
  setTimeout(runExtendo, 1000);
  
  // Watch for URL changes (FACEIT is a SPA)
  let currentUrl = window.location.href;
  setInterval(() => {
    if (window.location.href !== currentUrl) {
      currentUrl = window.location.href;
      console.log('URL changed, re-running Extendo');
      setTimeout(runExtendo, 2000); // Give page time to load
    }
  }, 1000);
}

// Start when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initialize);
} else {
  initialize();
}