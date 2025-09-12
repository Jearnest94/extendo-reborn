#!/usr/bin/env python3
"""
learning-the-api.py

One-off helper to learn/inspect the FACEIT Data API responses used by this repo.

- Reads FACEIT_API_KEY from environment or .env
- Calls the documented v4 endpoints we rely on
  * GET /players?nickname=...
  * GET /players/{player_id}/stats/cs2
  * GET /matches/{match_id}
  * GET /matchmakings/{match_id}
- Writes each response to ./api-dumps/*.json so we can diff/inspect payload shapes

Usage examples:
  python learning-the-api.py --nickname someNick --match-id 1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

Alternatively, set env vars and run with no args:
  FACEIT_API_KEY=... SAMPLE_NICKNAME=someNick SAMPLE_MATCH_ID=1-... python learning-the-api.py

This script does not depend on the Flask backend; it talks directly to open.faceit.com.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def data_api_session(api_key: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    })
    return s


def get_player_by_nickname(session: requests.Session, nickname: str):
    r = session.get("https://open.faceit.com/data/v4/players", params={"nickname": nickname}, timeout=10)
    try:
        j = r.json()
    except Exception:
        j = {"_raw": r.text}
    return r.status_code, j


def get_player_cs2_stats(session: requests.Session, player_id: str):
    r = session.get(f"https://open.faceit.com/data/v4/players/{player_id}/stats/cs2", timeout=10)
    try:
        j = r.json()
    except Exception:
        j = {"_raw": r.text}
    return r.status_code, j


def get_match(session: requests.Session, match_id: str):
    r = session.get(f"https://open.faceit.com/data/v4/matches/{match_id}", timeout=10)
    try:
        j = r.json()
    except Exception:
        j = {"_raw": r.text}
    return r.status_code, j


def get_matchmaking(session: requests.Session, match_id: str):
    r = session.get(f"https://open.faceit.com/data/v4/matchmakings/{match_id}", timeout=10)
    try:
        j = r.json()
    except Exception:
        j = {"_raw": r.text}
    return r.status_code, j


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Dump FACEIT Data API responses to files for inspection")
    parser.add_argument("--nickname", default=os.getenv("SAMPLE_NICKNAME", ""), help="FACEIT nickname to resolve")
    parser.add_argument("--match-id", dest="match_id", default=os.getenv("SAMPLE_MATCH_ID", ""), help="FACEIT room/match id (e.g., 1-...)")
    parser.add_argument("--out", dest="out_dir", default="api-dumps", help="Output directory for JSON dumps")
    args = parser.parse_args()

    api_key = os.getenv("FACEIT_API_KEY")
    if not api_key:
        print("ERROR: FACEIT_API_KEY is required (set in environment or .env)", file=sys.stderr)
        sys.exit(1)

    session = data_api_session(api_key)
    out_dir = Path(args.out_dir)

    print("Using output directory:", out_dir)

    # 1) Players by nickname
    if args.nickname:
        print(f"[1/4] GET players?nickname={args.nickname}")
        sc, player = get_player_by_nickname(session, args.nickname)
        save_json(out_dir / f"players_by_nickname_{args.nickname}.json", {"status": sc, "body": player})
        print("  -> status:", sc)

        # 2) Player CS2 stats (if player_id available)
        player_id = None
        if isinstance(player, dict):
            player_id = player.get("player_id")
        if player_id:
            print(f"[2/4] GET players/{player_id}/stats/cs2")
            sc2, stats = get_player_cs2_stats(session, player_id)
            save_json(out_dir / f"player_stats_cs2_{player_id}.json", {"status": sc2, "body": stats})
            print("  -> status:", sc2)
        else:
            print("[2/4] Skipped player stats (player_id not found in player response)")
    else:
        print("[1/4] Skipped players (no nickname provided)")
        print("[2/4] Skipped player stats (no nickname provided)")

    # 3) Matches/{id}
    if args.match_id:
        print(f"[3/4] GET matches/{args.match_id}")
        sm, match_body = get_match(session, args.match_id)
        save_json(out_dir / f"match_{args.match_id}.json", {"status": sm, "body": match_body})
        print("  -> status:", sm)

        # 4) Matchmakings/{id}
        print(f"[4/4] GET matchmakings/{args.match_id}")
        smm, mm_body = get_matchmaking(session, args.match_id)
        save_json(out_dir / f"matchmaking_{args.match_id}.json", {"status": smm, "body": mm_body})
        print("  -> status:", smm)
    else:
        print("[3/4] Skipped matches (no match_id provided)")
        print("[4/4] Skipped matchmakings (no match_id provided)")

    print("Done. Inspect JSON files under:", out_dir)


if __name__ == "__main__":
    main()
