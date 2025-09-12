#!/usr/bin/env python3
"""
Extendo Reborn - Test Version with Mock Data
Proves the concept works without needing real API keys
"""

import os
import time
from flask import Flask, request, jsonify
from flask_cors import CORS


# Mock FACEIT data for testing
MOCK_PLAYERS = {
    "s1mple": {
        "nickname": "s1mple",
        "player_id": "test-s1mple-id",
        "games": {"cs2": {"faceit_elo": 3200, "skill_level": 10}},
        "avatar": "https://example.com/avatar1.jpg",
        "country": "UA"
    },
    "ZywOo": {
        "nickname": "ZywOo",
        "player_id": "test-zywoo-id", 
        "games": {"cs2": {"faceit_elo": 3100, "skill_level": 10}},
        "avatar": "https://example.com/avatar2.jpg",
        "country": "FR"
    },
    "test_player": {
        "nickname": "test_player",
        "player_id": "test-player-id",
        "games": {"cs2": {"faceit_elo": 2000, "skill_level": 7}},
        "avatar": "https://example.com/avatar3.jpg",
        "country": "US"
    }
}

MOCK_STATS = {
    "test-s1mple-id": {
        "segments": [{
            "mode": "5v5",
            "stats": {
                "Matches": "150",
                "Wins": "120", 
                "K/D Ratio": "1.85",
                "Headshots %": "65.2",
                "Average Kills per Round": "0.92"
            }
        }]
    },
    "test-zywoo-id": {
        "segments": [{
            "mode": "5v5", 
            "stats": {
                "Matches": "200",
                "Wins": "165",
                "K/D Ratio": "1.78",
                "Headshots %": "58.1", 
                "Average Kills per Round": "0.88"
            }
        }]
    },
    "test-player-id": {
        "segments": [{
            "mode": "5v5",
            "stats": {
                "Matches": "50",
                "Wins": "30",
                "K/D Ratio": "1.12",
                "Headshots %": "45.5",
                "Average Kills per Round": "0.65"
            }
        }]
    }
}


class MockFaceitAPI:
    def __init__(self):
        print("🧪 Using MOCK FACEIT API for testing")
        print("🎯 This proves the concept works without real API keys")
    
    def get_player(self, nickname):
        """Mock player lookup with realistic delay"""
        time.sleep(0.1)  # Simulate network delay
        
        player = MOCK_PLAYERS.get(nickname.lower())
        if player:
            print(f"✅ Found mock player: {nickname}")
            return player
        else:
            print(f"❌ Mock player not found: {nickname}")
            return {"error": f"Player '{nickname}' not found in mock data"}
    
    def get_stats(self, player_id):
        """Mock stats lookup"""
        time.sleep(0.1)  # Simulate network delay
        
        stats = MOCK_STATS.get(player_id)
        if stats:
            print(f"✅ Found mock stats for: {player_id}")
            return stats
        else:
            print(f"❌ Mock stats not found for: {player_id}")
            return {"error": f"Stats not found for {player_id}"}


app = Flask(__name__)
CORS(app)
faceit = MockFaceitAPI()


@app.route("/players", methods=["POST"])
def get_players():
    """
    POST /players
    Body: {"nicknames": ["player1", "player2", ...]}
    Returns: [{"nickname": "player1", "elo": 2000, "level": 10, ...}, ...]
    """
    print(f"\n🎯 API Request received: {request.method} {request.path}")
    
    data = request.get_json()
    nicknames = data.get("nicknames", [])
    
    print(f"📝 Requested players: {nicknames}")
    
    if not nicknames:
        return {"error": "No nicknames provided"}, 400
    
    results = []
    for nickname in nicknames[:10]:  # Max 10 players
        print(f"\n🔍 Processing player: {nickname}")
        
        player = faceit.get_player(nickname)
        if "error" in player:
            print(f"❌ Error for {nickname}: {player['error']}")
            results.append({"nickname": nickname, "error": player["error"]})
            continue
        
        # Extract key info
        cs2_data = player.get("games", {}).get("cs2", {})
        result = {
            "nickname": player["nickname"],
            "player_id": player["player_id"],
            "elo": cs2_data.get("faceit_elo", 0),
            "level": cs2_data.get("skill_level", 0),
            "avatar": player.get("avatar", ""),
            "country": player.get("country", "")
        }
        
        # Get detailed stats
        stats = faceit.get_stats(player["player_id"])
        if "error" not in stats and stats.get("segments"):
            # Find overall stats
            overall = next((s for s in stats["segments"] if s.get("mode") == "5v5"), {})
            if overall and "stats" in overall:
                stats_data = overall["stats"]
                result.update({
                    "matches": int(stats_data.get("Matches", 0)),
                    "wins": int(stats_data.get("Wins", 0)),
                    "kd": float(stats_data.get("K/D Ratio", 0)),
                    "hs_percent": float(stats_data.get("Headshots %", 0)),
                    "avg_kills": float(stats_data.get("Average Kills per Round", 0))
                })
        
        print(f"✅ Successfully processed {nickname}: ELO {result.get('elo')}, Level {result.get('level')}")
        results.append(result)
    
    print(f"\n🎉 Returning {len(results)} player results")
    return jsonify(results)


@app.route("/health")
def health():
    print("❤️ Health check requested")
    return {"status": "ok", "message": "Extendo Reborn Test API is running!"}


@app.route("/")
def home():
    return {
        "message": "🎯 Extendo Reborn Test API",
        "status": "running",
        "endpoints": {
            "/health": "GET - Health check",
            "/players": "POST - Get player stats",
        },
        "test_players": list(MOCK_PLAYERS.keys()),
        "note": "This is a test version with mock data to prove the concept works"
    }


if __name__ == "__main__":
    print("\n" + "="*50)
    print("🎯 EXTENDO REBORN - TEST VERSION")
    print("="*50)
    print("✅ Using mock FACEIT data")
    print("✅ No API key required")
    print("✅ Ready to test the full concept")
    print(f"✅ Test players available: {', '.join(MOCK_PLAYERS.keys())}")
    print("="*50)
    
    app.run(debug=True, port=5000, host='0.0.0.0')