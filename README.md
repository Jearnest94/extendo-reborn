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
pip install flask flask-cors requests
export FACEIT_API_KEY=your_key_here
python api.py
```

### 2. Chrome Extension
1. Open Chrome → Extensions → Developer mode
2. "Load unpacked" → Select `extendo-reborn` folder
3. Visit a FACEIT match room
4. Extension auto-detects and shows player stats

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
Build THIS first. Add features later.

## Next Steps
1. Read https://healeycodes.com/ writeups such as [compressing cs2 demos](https://healeycodes.com/compressing-cs2-demos)
https://github.com/markus-wa/demoinfocs-golang
2. Try to make demoparsing really really fast. 
Because: We don't have a humongous database of ready-parsed player data for every single Faceit player
And the situation: That from the point in time where we know which Players we want to analyze AND on which Map to analyze them on, we've got ~2-3 minutes to produce results before the knife round has started.
This means we need to: Download demo(s), +Parse demo(s) *and* Produce actually useful enemy player pattern data (f.e. Plot showing enemy player "Shoguun" plays AWP on this position on CT-Side) 
4. 
5. Figure out what data we can produce that actually gives a competetive advantage (This player "ABDI" plays AWP on x position CT-Side)
6. Add caching with Redis

But only if users actually ask for it.
