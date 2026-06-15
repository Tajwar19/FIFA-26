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
    print(f"Navigating to {URL}...")
    with sync_playwright() as p:
        # Launch browser with a large viewport to guarantee d-lg-block elements (the visual bracket) render
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        
        # Dismiss cookie banner
        page.evaluate('() => document.getElementById("onetrust-accept-btn-handler")?.click()')
        page.wait_for_timeout(2000)
        
        # Click 'View brackets' to ensure it's active (though it is always in the DOM for desktop sizes)
        view_bracket_btn = page.locator("text=/View brackets/i").first
        if view_bracket_btn.count() > 0:
            print("Clicking 'View brackets' toggle...")
            view_bracket_btn.click(force=True)
            page.wait_for_timeout(3000)
            
        print("Locating bracket stage columns...")
        stages = page.query_selector_all("div[data-testid='bracket-stage']")
        print(f"Found {len(stages)} stage columns in the bracket.")
        
        bracket_tree = {}
        flat_records = []
        
        for idx, stage in enumerate(stages):
            stage_id = stage.get_attribute("data-stage-id") or "N/A"
            position = stage.get_attribute("data-stage-position") or "N/A"
            round_name = STAGE_NAMES_BY_INDEX.get(idx, f"Stage_{idx}")
            
            # Query match nodes in this column
            match_nodes = stage.query_selector_all("[class*='bracketMainWrapper']")
            if len(match_nodes) == 0:
                continue
                
            bracket_tree[round_name] = []
            
            for m_idx, node in enumerate(match_nodes):
                try:
                    # Match ID
                    label_el = node.query_selector("[class*='matchLabel']")
                    label = label_el.text_content().strip() if label_el else "N/A"
                    
                    # Date & Time
                    date_el = node.query_selector("[class*='date']")
                    date = date_el.text_content().strip() if date_el else "N/A"
                    time_el = node.query_selector("[class*='time']")
                    time = time_el.text_content().strip() if time_el else "N/A"
                    
                    # Teams (T1 and T2 name or placeholders)
                    teams = node.query_selector_all("[class*='teamName']")
                    team1 = teams[0].text_content().strip() if len(teams) > 0 else "N/A"
                    team2 = teams[1].text_content().strip() if len(teams) > 1 else "N/A"
                    
                    # Next Match ID in bracket progression
                    next_match = NEXT_MATCH_MAP.get(label, "")
                    
                    match_record = {
                        "Match": label,
                        "Round": round_name,
                        "Side": position,
                        "Date": date,
                        "Time": time,
                        "Team1": team1,
                        "Team2": team2,
                        "NextMatch": next_match
                    }
                    
                    bracket_tree[round_name].append(match_record)
                    flat_records.append(match_record)
                except Exception as e:
                    print(f"Error parsing bracket match node: {e}")
                    
        browser.close()
        
    print("\n========================================================")
    print("           FIFA WORLD CUP 2026 VISUAL BRACKET TREE      ")
    print("========================================================")
    for round_name, matches in bracket_tree.items():
        print(f"\n--- {round_name} ---")
        for m in matches:
            next_txt = f" -> Next: {m['NextMatch']}" if m['NextMatch'] else ""
            print(f"  {m['Match']} ({m['Date']} {m['Time']}): {m['Team1']} vs {m['Team2']}{next_txt}")
            
    # Save files
    # 1. JSON
    with open("bracket_tree.json", "w", encoding="utf-8") as f:
        json.dump(bracket_tree, f, indent=4, ensure_ascii=False)
    print("\nSaved bracket tree to bracket_tree.json")
    
    pass

if __name__ == "__main__":
    scrape_bracket_tree()
