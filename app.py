import os
import datetime
import json
import traceback
import re
from flask import Flask, render_template, jsonify

# Import the scraping functions directly
from scrape_standings import scrape_standings
from scrape_bracket import scrape_bracket
from scrape_bracket_tree import scrape_bracket_tree

app = Flask(__name__)

# Paths to data files
STANDINGS_FILE = "all_standings.json"
BRACKET_FILE = "bracket_tree.json"
MATCHES_FILE = "all_matches.json"

def get_last_updated_time():
    """
    Returns the last modified time of the scraped files as a formatted string.
    """
    files = [STANDINGS_FILE, BRACKET_FILE, MATCHES_FILE]
    mod_times = []
    for f in files:
        if os.path.exists(f):
            mod_times.append(os.path.getmtime(f))
    if mod_times:
        latest_time = max(mod_times)
        return datetime.datetime.fromtimestamp(latest_time).strftime("%Y-%m-%d %I:%M:%S %p")
    return "Never"

def load_json_data(filepath, default_val=None):
    """
    Helper to safely load a JSON file.
    """
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    return default_val if default_val is not None else {}

@app.route("/")
def index():
    # Render index.html template
    return render_template("index.html")

def is_placeholder(team_name):
    """
    Checks if a team name string is a bracket placeholder (e.g. 1A, 2B, 3ABCDF, W74, RU101).
    """
    if not team_name:
        return False
    # 1A to 2L
    if re.match(r'^[1-2][A-L]$', team_name):
        return True
    # 3ABCDF etc.
    if re.match(r'^3[A-L]{2,12}$', team_name):
        return True
    # Winner placeholders (W73, W74, etc.)
    if team_name.startswith('W') and team_name[1:].isdigit():
        return True
    # Runner up placeholders (RU101, RU102, etc.)
    if team_name.startswith('RU') and team_name[2:].isdigit():
        return True
    return False

def get_third_placed_standings(standings):
    """
    Collects and ranks the 3rd-placed teams from all 12 groups (A-L)
    based on Points, Goal Difference (GD), Goals For (GF), and Wins.
    """
    third_places = []
    for group_name, teams in standings.items():
        if len(teams) >= 3:
            t = teams[2]
            group_letter = group_name.split()[-1] if len(group_name.split()) > 1 else group_name
            third_places.append({
                "Team": t.get("Team", ""),
                "Code": t.get("Code", ""),
                "Group": group_letter,
                "Played": t.get("Played", 0),
                "Won": t.get("Won", 0),
                "Drawn": t.get("Drawn", 0),
                "Lost": t.get("Lost", 0),
                "GF": t.get("GF", 0),
                "GA": t.get("GA", 0),
                "GD": t.get("GD", 0),
                "Points": t.get("Points", 0)
            })
            
    # Sort: Points (desc), GD (desc), GF (desc), Won (desc)
    third_places.sort(key=lambda x: (x["Points"], x["GD"], x["GF"], x["Won"]), reverse=True)
    
    # Assign Position ranks 1-12
    for idx, t in enumerate(third_places):
        t["Pos"] = idx + 1
        
    return third_places

def find_3rd_place_assignment(qualified_groups):
    """
    Bipartite matching/backtracking algorithm to dynamically assign the 8 best
    third-placed groups to their specific Round of 32 slots according to FIFA regulations.
    """
    slots = [
        {"name": "3ABCDF", "allowed": {'A', 'B', 'C', 'D', 'F'}},
        {"name": "3CDFGH", "allowed": {'C', 'D', 'F', 'G', 'H'}},
        {"name": "3BEFIJ", "allowed": {'B', 'E', 'F', 'I', 'J'}},
        {"name": "3AEHIJ", "allowed": {'A', 'E', 'H', 'I', 'J'}},
        {"name": "3EFGIJ", "allowed": {'E', 'F', 'G', 'I', 'J'}},
        {"name": "3DEIJL", "allowed": {'D', 'E', 'I', 'J', 'L'}},
        {"name": "3CEFHI", "allowed": {'C', 'E', 'F', 'H', 'I'}},
        {"name": "3EHIJK", "allowed": {'E', 'H', 'I', 'J', 'K'}}
    ]
    
    assignment = {}
    used_slots = set()
    
    def backtrack(group_idx):
        if group_idx == len(qualified_groups):
            return True
        group = qualified_groups[group_idx]
        for i, slot in enumerate(slots):
            if i not in used_slots and group in slot["allowed"]:
                used_slots.add(i)
                assignment[slot["name"]] = group
                if backtrack(group_idx + 1):
                    return True
                used_slots.remove(i)
                del assignment[slot["name"]]
        return False
        
    if backtrack(0):
        return assignment
        
    # Greedy fallback
    fallback_assignment = {}
    for group in qualified_groups:
        for slot in slots:
            if slot["name"] not in fallback_assignment and group in slot["allowed"]:
                fallback_assignment[slot["name"]] = group
                break
    return fallback_assignment

def parse_date_components(date_str):
    """
    Parses date_str into (year, month, day) integers.
    Supports formats like 'Monday 29 June 2026' and '06/29/202601:00' and '06/29/2026'.
    """
    if not date_str:
        return None
    date_str = date_str.strip().lower()
    
    # Months mapping
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    
    # Try MM/DD/YYYY format first
    m_slash = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_str)
    if m_slash:
        return int(m_slash.group(3)), int(m_slash.group(1)), int(m_slash.group(2))
        
    # Try text format like 'Monday 29 June 2026' or '29 June 2026'
    day_match = re.search(r'\b(\d{1,2})\b', date_str)
    year_match = re.search(r'\b(\d{4})\b', date_str)
    
    month_val = None
    for m_name, m_val in months.items():
        if m_name in date_str:
            month_val = m_val
            break
            
    if day_match and year_match and month_val:
        return int(year_match.group(1)), month_val, int(day_match.group(1))
        
    return None

def resolve_bracket_placeholders(standings, third_places_ranking, all_matches_list, bracket):
    """
    Builds a lookup mapping from placeholder strings to actual country names,
    propagating group winners, qualified 3rd places, and match winners recursively.
    """
    resolved = {}
    
    # 1. Map Group Winners (1A-1L) and Runners-up (2A-2L)
    for group_name, teams in standings.items():
        group_letter = group_name.split()[-1] if len(group_name.split()) > 1 else group_name
        if len(teams) >= 1:
            resolved[f"1{group_letter}"] = teams[0].get("Team", "")
        if len(teams) >= 2:
            resolved[f"2{group_letter}"] = teams[1].get("Team", "")
            
    # 2. Map best 8 third-placed teams
    best_8_third_places = [t for t in third_places_ranking if t["Pos"] <= 8]
    best_8_groups = [t["Group"] for t in best_8_third_places]
    
    # Run assignment solver
    assignment = find_3rd_place_assignment(best_8_groups)
    
    group_to_third_team = {t["Group"]: t["Team"] for t in best_8_third_places}
    for slot_name, group_letter in assignment.items():
        resolved[slot_name] = group_to_third_team.get(group_letter, "")
        
    # 3. Propagate match winners and runners-up recursively
    # We map bracket tree match IDs to all_matches.json match details using:
    # (a) Date and Time components matching (primary and highly robust)
    # (b) Fallback to placeholder matching
    match_results = {}
    for round_name, matches in bracket.items():
        for m in matches:
            match_id = m.get("Match", "")
            m_date_comp = parse_date_components(m.get("Date", ""))
            m_time = m.get("Time", "").strip()
            
            t1_placeholder = m.get("Team1", "").strip()
            t2_placeholder = m.get("Team2", "").strip()
            
            # Find matching detail in all_matches_list
            matched_detail = None
            
            # Try date/time matching first
            if m_date_comp and m_time:
                for match_detail in all_matches_list:
                    det_date_comp = parse_date_components(match_detail.get("Date", ""))
                    det_time = match_detail.get("Time", "").strip()
                    if det_date_comp == m_date_comp and det_time == m_time:
                        matched_detail = match_detail
                        break
                        
            # Fallback to placeholder matching
            if not matched_detail:
                for match_detail in all_matches_list:
                    det_t1 = match_detail.get("Team1", "").strip()
                    det_t2 = match_detail.get("Team2", "").strip()
                    if det_t1 == t1_placeholder and det_t2 == t2_placeholder:
                        matched_detail = match_detail
                        break
                        
            if matched_detail:
                match_results[match_id] = matched_detail
                
    # Iteratively propagate through 5 rounds of knockouts (R32, R16, QF, SF, Finals)
    for _ in range(5):
        for match_id, m in match_results.items():
            t1 = m.get("Team1", "")
            t2 = m.get("Team2", "")
            
            # Resolve placeholders
            res_t1 = resolved.get(t1, t1)
            res_t2 = resolved.get(t2, t2)
            
            score1 = m.get("Score1", "")
            score2 = m.get("Score2", "")
            
            if score1 != "" and score2 != "":
                try:
                    s1 = int(score1)
                    s2 = int(score2)
                    
                    winner = ""
                    runner_up = ""
                    if s1 > s2:
                        winner = res_t1
                        runner_up = res_t2
                    elif s2 > s1:
                        winner = res_t2
                        runner_up = res_t1
                    else:
                        # Tie: default to team 1, can be overridden by penalties info if needed
                        winner = res_t1
                        runner_up = res_t2
                        
                    match_num = match_id[1:] # e.g. "74"
                    if winner:
                        resolved[f"W{match_num}"] = winner
                    if runner_up:
                        resolved[f"RU{match_num}"] = runner_up
                except Exception as e:
                    print(f"Error resolving winner for match {match_id}: {e}")
                    
    return resolved, match_results

@app.route("/api/data", methods=["GET"])
def get_data():
    """
    Returns all collected standings, match playlists, and enhanced/resolved bracket tree details.
    """
    standings = load_json_data(STANDINGS_FILE, default_val={})
    bracket = load_json_data(BRACKET_FILE, default_val={})
    matches_data = load_json_data(MATCHES_FILE, default_val={"group_stage": [], "knockout_stage": {}})
    
    # Get flat list of all matches
    all_matches_list = matches_data.get("group_stage", []).copy()
    for stage_matches in matches_data.get("knockout_stage", {}).values():
        all_matches_list.extend(stage_matches)
        
    # 1. Rank third-places
    third_places_ranking = get_third_placed_standings(standings)
    
    # 2. Solve mappings
    resolved_placeholders, match_details = resolve_bracket_placeholders(standings, third_places_ranking, all_matches_list, bracket)
    
    # 3. Enhance bracket tree matches with resolved names, scores, and status
    enhanced_bracket = {}
    for round_name, matches in bracket.items():
        enhanced_bracket[round_name] = []
        for m in matches:
            m_copy = m.copy()
            match_id = m_copy.get("Match", "") # e.g. "M74"
            
            # Populate score and status from all_matches.json details
            m_detail = match_details.get(match_id)
            if m_detail:
                m_copy["Score1"] = m_detail.get("Score1", "")
                m_copy["Score2"] = m_detail.get("Score2", "")
                m_copy["Status"] = m_detail.get("Status", "")
                if m_detail.get("Date"):
                    m_copy["Date"] = m_detail.get("Date")
                if m_detail.get("Time"):
                    m_copy["Time"] = m_detail.get("Time")
            else:
                m_copy["Score1"] = ""
                m_copy["Score2"] = ""
                m_copy["Status"] = ""
                
            # Resolve team names with placeholder prefix (e.g., "1E: Spain")
            t1_orig = m_copy.get("Team1", "")
            t2_orig = m_copy.get("Team2", "")
            
            resolved_t1 = resolved_placeholders.get(t1_orig, t1_orig)
            resolved_t2 = resolved_placeholders.get(t2_orig, t2_orig)
            
            # Formatting (e.g. "1E: Spain")
            if is_placeholder(t1_orig) and resolved_t1 and resolved_t1 != t1_orig:
                m_copy["Team1"] = f"{t1_orig}: {resolved_t1}"
            else:
                m_copy["Team1"] = resolved_t1 if resolved_t1 else t1_orig
                
            if is_placeholder(t2_orig) and resolved_t2 and resolved_t2 != t2_orig:
                m_copy["Team2"] = f"{t2_orig}: {resolved_t2}"
            else:
                m_copy["Team2"] = resolved_t2 if resolved_t2 else t2_orig
                
            enhanced_bracket[round_name].append(m_copy)
            
    # 4. Resolve team placeholders in the matches playlist as well
    enhanced_matches = {
        "group_stage": matches_data.get("group_stage", []),
        "knockout_stage": {}
    }
    for stage_name, stage_matches in matches_data.get("knockout_stage", {}).items():
        enhanced_matches["knockout_stage"][stage_name] = []
        for m in stage_matches:
            m_copy = m.copy()
            t1_orig = m_copy.get("Team1", "")
            t2_orig = m_copy.get("Team2", "")
            
            resolved_t1 = resolved_placeholders.get(t1_orig, t1_orig)
            resolved_t2 = resolved_placeholders.get(t2_orig, t2_orig)
            
            if is_placeholder(t1_orig) and resolved_t1 and resolved_t1 != t1_orig:
                m_copy["Team1"] = f"{t1_orig}: {resolved_t1}"
            else:
                m_copy["Team1"] = resolved_t1 if resolved_t1 else t1_orig
                
            if is_placeholder(t2_orig) and resolved_t2 and resolved_t2 != t2_orig:
                m_copy["Team2"] = f"{t2_orig}: {resolved_t2}"
            else:
                m_copy["Team2"] = resolved_t2 if resolved_t2 else t2_orig
                
            enhanced_matches["knockout_stage"][stage_name].append(m_copy)

    last_updated = get_last_updated_time()
    
    return jsonify({
        "standings": standings,
        "third_places": third_places_ranking,
        "bracket": enhanced_bracket,
        "matches": enhanced_matches,
        "last_updated": last_updated
    })

@app.route("/api/scrape", methods=["POST"])
def trigger_scrape():
    """
    Triggers all playwright scrapers in sequence to pull live data.
    """
    print("\n[API] Live scrape requested...")
    try:
        # 1. Scrape standings table
        print("[API] Running scrape_standings...")
        scrape_standings()
        
        # 2. Scrape match list (group + knockout)
        print("[API] Running scrape_bracket (matches)...")
        scrape_bracket()
        
        # 3. Scrape visual bracket tree connections
        print("[API] Running scrape_bracket_tree...")
        scrape_bracket_tree()
        
        last_updated = get_last_updated_time()
        print(f"[API] Scraped successfully! Last updated: {last_updated}\n")
        
        return jsonify({
            "status": "success",
            "message": "Scraped all data successfully!",
            "last_updated": last_updated
        })
    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"[API] Error running scrapers: {error_msg}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": error_msg
        }), 500

if __name__ == "__main__":
    # Ensure templates folder exists
    os.makedirs("templates", exist_ok=True)
    
    # Run server on port 5000
    print(f"Starting FIFA World Cup 2026 Dashboard Server on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
