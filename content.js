/*
 * Extendo Reborn - ONE JOB: Show player stats in FACEIT match rooms
 */

let extendoPanel = null;
let extendoRunId = 0; // increments on each navigation so pending polls can cancel

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
  }
  return extendoPanel;
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
    return { ok: true, status, nicknames };
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
    return [];
  }
  console.log('Extendo: Found match ID:', matchId, 'from URL:', window.location.href);

  const start = Date.now();
  let delay = initialDelayMs;
  let attempt = 0;

  while (Date.now() - start < maxWaitMs) {
    // Cancel if a new navigation happened
    if (runId !== extendoRunId) return [];

    const r = await fetchMatchPlayersOnce(matchId);
    if (r.ok && Array.isArray(r.nicknames) && r.nicknames.length > 0) {
      return r.nicknames;
    }
    if (r.status === 401) {
      // Auth problem on backend (likely invalid/expired FACEIT token)
      console.warn('Extendo: FACEIT auth error from backend');
      return [];
    }
    // If backend returns 400/404 it likely means Data API doesn't have the match yet
    const shouldRetry = r.status === 400 || r.status === 404 || r.status === 503 || r.status === 0;
    if (!shouldRetry) {
      console.warn('Extendo: non-retryable error from backend:', r);
      return [];
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
  return [];
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
function createStatsPanel(players) {
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
    players.forEach(player => {
      if (player.error) {
        html += `<div class="player-card error">X ${player.nickname}: ${player.error}</div>`;
      } else {
        const winRate = player.wins && player.matches ? Math.round((player.wins / player.matches) * 100) : 0;
            const adr10 = player.adr_last_10 != null ? player.adr_last_10 : 'N/A';
            const adr30 = player.adr_last_30 != null ? player.adr_last_30 : 'N/A';
            const adr100 = player.adr_last_100 != null ? player.adr_last_100 : 'N/A';
            const d10 = player.date_10_games_ago || '—';
            const d30 = player.date_30_games_ago || '—';
            const d100 = player.date_100_games_ago || '—';
            const g7 = player.games_per_day_7d != null ? player.games_per_day_7d : '—';
            const g30 = player.games_per_day_30d != null ? player.games_per_day_30d : '—';
            const g90 = player.games_per_day_90d != null ? player.games_per_day_90d : '—';
        html += `
          <div class="player-card">
            <div class="player-name">${player.nickname}</div>
            <div class="player-stats">
              <span class="elo">⭐ ${player.elo}</span>
              <span class="level">Lvl ${player.level}</span>
              <span class="kd">K/D: ${player.kd || 'N/A'}</span>
              <span class="winrate">Win: ${winRate}%</span>
            </div>
                <div class="player-stats">
                  <span class="adr">ADR 10/30/100: ${adr10}/${adr30}/${adr100}</span>
                </div>
                <div class="player-stats small">
                  <span class="dates">10th: ${d10}</span>
                  <span class="dates">30th: ${d30}</span>
                  <span class="dates">100th: ${d100}</span>
                </div>
                <div class="player-stats small">
                  <span class="gpd">GPD 7d: ${g7}</span>
                  <span class="gpd">30d: ${g30}</span>
                  <span class="gpd">90d: ${g90}</span>
                </div>
          </div>
        `;
      }
    });
  }
  
  html += '</div>';
  extendoPanel.innerHTML = html;
  
  // Add to page
  document.body.appendChild(extendoPanel);
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
  const nicknames = await getPlayerNicknamesWithBackoff(runId, { maxWaitMs: 60000, initialDelayMs: 2000, maxDelayMs: 8000 });
  console.log('Found players:', nicknames);

  if (nicknames.length === 0) {
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
      <div class="loading">Loading... Fetching data for ${nicknames.length} players...</div>
    </div>
  `;

  // Fetch and display stats
  const players = await fetchPlayerStats(nicknames);
  createStatsPanel(players);
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