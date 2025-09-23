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
from dotenv import load_dotenv

load_dotenv()


class FaceitAPI:
    def __init__(self):
        self.api_key = os.getenv("FACEIT_API_KEY")
        if not self.api_key:
            raise ValueError("FACEIT_API_KEY required")
        
        # Open Data API session
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        })

    def _parse_response(self, resp):
        """Return (ok, data). On error, include auth_error if token invalid."""
        if resp.status_code == 200:
            try:
                return True, resp.json()
            except Exception:
                return True, {}
        try:
            data = resp.json()
        except Exception:
            data = {"message": resp.text}
        auth_err = (
            resp.status_code in (401, 403)
            or (isinstance(data, dict) and data.get("error") == "invalid_token")
        )
        err_msg = data.get("message") or data.get("error_description") or data.get("error") or resp.text
        return False, {"status": resp.status_code, "auth_error": auth_err, "error": err_msg}
    
    @lru_cache(maxsize=512)
    def get_player(self, nickname):
        """Get player by nickname with simple caching"""
        try:
            resp = self.session.get(
                f"https://open.faceit.com/data/v4/players",
                params={"nickname": nickname},
                timeout=5
            )
            ok, data = self._parse_response(resp)
            if ok:
                return data
            return {"error": f"FACEIT Data API {data.get('status')}: {data.get('error')}", "auth": data.get("auth_error", False)}
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
            ok, data = self._parse_response(resp)
            if ok:
                return data
            return {"error": f"FACEIT Data API {data.get('status')}: {data.get('error')}", "auth": data.get("auth_error", False)}
        except Exception as e:
            return {"error": str(e)}

    @lru_cache(maxsize=1024)
    def get_player_matches_stats_list(self, player_id: str, *, game_id: str = "cs2", offset: int = 0, limit: int = 100, from_ms: int | None = None, to_ms: int | None = None):
        """
        Call Data API: GET /players/{player_id}/games/{game_id}/stats
        Returns a dict { 'items': [...], 'start': n, 'end': m }

        Notes per official docs:
        - 'from'/'to' expect epoch milliseconds of "items.stats.Match Finished At".
        - limit max is 100.
        """
        try:
            params = {"offset": offset, "limit": limit}
            if from_ms is not None:
                params["from"] = int(from_ms)
            if to_ms is not None:
                params["to"] = int(to_ms)
            resp = self.session.get(
                f"https://open.faceit.com/data/v4/players/{player_id}/games/{game_id}/stats",
                params=params,
                timeout=8,
            )
            ok, data = self._parse_response(resp)
            if ok:
                # Ensure shape
                if not isinstance(data, dict):
                    return {"items": [], "start": 0, "end": 0}
                data.setdefault("items", [])
                data.setdefault("start", offset)
                data.setdefault("end", offset + len(data["items"]))
                return data
            return {"error": f"FACEIT Data API {data.get('status')}: {data.get('error')}", "auth": data.get("auth_error", False)}
        except Exception as e:
            return {"error": str(e)}

    def _avg_adr_from_items(self, items: list[dict], n: int) -> float | None:
        """
        Compute average ADR from the most recent n matches in items.
        Items are expected to be in descending recency, but we sort by 'Match Finished At' just in case.
        """
        try:
            # Extract (timestamp, ADR)
            pairs = []
            for it in items:
                s = it.get("stats", {}) if isinstance(it, dict) else {}
                adr_s = s.get("ADR")
                ts = s.get("Match Finished At") or s.get("Match Finished At ")
                if adr_s is None or ts is None:
                    continue
                try:
                    adr = float(str(adr_s).replace(",", "."))
                    tsi = int(ts)
                    pairs.append((tsi, adr))
                except Exception:
                    continue
            if not pairs:
                return None
            pairs.sort(key=lambda x: x[0], reverse=True)
            slice_vals = [adr for _, adr in pairs[:n]]
            if not slice_vals:
                return None
            return sum(slice_vals) / len(slice_vals)
        except Exception:
            return None

    def _nth_match_date(self, items: list[dict], n: int) -> int | None:
        """Return epoch ms for the Nth most recent match (e.g., n=10 for 10 games ago)."""
        try:
            matches = []
            for it in items:
                s = it.get("stats", {}) if isinstance(it, dict) else {}
                ts = s.get("Match Finished At") or s.get("Match Finished At ")
                if ts is None:
                    continue
                try:
                    matches.append(int(ts))
                except Exception:
                    continue
            if not matches:
                return None
            matches.sort(reverse=True)
            if len(matches) < n:
                # If fewer than n matches, use the oldest available
                return matches[-1]
            return matches[n - 1]
        except Exception:
            return None

    def count_matches_in_window(self, player_id: str, *, days: int, game_id: str = "cs2") -> int:
        """
        Count matches within the last `days` days using the per-match stats endpoint with from/to filters.
        Paginates until all matches are counted or no more results.
        """
        try:
            import time
            now_ms = int(time.time() * 1000)
            from_ms = now_ms - days * 24 * 60 * 60 * 1000
            total = 0
            offset = 0
            limit = 100
            while True:
                page = self.get_player_matches_stats_list(player_id, game_id=game_id, offset=offset, limit=limit, from_ms=from_ms, to_ms=now_ms)
                if "error" in page:
                    # On error, break to avoid infinite loop
                    break
                items = page.get("items", [])
                total += len(items)
                if len(items) < limit:
                    break
                offset += limit
            return total
        except Exception:
            return 0
    
    @lru_cache(maxsize=512)
    def get_match(self, match_id):
        """Get match details from FACEIT Data API (v4): /matches/{match_id}.
        Note: This requires a valid match_id known to the Data API. "room" IDs
        that are not yet matches will not be available here.
        """
        try:
            resp = self.session.get(
                f"https://open.faceit.com/data/v4/matches/{match_id}",
                timeout=5,
            )
            ok, data = self._parse_response(resp)
            if ok:
                return {"source": "matches", **data}
            if data.get("auth_error"):
                return {"error": f"FACEIT Data API {data.get('status')}: {data.get('error')}", "auth": True}
            # If not found or not yet promoted, attempt documented matchmaking endpoint
            mm_resp = self.session.get(
                f"https://open.faceit.com/data/v4/matchmakings/{match_id}",
                timeout=5,
            )
            mm_ok, mm_data = self._parse_response(mm_resp)
            if mm_ok:
                return {"source": "matchmakings", **mm_data}
            if mm_data.get("auth_error"):
                return {"error": f"FACEIT Data API {mm_data.get('status')}: {mm_data.get('error')}", "auth": True}
            # Propagate a concise error consistent with Data API responses
            return {"error": (
                f"FACEIT Data API matches {data.get('status')}: {data.get('error')}; "
                f"matchmakings {mm_data.get('status')}: {mm_data.get('error')}"
            )}
        except Exception as e:
            return {"error": str(e)}


app = Flask(__name__)
CORS(app)
faceit = FaceitAPI()


@app.route("/match/<match_id>/players", methods=["GET"])
def get_match_players(match_id):
    """
    GET /match/{match_id}/players
    Returns: {"nicknames": ["player1", "player2", ...], "teams": {...}}
    """
    match_data = faceit.get_match(match_id)
    
    if "error" in match_data:
        status = 401 if match_data.get("auth") else 400
        return {"error": match_data["error"], "auth": match_data.get("auth", False)}, status
    
    # Extract player nicknames from match data (support multiple schemas)
    nicknames = []
    teams = {"team1": {"name": "", "players": []}, "team2": {"name": "", "players": []}}

    try:
        data = match_data.get("payload", match_data)

        def add_team(idx, name, roster_list):
            key = "team1" if idx == 0 else "team2"
            tplayers = []
            for p in roster_list:
                # Support different player key names
                nickname = p.get("nickname") or p.get("nick") or p.get("name") or ""
                pid = p.get("player_id") or p.get("id") or p.get("guid") or ""
                avatar = p.get("avatar") or p.get("picture") or ""
                if nickname:
                    if nickname not in nicknames:
                        nicknames.append(nickname)
                    tplayers.append({"nickname": nickname, "player_id": pid, "avatar": avatar})
            teams[key] = {"name": name or key, "players": tplayers}

        # Case A: Open Data API style { teams: { faction1: {...}, faction2: {...} } }
        if isinstance(data.get("teams"), dict):
            ordered = []
            for key in ("faction1", "faction2"):
                if key in data["teams"]:
                    ordered.append(data["teams"][key])
            if not ordered:
                # any dict values
                ordered = list(data["teams"].values())
            for i, t in enumerate(ordered[:2]):
                roster = t.get("roster") or t.get("players") or []
                add_team(i, t.get("name", ""), roster)

        # Case B: Alternative list format { teams: [ { name, roster:[...] }, { ... } ] }
        elif isinstance(data.get("teams"), list):
            for i, t in enumerate(data["teams"][:2]):
                roster = t.get("roster") or t.get("players") or []
                add_team(i, t.get("name", ""), roster)

        # Case C: Nested under data.match or data.room etc.
        elif isinstance(data.get("match"), dict) and isinstance(data["match"].get("teams"), list):
            for i, t in enumerate(data["match"]["teams"][:2]):
                roster = t.get("roster") or t.get("players") or []
                add_team(i, t.get("name", ""), roster)

        result = {
            "nicknames": nicknames,
            "teams": teams,
            "match_id": match_id,
            "status": data.get("status") or data.get("state") or "unknown",
        }

        if not nicknames:
            # Provide more context to the caller instead of a silent empty list
            result["warning"] = "No players found in match data"
        return result

    except Exception as e:
        return {"error": f"Failed to parse match data: {str(e)}"}, 500


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

        # Enrich with ADR last 10/30/100 and dates for nth matches using per-match stats endpoint
        try:
            recent_100 = faceit.get_player_matches_stats_list(player_id=result["player_id"], game_id="cs2", offset=0, limit=100)
            if "error" not in recent_100:
                items = recent_100.get("items", [])
                adr10 = faceit._avg_adr_from_items(items, 10)
                adr30 = faceit._avg_adr_from_items(items, 30)
                adr100 = faceit._avg_adr_from_items(items, 100)
                d10 = faceit._nth_match_date(items, 10)
                d30 = faceit._nth_match_date(items, 30)
                d100 = faceit._nth_match_date(items, 100)
                if adr10 is not None:
                    result["adr_last_10"] = round(adr10, 2)
                if adr30 is not None:
                    result["adr_last_30"] = round(adr30, 2)
                if adr100 is not None:
                    result["adr_last_100"] = round(adr100, 2)
                # Convert ms epoch to ISO date (YYYY-MM-DD)
                import datetime as _dt
                def _to_date(ms):
                    try:
                        return _dt.datetime.utcfromtimestamp(ms/1000).strftime('%Y-%m-%d') if ms else None
                    except Exception:
                        return None
                result["date_10_games_ago"] = _to_date(d10)
                result["date_30_games_ago"] = _to_date(d30)
                result["date_100_games_ago"] = _to_date(d100)
        except Exception:
            # Non-fatal: keep minimal result
            pass

        # Games per day for last 7/30/90 days using time-bounded stats list counts
        try:
            c7 = faceit.count_matches_in_window(result["player_id"], days=7)
            c30 = faceit.count_matches_in_window(result["player_id"], days=30)
            c90 = faceit.count_matches_in_window(result["player_id"], days=90)
            result["games_per_day_7d"] = round(c7 / 7.0, 2)
            result["games_per_day_30d"] = round(c30 / 30.0, 2)
            result["games_per_day_90d"] = round(c90 / 90.0, 2)
        except Exception:
            pass
        
        results.append(result)
    
    return jsonify(results)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=5000)