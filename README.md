# Extendo Reborn - The Minimal Version

## What This Is
4 files. 200 lines total. Does ONE thing: Shows FACEIT player stats in match rooms.

## Files
- `api.py` - Flask API (80 lines)
- `content.js` - Chrome extension logic (120 lines) 
- `manifest.json` - Extension config (10 lines)
- `style.css` - Basic styling (100 lines)

## Setup

### 1. Backend
```bash
cd extendo-reborn
pip install flask flask-cors requests
export FACEIT_API_KEY=your_key_here
python api.py
```

### 2. Chrome Extension
1. Open Chrome → Extensions → Developer mode
2. "Load unpacked" → Select `extendo-reborn` folder
3. Visit a FACEIT match room

## What It Does
1. ✅ Detects FACEIT match rooms automatically
2. ✅ Extracts player nicknames from page
3. ✅ Fetches basic stats (Elo, Level, K/D, Win Rate)
4. ✅ Shows clean popup with stats
5. ✅ Works on any FACEIT match room page

## What It Doesn't Do
- ❌ No demo parsing
- ❌ No MongoDB 
- ❌ No complex threading
- ❌ No authentication
- ❌ No advanced analytics
- ❌ No Docker

## The Point
This does 80% of what users need in 5% of the code.
Build THIS first. Add features later.

## Next Steps (if needed)
1. Add map-specific win rates
2. Add player match history
3. Add better error handling
4. Add caching with Redis

But only if users actually ask for it.