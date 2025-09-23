# Extendo Reborn - The Minimal Version

## What This Is
4 files. ~420 lines total. Does ONE thing: Shows FACEIT player stats in match rooms.

## Files
- `api.py` - Flask API with caching (113 lines)
- `content.js` - Chrome extension logic (169 lines) 
- `manifest.json` - Extension config (14 lines)
- `style.css` - Basic styling (116 lines)

## Setup

### 1. Backend
```bash
cd extendo-reborn
pip install flask flask-cors requests python-dotenv
export FACEIT_API_KEY=your_key_here
python api.py
```

Windows (PowerShell):
```pwsh
cd extendo-reborn
pip install flask flask-cors requests python-dotenv
$env:FACEIT_API_KEY="your_key_here"
python api.py
```

Or put your key in a local .env file (auto-loaded):
```
FACEIT_API_KEY=your_key_here
```

### 2. Chrome Extension
1. Open Chrome → Extensions → Developer mode
2. "Load unpacked" → Select `extendo-reborn` folder
3. Visit a FACEIT match room
4. Extension auto-detects and shows player stats

## What It Does
1. ✅ Detects FACEIT match rooms automatically
2. ✅ Fetches match players via the official FACEIT Data API
3. ✅ Fetches basic stats (Elo, Level, K/D, Win Rate)
4. ✅ Shows clean popup with stats
5. ✅ Works on any FACEIT match room page
6. ✅ Accurate historical Elo windows (E10/E30/E100) via web API time-series with on-disk cache
7. ✅ Top maps (Most Played & Best WR) up to 7, with WR-based color/bold pairing across rows
8. ✅ Peak Elo (All-Time) and the date achieved

## What It Doesn't Do
- ❌ No demo parsing
- ❌ No MongoDB 
- ❌ No complex threading
- ❌ No authentication
- ❌ No advanced analytics
- ❌ No Docker


## Next Steps
1. Minimal knobs (env var) for API host
2. Optional: cache-busting/expiry

## API Response (minimal)
`POST /players` request body:

```
{ "nicknames": ["player1", "player2"] }
```

`200 OK` response (per player fields):

```
{
	nickname, player_id, elo, level, avatar, country,
	matches, wins, kd,
	adr_last_10, adr_last_30, adr_last_100,
	date_10_games_ago, date_30_games_ago, date_100_games_ago, // YYYY-MM-DD (UTC)
	games_per_day_7d, games_per_day_30d, games_per_day_90d,
	elo_10_games_ago, elo_30_games_ago, elo_100_games_ago,
	top_maps_played: [{ label, matches, wr }...],
	top_maps_wr: [{ label, matches, wr }...],
	top_elo_all_time, // integer peak Elo observed
	top_elo_date // YYYY-MM-DD (UTC)
}
```

## Links
[compressing cs2 demos](https://healeycodes.com/compressing-cs2-demos)
[demoinfocs-golang](https://github.com/markus-wa/demoinfocs-golang)
