# Extendo Reborn - The Minimal Version

## What This Is
4 files. 412 lines total. Does ONE thing: Shows FACEIT player stats in match rooms.

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
4. ✅ ADR windows: last 10/30/100 matches + date when the Nth match occurred
5. ✅ Activity: games/day over last 7d/30d/90d windows
6. ✅ Shows clean popup with stats
5. ✅ Works on any FACEIT match room page

## What It Doesn't Do
- ❌ No demo parsing
- ❌ No MongoDB 
- ❌ No complex threading
- ❌ No authentication
- ❌ No advanced analytics
- ❌ No Docker

## The Point
Build THIS first. Add features later.

## Next Steps
1. ???


## Links
[compressing cs2 demos](https://healeycodes.com/compressing-cs2-demos)
[demoinfocs-golang](https://github.com/markus-wa/demoinfocs-golang)
