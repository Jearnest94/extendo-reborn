/*
 * Extendo Reborn - ONE JOB: Show player stats in FACEIT match rooms
 */

let extendoPanel = null;

// Simple function to extract player nicknames from FACEIT match room
function getPlayerNicknames() {
  // Look for player nickname elements in the roster
  const playerElements = document.querySelectorAll('[data-testid*="roster"] .text-truncate, .roster .text-truncate, [class*="nickname"], [class*="player-nickname"]');
  
  const nicknames = [];
  playerElements.forEach(el => {
    const text = el.textContent.trim();
    if (text && text.length > 2 && text.length < 20 && !nicknames.includes(text)) {
      nicknames.push(text);
    }
  });
  
  // Fallback: look for any elements that might contain player names
  if (nicknames.length === 0) {
    const allElements = document.querySelectorAll('*');
    allElements.forEach(el => {
      if (el.children.length === 0) { // Only leaf elements
        const text = el.textContent.trim();
        if (text.match(/^[a-zA-Z0-9_-]{3,16}$/) && !nicknames.includes(text)) {
          nicknames.push(text);
        }
      }
    });
  }
  
  return nicknames.slice(0, 10); // Max 10 players
}

// Check if we're in a match room
function isMatchRoom() {
  return window.location.href.includes('/room/') || 
         document.querySelector('[data-testid*="roster"]') ||
         document.querySelector('.roster') ||
         getPlayerNicknames().length >= 5; // If we found players, probably a match room
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
        html += `
          <div class="player-card">
            <div class="player-name">${player.nickname}</div>
            <div class="player-stats">
              <span class="elo">⭐ ${player.elo}</span>
              <span class="level">Lvl ${player.level}</span>
              <span class="kd">K/D: ${player.kd || 'N/A'}</span>
              <span class="winrate">Win: ${winRate}%</span>
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
  
  const nicknames = getPlayerNicknames();
  console.log('Found players:', nicknames);
  
  if (nicknames.length === 0) {
    console.log('No players found');
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