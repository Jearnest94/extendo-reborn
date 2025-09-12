#!/usr/bin/env python3
"""
Extendo Reborn - Minimal FACEIT stats API
ONE job: Get player stats fast
"""

import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import lru_cache


class FaceitAPI:
    def __init__(self):
        self.api_key = os.getenv("FACEIT_API_KEY")
        if not self.api_key:
            raise ValueError("FACEIT_API_KEY required")
        
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
    
    @lru_cache(maxsize=512)
    def get_player(self, nickname):
        """Get player by nickname with simple caching"""
        try:
            resp = self.session.get(
                f"https://open.faceit.com/data/v4/players",
                params={"nickname": nickname},
                timeout=5
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    @lru_cache(maxsize=512)
    def get_stats(self, player_id):
        """Get CS2 stats for player"""
        try:
            resp = self.session.get(
                f"https://open.faceit.com/data/v4/players/{player_id}/stats/cs2",
                timeout=5
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}


app = Flask(__name__)
CORS(app)
faceit = FaceitAPI()


@app.route("/players", methods=["POST"])
def get_players():
    """
    POST /players
    Body: {"nicknames": ["player1", "player2", ...]}
    Returns: [{"nickname": "player1", "elo": 2000, "level": 10, ...}, ...]
    """
    data = request.get_json()
    nicknames = data.get("nicknames", [])
    
    if not nicknames:
        return {"error": "No nicknames provided"}, 400
    
    results = []
    for nickname in nicknames[:10]:  # Max 10 players
        player = faceit.get_player(nickname)
        if "error" in player:
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
        
        # Get detailed stats if possible
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
        
        results.append(result)
    
    return jsonify(results)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=5000)