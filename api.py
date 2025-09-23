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

        # Public Web API session (used by faceit.com frontend). No auth header.
        # Some endpoints expose per-match Elo time series we need for historical values.
        self.web = requests.Session()
        self.web.headers.update({
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.faceit.com/",
            "Origin": "https://www.faceit.com",
        })

        # On-disk cache for Elo time-series to reduce web calls and support offline
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.elo_cache_dir = os.path.join(base_dir, ".cache", "elo")
        try:
            os.makedirs(self.elo_cache_dir, exist_ok=True)
        except Exception:
            pass

        # Peak Elo cache
        self.peak_cache_dir = os.path.join(base_dir, ".cache", "peak")
        try:
            os.makedirs(self.peak_cache_dir, exist_ok=True)
        except Exception:
            pass

    @staticmethod
    def _to_unix_seconds(value: int | float | str | None) -> int | None:
        """
        Normalize a timestamp value to UNIX seconds.
        Accepts seconds or milliseconds; detects by magnitude (> 10^12 => ms).
        Returns None if input is falsy or cannot be parsed.
        """
        if value is None:
            return None
        try:
            iv = int(value)
        except Exception:
            return None
        # If it's clearly in milliseconds, convert to seconds
        if iv > 10**12:
            return iv // 1000
        return iv

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
        - Endpoint supports pagination via 'offset' and 'limit'.
        - Response items include per-match player_stats keys which are game-defined (not enumerated);
          for CS2 these typically include 'ADR'.
        """
        try:
            params = {"offset": offset, "limit": limit}
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

    @lru_cache(maxsize=1024)
    def get_player_history(self, player_id: str, *, game_id: str = "cs2", offset: int = 0, limit: int = 100, from_ms: int | None = None, to_ms: int | None = None):
        """
        Call Data API: GET /players/{player_id}/history
        Query params: game (required), from/to (epoch ms, optional), offset, limit
        Returns a dict { 'items': [...], 'start': n, 'end': m }
        Each item includes fields like 'match_id', 'finished_at' (epoch ms), etc.
        """
        try:
            params = {"game": game_id, "offset": offset, "limit": limit}
            # FACEIT docs: 'from'/'to' are UNIX time (seconds). Convert if ms provided.
            if from_ms is not None:
                fsec = self._to_unix_seconds(from_ms)
                if fsec is not None:
                    params["from"] = fsec
            if to_ms is not None:
                tsec = self._to_unix_seconds(to_ms)
                if tsec is not None:
                    params["to"] = tsec
            resp = self.session.get(
                f"https://open.faceit.com/data/v4/players/{player_id}/history",
                params=params,
                timeout=8,
            )
            ok, data = self._parse_response(resp)
            if ok:
                if not isinstance(data, dict):
                    return {"items": [], "start": 0, "end": 0}
                data.setdefault("items", [])
                data.setdefault("start", offset)
                # Many list endpoints also return 'end' in body; if not, synthesize it
                data.setdefault("end", offset + len(data["items"]))
                return data
            return {"error": f"FACEIT Data API {data.get('status')}: {data.get('error')}", "auth": data.get("auth_error", False)}
        except Exception as e:
            return {"error": str(e)}

    def _avg_adr_from_items(self, items: list[dict], n: int) -> float | None:
        """
        Compute average ADR from the most recent n matches in items.
        Items are expected to be in descending recency. When timestamps are present as stats fields,
        we sort by them; otherwise we assume the API returns newest-first.
        """
        try:
            # Extract (timestamp, ADR)
            pairs = []
            for it in items:
                s = it.get("stats", {}) if isinstance(it, dict) else {}
                adr_s = s.get("ADR")
                # Prefer explicit timestamp if exposed in stats; fall back to None
                ts = s.get("Match Finished At") or s.get("Match Finished At ") or s.get("played")
                if adr_s is None or ts is None:
                    # If no timestamp in stats, still consider ADR but use a decreasing counter to keep order
                    try:
                        adr = float(str(adr_s).replace(",", "."))
                        pairs.append((None, adr))
                    except Exception:
                        continue
                    continue
                try:
                    adr = float(str(adr_s).replace(",", "."))
                    tsi = int(ts)
                    pairs.append((tsi, adr))
                except Exception:
                    continue
            if not pairs:
                return None
            # If timestamps exist, sort by ts desc; otherwise keep input order
            if any(p[0] is not None for p in pairs):
                pairs = [p for p in pairs if p[0] is not None]
                pairs.sort(key=lambda x: x[0], reverse=True)
            slice_vals = [adr for _, adr in pairs[:n]]
            if not slice_vals:
                return None
            return sum(slice_vals) / len(slice_vals)
        except Exception:
            return None

    def _win_rate_from_items(self, items: list[dict], n: int) -> float | None:
        """Compute win rate percentage over the most recent n items from per-match stats list.
        Tries to detect a win/lose indicator from stats fields like 'Result', 'Result with overtime', 'Outcome'.
        """
        try:
            # Build (timestamp, is_win) list
            rows: list[tuple[int | None, bool]] = []
            for it in items:
                s = it.get("stats", {}) if isinstance(it, dict) else {}
                if not isinstance(s, dict):
                    continue
                # detect win keywords
                def _is_win_val(v):
                    if v is None:
                        return None
                    sv = str(v).strip().lower()
                    if sv in ("win", "won", "victory", "1", "true", "yes"):
                        return True
                    if sv in ("loss", "lose", "defeat", "0", "false", "no"):
                        return False
                    # If contains word win
                    if "win" in sv or "victor" in sv:
                        return True
                    if "loss" in sv or "defeat" in sv or "lose" in sv:
                        return False
                    return None
                is_win = None
                for key in ("Result", "Result with overtime", "Outcome", "Match Result", "Win"):
                    if key in s:
                        is_win = _is_win_val(s.get(key))
                        if is_win is not None:
                            break
                # Fallback: some payloads might have 'i18n_result' etc. Skip if unknown
                if is_win is None:
                    continue
                ts = s.get("Match Finished At") or s.get("Match Finished At ") or s.get("played")
                try:
                    tsi = int(ts) if ts is not None else None
                except Exception:
                    tsi = None
                rows.append((tsi, bool(is_win)))
            if not rows:
                return None
            if any(r[0] is not None for r in rows):
                rows = [r for r in rows if r[0] is not None]
                rows.sort(key=lambda x: x[0], reverse=True)
            slice_rows = rows[:n]
            if not slice_rows:
                return None
            wins = sum(1 for _, w in slice_rows if w)
            return (wins / len(slice_rows)) * 100.0
        except Exception:
            return None

    def _elo_at_n_from_items(self, items: list[dict], n: int) -> int | None:
        """Attempt to retrieve the player's Elo value at the Nth most recent match from per-match stats items.
        This relies on a per-item 'stats' key whose name includes 'elo' (case-insensitive). If absent, return None.
        """
        try:
            rows: list[tuple[int | None, int]] = []
            for it in items:
                s = it.get("stats", {}) if isinstance(it, dict) else {}
                if not isinstance(s, dict):
                    continue
                # find an elo-like field
                elo_val = None
                for k, v in s.items():
                    if isinstance(k, str) and "elo" in k.lower():
                        try:
                            elo_val = int(float(str(v).replace(",", ".")))
                            break
                        except Exception:
                            continue
                if elo_val is None:
                    continue
                ts = s.get("Match Finished At") or s.get("Match Finished At ") or s.get("played")
                try:
                    tsi = int(ts) if ts is not None else None
                except Exception:
                    tsi = None
                rows.append((tsi, elo_val))
            if not rows:
                return None
            if any(r[0] is not None for r in rows):
                rows = [r for r in rows if r[0] is not None]
                rows.sort(key=lambda x: x[0], reverse=True)
            if len(rows) < n:
                idx = len(rows) - 1
            else:
                idx = n - 1
            if idx < 0:
                return None
            return rows[idx][1]
        except Exception:
            return None

    @lru_cache(maxsize=1024)
    def get_web_time_stats(self, player_id: str, game_id: str = "cs2") -> list[dict]:
        """
        FACEIT Web API (used by faceit.com):
        GET https://api.faceit.com/stats/v1/stats/time/users/{player_id}/games/{game_id}
        Observed to return a list of (date, elo, ...). Undocumented limits may cap length.
        We attempt multiple strategies to retrieve as much history as possible:
        - bare call (no params)
        - large size/limit param
        - simple pagination attempts using page/offset with a conservative page count
        """
        try:
            base = f"https://api.faceit.com/stats/v1/stats/time/users/{player_id}/games/{game_id}"
            def fetch(params: dict | None = None) -> list[dict]:
                try:
                    resp = self.web.get(base, params=params or {}, timeout=10)
                    if resp.status_code != 200:
                        return []
                    data = resp.json()
                    return data if isinstance(data, list) else []
                except Exception:
                    return []

            # Collect pages with different strategies, then merge/dedup
            collected: list[list[dict]] = []
            # 1) bare
            collected.append(fetch())
            # 2) with large size/limit
            for k in ("size", "limit"):
                collected.append(fetch({k: 5000}))
            # 3) paginate with page or offset (try a few pages conservatively)
            for k in ("page", "offset"):
                for p in range(0, 5):  # up to 5 pages to avoid abuse
                    if k == "offset":
                        params = {k: p * 1000, "size": 1000}
                    else:
                        params = {k: p, "size": 1000}
                    lst = fetch(params)
                    if not lst:
                        break
                    collected.append(lst)
                    # Heuristic: if returned less than requested size, likely last page
                    if len(lst) < params.get("size", 1000):
                        break

            # Merge all and dedup via existing merge helper
            merged = []
            for lst in collected:
                merged = self._merge_elo_items(merged, lst)
            return merged
        except Exception:
            return []

    def _elo_at_n_from_web(self, web_items: list[dict], n: int) -> int | None:
        """Get Elo at the Nth most recent match from FACEIT web time stats list.
        Sorts by 'date' desc (epoch ms). Returns None if missing or insufficient.
        """
        try:
            rows: list[tuple[int, int]] = []
            for it in web_items:
                if not isinstance(it, dict):
                    continue
                elo = it.get("elo")
                dt = it.get("date") or it.get("created_at") or it.get("updated_at")
                if elo is None or dt is None:
                    continue
                try:
                    elo_i = int(elo)
                    ts = int(dt)
                    # normalize to ms if needed
                    if ts < 10**12:
                        ts *= 1000
                    rows.append((ts, elo_i))
                except Exception:
                    continue
            if not rows:
                return None
            rows.sort(key=lambda x: x[0], reverse=True)
            idx = n - 1
            if idx < 0:
                return None
            if idx >= len(rows):
                idx = len(rows) - 1
            return rows[idx][1]
        except Exception:
            return None

    def _peak_elo_from_web(self, web_items: list[dict]) -> tuple[int | None, int | None]:
        """Return (max_elo, when_ms) from FACEIT web time stats list.
        If multiple entries share the max elo, prefer the most recent by date.
        Date is returned as epoch milliseconds.
        """
        try:
            peak_elo = None
            peak_ts = None
            for it in web_items:
                if not isinstance(it, dict):
                    continue
                elo = it.get("elo")
                dt = it.get("date") or it.get("created_at") or it.get("updated_at")
                if elo is None or dt is None:
                    continue
                try:
                    e = int(elo)
                    ts = int(dt)
                    if ts < 10**12:
                        ts *= 1000
                except Exception:
                    continue
                if peak_elo is None or e > peak_elo or (e == peak_elo and (peak_ts is None or ts > peak_ts)):
                    peak_elo = e
                    peak_ts = ts
            return peak_elo, peak_ts
        except Exception:
            return None, None

    # ---- Disk cache helpers for Elo time-series ----
    def _elo_cache_path(self, player_id: str) -> str:
        safe_id = str(player_id)
        return os.path.join(self.elo_cache_dir, f"{safe_id}.json")

    def _read_elo_cache(self, player_id: str) -> dict:
        path = self._elo_cache_path(player_id)
        try:
            if os.path.exists(path):
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("updated_at", 0)
                    data.setdefault("items", [])
                    return data
        except Exception:
            pass
        return {"updated_at": 0, "items": []}

    def _write_elo_cache(self, player_id: str, items: list[dict]):
        path = self._elo_cache_path(player_id)
        try:
            import json, time
            payload = {"updated_at": int(time.time()), "items": items}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            pass

    def _merge_elo_items(self, a: list[dict], b: list[dict]) -> list[dict]:
        """Merge two lists of web elo items, dedup by matchId (fallback date), keep latest by date."""
        def key_of(it: dict):
            mid = it.get("matchId")
            if not mid and isinstance(it.get("_id"), dict):
                mid = it["_id"].get("matchId")
            if mid:
                return ("m", str(mid))
            dt = it.get("date") or it.get("created_at") or it.get("updated_at") or 0
            elo = it.get("elo") or 0
            return ("d", f"{dt}:{elo}")

        merged = {}
        for lst in (a or []), (b or []):
            for it in lst:
                if not isinstance(it, dict):
                    continue
                k = key_of(it)
                # choose the one with newer date
                old = merged.get(k)
                if old is None:
                    merged[k] = it
                else:
                    old_dt = old.get("date") or old.get("created_at") or old.get("updated_at") or 0
                    new_dt = it.get("date") or it.get("created_at") or it.get("updated_at") or 0
                    if int(new_dt or 0) >= int(old_dt or 0):
                        merged[k] = it
        items = list(merged.values())
        # sort desc by date
        items.sort(key=lambda it: int(it.get("date") or it.get("created_at") or it.get("updated_at") or 0), reverse=True)
        return items

    def get_web_time_stats_cached(self, player_id: str, game_id: str = "cs2", ttl_seconds: int = 600, max_items: int = 10000) -> list[dict]:
        """
        Return elo time-series using disk cache with TTL and merge.
        - If cache is fresh (updated_at within ttl_seconds), return cache.
        - Else fetch web list; if success, merge into cache, prune to max_items, write and return.
        - If fetch fails, return cache (even if stale) to support offline.
        """
        import time
        cached = self._read_elo_cache(player_id)
        now = int(time.time())
        if cached.get("updated_at", 0) and (now - int(cached["updated_at"])) <= max(ttl_seconds, 0):
            return cached.get("items", [])
        web_list = self.get_web_time_stats(player_id, game_id)
        if web_list:
            merged = self._merge_elo_items(cached.get("items", []), web_list)
            if len(merged) > max_items:
                merged = merged[:max_items]
            self._write_elo_cache(player_id, merged)
            return merged
        # No web data; return whatever we have
        return cached.get("items", [])

    # ---- Peak Elo via per-match stats fallback and caching ----
    def _peak_cache_path(self, player_id: str) -> str:
        return os.path.join(self.peak_cache_dir, f"{player_id}.json")

    def _read_peak_cache(self, player_id: str) -> dict:
        path = self._peak_cache_path(player_id)
        try:
            if os.path.exists(path):
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("updated_at", 0)
                    return data
        except Exception:
            pass
        return {"updated_at": 0}

    def _write_peak_cache(self, player_id: str, peak_elo: int | None, peak_ts_ms: int | None):
        path = self._peak_cache_path(player_id)
        try:
            import json, time
            payload = {"updated_at": int(time.time()), "peak_elo": peak_elo, "peak_ts_ms": peak_ts_ms}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            pass

    def _peak_elo_from_items(self, items: list[dict]) -> tuple[int | None, int | None]:
        """Scan per-match stats items for the highest Elo-like value, return (elo, ts_ms)."""
        best_e = None
        best_ts = None
        try:
            for it in items:
                s = it.get("stats", {}) if isinstance(it, dict) else {}
                if not isinstance(s, dict):
                    continue
                # Timestamp from stats
                ts = s.get("Match Finished At") or s.get("Match Finished At ") or s.get("played")
                try:
                    tsi = int(ts) if ts is not None else None
                except Exception:
                    tsi = None
                # Find elo-like field
                elo_val = None
                for k, v in s.items():
                    if isinstance(k, str) and "elo" in k.lower():
                        try:
                            elo_val = int(float(str(v).replace(",", ".")))
                            break
                        except Exception:
                            continue
                if elo_val is None:
                    continue
                # Normalize ts to ms
                if tsi is not None and tsi < 10**12:
                    tsi *= 1000
                if best_e is None or elo_val > best_e or (elo_val == best_e and (best_ts is None or (tsi or 0) > (best_ts or 0))):
                    best_e = elo_val
                    best_ts = tsi
        except Exception:
            pass
        return best_e, best_ts

    def get_peak_elo_all_time(self, player_id: str, *, game_id: str = "cs2", ttl_seconds: int = 43200, max_pages: int = 30, page_size: int = 100) -> tuple[int | None, int | None]:
        """Return true all-time peak Elo by combining web time-series peak with a paginated scan of per-match stats.
        Caches result on disk with TTL; refreshes if stale or current elo likely exceeds cached peak.
        Returns (peak_elo, peak_ts_ms).
        """
        import time
        cached = self._read_peak_cache(player_id)
        now = int(time.time())
        if cached.get("updated_at", 0) and (now - int(cached["updated_at"])) <= max(ttl_seconds, 0):
            return cached.get("peak_elo"), cached.get("peak_ts_ms")

        # 1) From web time-series
        web_items = self.get_web_time_stats_cached(player_id, game_id=game_id, ttl_seconds=600, max_items=10000)
        web_peak_e, web_peak_ts = self._peak_elo_from_web(web_items)

        # 2) From per-match stats (paginated scan)
        best_e = web_peak_e
        best_ts = web_peak_ts
        offset = 0
        pages = 0
        while pages < max_pages:
            page = self.get_player_matches_stats_list(player_id=player_id, game_id=game_id, offset=offset, limit=page_size)
            if "error" in page:
                break
            items = page.get("items", [])
            if not items:
                break
            e, ts = self._peak_elo_from_items(items)
            if e is not None:
                if best_e is None or e > best_e or (e == best_e and (best_ts is None or (ts or 0) > (best_ts or 0))):
                    best_e = e
                    best_ts = ts
            if len(items) < page_size:
                break
            offset += page_size
            pages += 1

        self._write_peak_cache(player_id, best_e, best_ts)
        return best_e, best_ts

    def _nth_match_date_from_history(self, items: list[dict], n: int) -> int | None:
        """Return epoch ms for the Nth most recent match using /players/{player_id}/history items."""
        try:
            stamps = []
            for it in items:
                ts = None
                if isinstance(it, dict):
                    ts = it.get("finished_at") or it.get("ended_at") or it.get("started_at")
                if ts is None:
                    continue
                try:
                    # Normalize to seconds for consistency
                    s = self._to_unix_seconds(ts)
                    if s is not None:
                        stamps.append(s)
                except Exception:
                    continue
            if not stamps:
                return None
            stamps.sort(reverse=True)
            if len(stamps) < n:
                return stamps[-1]
            return stamps[n - 1]
        except Exception:
            return None

    def count_matches_in_window(self, player_id: str, *, days: int, game_id: str = "cs2") -> int:
        """
        Count matches within the last `days` days using the documented player history endpoint
        with from/to time filters. Paginates until all matches are counted or no more results.
        """
        try:
            import time
            # Use seconds for history params
            now_s = int(time.time())
            from_s = now_s - days * 24 * 60 * 60
            total = 0
            offset = 0
            limit = 100
            while True:
                page = self.get_player_history(player_id, game_id=game_id, offset=offset, limit=limit, from_ms=from_s, to_ms=now_s)
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
                # Prefer 'Average K/D Ratio' for KD; 'K/D Ratio' often represents an aggregated scaled value in lifetime payloads
                kd_val = stats_data.get("Average K/D Ratio")
                if kd_val is None:
                    kd_val = stats_data.get("K/D Ratio")
                try:
                    kd_val = float(kd_val)
                except Exception:
                    kd_val = 0.0
                result.update({
                    "matches": int(stats_data.get("Matches", 0)),
                    "wins": int(stats_data.get("Wins", 0)),
                    "kd": kd_val,
                    "hs_percent": float(stats_data.get("Headshots %", 0)),
                    "avg_kills": float(stats_data.get("Average Kills per Round", 0))
                })

            # Compute top maps (most played and best win rate) from map segments
            try:
                map_rows = []
                for seg in stats.get("segments", []):
                    if not isinstance(seg, dict):
                        continue
                    # Only Map segments for 5v5 mode
                    if str(seg.get("type", "")).lower() != "map":
                        continue
                    if str(seg.get("mode", "")).lower() != "5v5":
                        continue
                    sdat = seg.get("stats", {})
                    if not isinstance(sdat, dict):
                        continue
                    label = seg.get("label") or seg.get("name") or ""
                    if not label:
                        continue
                    # parse matches and win rate
                    matches_s = sdat.get("Matches") or sdat.get("Total Matches") or 0
                    wr_s = sdat.get("Win Rate %") or 0
                    try:
                        matches_i = int(str(matches_s).split(".")[0])
                    except Exception:
                        matches_i = 0
                    try:
                        wr_f = float(str(wr_s).replace(",", "."))
                    except Exception:
                        wr_f = 0.0
                    # Skip maps with zero matches
                    if matches_i <= 0:
                        continue
                    map_rows.append({"label": label, "matches": matches_i, "wr": wr_f})
                if map_rows:
                    most_played = sorted(map_rows, key=lambda r: (r["matches"], r["wr"]), reverse=True)[:7]
                    best_wr = sorted(map_rows, key=lambda r: (r["wr"], r["matches"]), reverse=True)[:7]
                    result["top_maps_played"] = most_played
                    result["top_maps_wr"] = best_wr
            except Exception:
                pass

        # Enrich with ADR last 10/30/100 and dates for nth matches using per-match stats endpoint
        try:
            # Prefer robust Elo history from cached web time stats (if available)
            web_items = faceit.get_web_time_stats_cached(result["player_id"], "cs2", ttl_seconds=600, max_items=800)
            if web_items:
                e10w = faceit._elo_at_n_from_web(web_items, 10)
                e30w = faceit._elo_at_n_from_web(web_items, 30)
                e100w = faceit._elo_at_n_from_web(web_items, 100)
                if e10w is not None:
                    result["elo_10_games_ago"] = e10w
                if e30w is not None:
                    result["elo_30_games_ago"] = e30w
                if e100w is not None:
                    result["elo_100_games_ago"] = e100w
            # True all-time peak Elo (web series + paginated fallback)
            peak_elo, peak_ms = faceit.get_peak_elo_all_time(result["player_id"], game_id="cs2", ttl_seconds=43200)
            if peak_elo is not None:
                result["top_elo_all_time"] = peak_elo
            if peak_ms is not None:
                import datetime as _dt
                try:
                    result["top_elo_date"] = _dt.datetime.utcfromtimestamp(int(peak_ms) / 1000).strftime('%Y-%m-%d')
                except Exception:
                    pass

            recent_100 = faceit.get_player_matches_stats_list(player_id=result["player_id"], game_id="cs2", offset=0, limit=100)
            if "error" not in recent_100:
                items = recent_100.get("items", [])
                adr10 = faceit._avg_adr_from_items(items, 10)
                adr30 = faceit._avg_adr_from_items(items, 30)
                adr100 = faceit._avg_adr_from_items(items, 100)
                if adr10 is not None:
                    result["adr_last_10"] = round(adr10, 2)
                if adr30 is not None:
                    result["adr_last_30"] = round(adr30, 2)
                if adr100 is not None:
                    result["adr_last_100"] = round(adr100, 2)
                # win rate over recent windows
                wr10 = faceit._win_rate_from_items(items, 10)
                wr30 = faceit._win_rate_from_items(items, 30)
                wr100 = faceit._win_rate_from_items(items, 100)
                if wr10 is not None:
                    result["win_rate_last_10"] = round(wr10, 2)
                if wr30 is not None:
                    result["win_rate_last_30"] = round(wr30, 2)
                if wr100 is not None:
                    result["win_rate_last_100"] = round(wr100, 2)
                # Fallback Elo via per-match stats if web time stats failed
                if "elo_10_games_ago" not in result or result.get("elo_10_games_ago") is None:
                    e10 = faceit._elo_at_n_from_items(items, 10)
                    if e10 is not None:
                        result["elo_10_games_ago"] = e10
                if "elo_30_games_ago" not in result or result.get("elo_30_games_ago") is None:
                    e30 = faceit._elo_at_n_from_items(items, 30)
                    if e30 is not None:
                        result["elo_30_games_ago"] = e30
                if "elo_100_games_ago" not in result or result.get("elo_100_games_ago") is None:
                    e100 = faceit._elo_at_n_from_items(items, 100)
                    if e100 is not None:
                        result["elo_100_games_ago"] = e100
            # Derive the Nth match dates from the authoritative history endpoint
            history_100 = faceit.get_player_history(player_id=result["player_id"], game_id="cs2", offset=0, limit=100)
            if "error" not in history_100:
                hitems = history_100.get("items", [])
                d10 = faceit._nth_match_date_from_history(hitems, 10)
                d30 = faceit._nth_match_date_from_history(hitems, 30)
                d100 = faceit._nth_match_date_from_history(hitems, 100)
                # Convert ms epoch to ISO date (YYYY-MM-DD)
                import datetime as _dt
                def _to_date(ts_seconds):
                    try:
                        if not ts_seconds:
                            return None
                        return _dt.datetime.utcfromtimestamp(int(ts_seconds)).strftime('%Y-%m-%d')
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