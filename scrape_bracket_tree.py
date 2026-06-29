import os
import json
import csv
from playwright.sync_api import sync_playwright
import pandas as pd

URL = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures"

# Brackets connector map defining the logical path/progression of the tournament
# e.g., Winner of M74 and M77 meet in M89, Winner of M89 and M90 meet in M97, etc.
NEXT_MATCH_MAP = {
    # LEFT Side
    "M74": "M89", "M77": "M89",
    "M73": "M90", "M75": "M90",
    "M83": "M93", "M84": "M93",
    "M81": "M94", "M82": "M94",
    "M89": "M97", "M90": "M97",
    "M93": "M98", "M94": "M98",
    "M97": "M101", "M98": "M101",
    "M101": "M104 (winner) / M103 (loser)",
    
    # RIGHT Side
    "M76": "M91", "M78": "M91",
    "M79": "M92", "M80": "M92",
    "M86": "M95", "M88": "M95",
    "M85": "M96", "M87": "M96",
    "M91": "M99", "M92": "M99",
    "M95": "M100", "M96": "M100",
    "M99": "M102", "M100": "M102",
    "M102": "M104 (winner) / M103 (loser)",
    
    # Center
    "M103": "",  # Third Place Match
    "M104": ""   # Final
}

# Mapping of stage column indices to human-readable round names
STAGE_NAMES_BY_INDEX = {
    0: "Round of 32 (Left)",
    1: "Round of 16 (Left)",
    2: "Quarter-final (Left)",
    3: "Semi-final (Left)",
    4: "Play-off for third place",
    5: "Final",
    6: "Semi-final (Right)",
    7: "Quarter-final (Right)",
    8: "Round of 16 (Right)",
    9: "Round of 32 (Right)"
}

def scrape_bracket_tree():
    print("Programmatically constructing bracket tree from all_matches.json...")
    
    # 1. Load matches from all_matches.json
    all_matches_list = []
    if os.path.exists("all_matches.json"):
        try:
            with open("all_matches.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                all_matches_list.extend(data.get("group_stage", []))
                for stage_matches in data.get("knockout_stage", {}).values():
                    all_matches_list.extend(stage_matches)
        except Exception as e:
            print(f"Error reading all_matches.json: {e}")
            return
            
    # Create lookup map for fast retrieval
    match_lookup = {m.get("Match"): m for m in all_matches_list if m.get("Match")}
    
    # Mappings for side and round name of each match in the visual bracket layout
    MATCH_CONFIG = {
        # LEFT Side
        "M73": {"Round": "Round of 32 (Left)", "Side": "LEFT"},
        "M74": {"Round": "Round of 32 (Left)", "Side": "LEFT"},
        "M75": {"Round": "Round of 32 (Left)", "Side": "LEFT"},
        "M77": {"Round": "Round of 32 (Left)", "Side": "LEFT"},
        "M81": {"Round": "Round of 32 (Left)", "Side": "LEFT"},
        "M82": {"Round": "Round of 32 (Left)", "Side": "LEFT"},
        "M83": {"Round": "Round of 32 (Left)", "Side": "LEFT"},
        "M84": {"Round": "Round of 32 (Left)", "Side": "LEFT"},
        
        "M89": {"Round": "Round of 16 (Left)", "Side": "LEFT"},
        "M90": {"Round": "Round of 16 (Left)", "Side": "LEFT"},
        "M93": {"Round": "Round of 16 (Left)", "Side": "LEFT"},
        "M94": {"Round": "Round of 16 (Left)", "Side": "LEFT"},
        
        "M97": {"Round": "Quarter-final (Left)", "Side": "LEFT"},
        "M98": {"Round": "Quarter-final (Left)", "Side": "LEFT"},
        
        "M101": {"Round": "Semi-final (Left)", "Side": "LEFT"},
        
        # CENTER
        "M103": {"Round": "Play-off for third place", "Side": "CENTER"},
        "M104": {"Round": "Final", "Side": "CENTER"},
        
        # RIGHT Side
        "M76": {"Round": "Round of 32 (Right)", "Side": "RIGHT"},
        "M78": {"Round": "Round of 32 (Right)", "Side": "RIGHT"},
        "M79": {"Round": "Round of 32 (Right)", "Side": "RIGHT"},
        "M80": {"Round": "Round of 32 (Right)", "Side": "RIGHT"},
        "M85": {"Round": "Round of 32 (Right)", "Side": "RIGHT"},
        "M86": {"Round": "Round of 32 (Right)", "Side": "RIGHT"},
        "M87": {"Round": "Round of 32 (Right)", "Side": "RIGHT"},
        "M88": {"Round": "Round of 32 (Right)", "Side": "RIGHT"},
        
        "M91": {"Round": "Round of 16 (Right)", "Side": "RIGHT"},
        "M92": {"Round": "Round of 16 (Right)", "Side": "RIGHT"},
        "M95": {"Round": "Round of 16 (Right)", "Side": "RIGHT"},
        "M96": {"Round": "Round of 16 (Right)", "Side": "RIGHT"},
        
        "M99": {"Round": "Quarter-final (Right)", "Side": "RIGHT"},
        "M100": {"Round": "Quarter-final (Right)", "Side": "RIGHT"},
        
        "M102": {"Round": "Semi-final (Right)", "Side": "RIGHT"}
    }
    
    # Required match ordering for columns to align correctly without cross-overs
    COLUMN_MATCH_ORDER = {
        "Round of 32 (Left)": ["M74", "M77", "M73", "M75", "M83", "M84", "M81", "M82"],
        "Round of 16 (Left)": ["M89", "M90", "M93", "M94"],
        "Quarter-final (Left)": ["M97", "M98"],
        "Semi-final (Left)": ["M101"],
        "Play-off for third place": ["M103"],
        "Final": ["M104"],
        "Semi-final (Right)": ["M102"],
        "Quarter-final (Right)": ["M99", "M100"],
        "Round of 16 (Right)": ["M91", "M92", "M95", "M96"],
        "Round of 32 (Right)": ["M76", "M78", "M79", "M80", "M86", "M88", "M85", "M87"]
    }
    
    bracket_tree = {}
    
    for round_name, match_ids in COLUMN_MATCH_ORDER.items():
        bracket_tree[round_name] = []
        for m_id in match_ids:
            m = match_lookup.get(m_id)
            if not m:
                print(f"Warning: Match {m_id} not found in all_matches.json!")
                continue
                
            config = MATCH_CONFIG.get(m_id, {})
            
            match_record = {
                "Match": m_id,
                "Round": round_name,
                "Side": config.get("Side", "N/A"),
                "Date": m.get("Date", "N/A"),
                "Time": m.get("Time", "N/A"),
                "Team1": m.get("Team1", "TBD"),
                "Team2": m.get("Team2", "TBD"),
                "NextMatch": NEXT_MATCH_MAP.get(m_id, "")
            }
            bracket_tree[round_name].append(match_record)
            
    print("\n========================================================")
    print("           FIFA WORLD CUP 2026 VISUAL BRACKET TREE      ")
    print("========================================================")
    for round_name, matches in bracket_tree.items():
        print(f"\n--- {round_name} ---")
        for m in matches:
            next_txt = f" -> Next: {m['NextMatch']}" if m['NextMatch'] else ""
            print(f"  {m['Match']} ({m['Date']} {m['Time']}): {m['Team1']} vs {m['Team2']}{next_txt}")
            
    # Save files
    # 1. JSON (only save if changed to preserve modified timestamp)
    existing_data = None
    if os.path.exists("bracket_tree.json"):
        try:
            with open("bracket_tree.json", "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            pass
            
    if existing_data != bracket_tree:
        with open("bracket_tree.json", "w", encoding="utf-8") as f:
            json.dump(bracket_tree, f, indent=4, ensure_ascii=False)
        print("\nSaved bracket tree to bracket_tree.json")
    else:
        print("\nNo changes in bracket tree. Skipping file write to preserve timestamp.")
    
    pass

if __name__ == "__main__":
    scrape_bracket_tree()
