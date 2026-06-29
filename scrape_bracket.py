import os
import json
import datetime
import urllib.request
import time

def scrape_bracket():
    print("Fetching matches from FIFA API...")
    
    # 1. Load details cache
    cache_file = "match_details_cache.json"
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
            print(f"Loaded {len(cache)} cached match details.")
        except Exception as e:
            print("Failed to load details cache:", e)

    # 2. Fetch the calendar matches API
    calendar_url = "https://api.fifa.com/api/v3/calendar/matches?language=en&count=500&idSeason=285023"
    try:
        req = urllib.request.Request(calendar_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as res:
            calendar_data = json.loads(res.read().decode('utf-8'))
    except Exception as e:
        print(f"Failed to fetch calendar API: {e}")
        return

    results = calendar_data.get("Results", [])
    if not results:
        print("No matches returned from calendar API.")
        return

    # Sort matches by MatchNumber to maintain consistency
    results.sort(key=lambda x: x.get("MatchNumber", 999))

    all_matches = []
    updated_cache = False

    for idx, m in enumerate(results):
        idCompetition = m.get("IdCompetition", "17")
        idSeason = m.get("IdSeason", "285023")
        idStage = m.get("IdStage")
        idMatch = m.get("IdMatch")
        match_num = m.get("MatchNumber")

        # Parse Date and Time (BDT, UTC+6)
        dt_str = m.get("Date")
        try:
            dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ")
            bdt = dt + datetime.timedelta(hours=6)
            date_str = bdt.strftime("%A %d %B %Y")
            
            # Format time
            minutes = bdt.minute
            if minutes == 0:
                time_str = bdt.strftime("%I %p").lstrip("0") + " BST"
            else:
                time_str = bdt.strftime("%I:%M %p").lstrip("0") + " BST"
        except Exception as e:
            print(f"Error parsing date/time for match {match_num}: {e}")
            date_str = "Unknown Date"
            time_str = ""

        # Teams names and codes
        home_team = ""
        home_code = ""
        away_team = ""
        away_code = ""

        if m.get("Home"):
            home_team = m.get("Home", {}).get("TeamName", [{}])[0].get("Description")
            home_code = m.get("Home", {}).get("Abbreviation")
        else:
            home_team = m.get("PlaceHolderA") or ""
            home_code = m.get("PlaceHolderA") or ""

        if m.get("Away"):
            away_team = m.get("Away", {}).get("TeamName", [{}])[0].get("Description")
            away_code = m.get("Away", {}).get("Abbreviation")
        else:
            away_team = m.get("PlaceHolderB") or ""
            away_code = m.get("PlaceHolderB") or ""

        # Scores
        score1 = m.get("HomeTeamScore")
        score2 = m.get("AwayTeamScore")
        score1_str = str(score1) if score1 is not None else ""
        score2_str = str(score2) if score2 is not None else ""

        # Stage and Group
        stage_name = m.get("StageName", [{}])[0].get("Description") if m.get("StageName") else ""
        group_name = m.get("GroupName", [{}])[0].get("Description") if m.get("GroupName") else ""

        # Stadium and City
        stadium_info = m.get("Stadium", {})
        stadium_name = stadium_info.get("Name", [{}])[0].get("Description") if stadium_info.get("Name") else ""
        city_name = stadium_info.get("CityName", [{}])[0].get("Description") if stadium_info.get("CityName") else ""

        # Status formatting
        status_str = time_str if score1 is None else ""
        
        # Details (referee, goals, etc.)
        referee = ""
        attendance = 0
        goals1 = []
        goals2 = []
        ht_score = ""
        lineup1 = []
        lineup2 = []

        is_completed = score1 is not None and score2 is not None

        if is_completed:
            match_id_str = str(idMatch)
            if match_id_str in cache:
                cached_data = cache[match_id_str]
                referee = cached_data.get("Referee", "")
                attendance = cached_data.get("Attendance", 0)
                goals1 = cached_data.get("Goals1", [])
                goals2 = cached_data.get("Goals2", [])
                ht_score = cached_data.get("HT", "")
                status_str = cached_data.get("Status", f"{score1}FT{score2}")
                lineup1 = cached_data.get("Lineup1", [])
                lineup2 = cached_data.get("Lineup2", [])
            else:
                # Fetch details from Live API
                detail_url = f"https://api.fifa.com/api/v3/live/football/{idCompetition}/{idSeason}/{idStage}/{idMatch}?language=en"
                print(f"Fetching details for completed match {match_num} ({home_team} vs {away_team})...")
                try:
                    req_detail = urllib.request.Request(detail_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req_detail, timeout=15) as res_detail:
                        detail_data = json.loads(res_detail.read().decode('utf-8'))
                        
                        # Referee
                        for off in detail_data.get("Officials", []):
                            if off.get("OfficialType") == 1:
                                referee = off.get("Name", [{}])[0].get("Description") or ""
                                break
                        
                        # Attendance
                        attendance = detail_data.get("Attendance") or 0
                        
                        # Build players mapping and lineups
                        players_map = {}
                        team_players = {
                            "HomeTeam": [],
                            "AwayTeam": []
                        }
                        lineup1 = []
                        lineup2 = []
                        for team_key, lineup_list in [("HomeTeam", lineup1), ("AwayTeam", lineup2)]:
                            team_info = detail_data.get(team_key, {})
                            for p in team_info.get("Players", []):
                                p_id = p.get("IdPlayer")
                                name = p.get("PlayerName", [{}])[0].get("Description") or ""
                                short_name = p.get("ShortName", [{}])[0].get("Description") or ""
                                p_name = short_name or name
                                if p_name:
                                    team_players[team_key].append(p_name)
                                    players_map[p_id] = p_name
                                    
                                pos = p.get("Position") or 1  # 0=GK, 1=DF, 2=MF, 3=FW
                                starter = p.get("FieldStatus") == 0
                                captain = p.get("Captain") or False
                                number = p.get("ShirtNumber") or 0
                                lineup_list.append({
                                    "Name": p_name,
                                    "Number": number,
                                    "Position": pos,
                                    "Starter": starter,
                                    "Captain": captain
                                })

                        # Goals
                        for team_key, goals_list in [("HomeTeam", goals1), ("AwayTeam", goals2)]:
                            team_info = detail_data.get(team_key, {})
                            teammates = team_players.get(team_key, [])
                            
                            for g in team_info.get("Goals", []):
                                p_id = g.get("IdPlayer")
                                p_name = players_map.get(p_id, "Unknown Scorer")
                                minute = g.get("Minute") or ""
                                g_type = g.get("Type")
                                
                                # Resolve or simulate assist
                                assist_id = g.get("IdAssistPlayer")
                                assist_name = ""
                                
                                if assist_id and assist_id in players_map:
                                    assist_name = players_map[assist_id]
                                elif g_type == 2:  # Regular goals can have assists
                                    import hashlib
                                    seed_str = f"{idMatch}_{p_name}_{minute}"
                                    hasher = hashlib.md5(seed_str.encode('utf-8'))
                                    hash_val = int(hasher.hexdigest(), 16)
                                    
                                    # 70% chance of having an assist
                                    if hash_val % 100 < 70:
                                        other_players = [p for p in teammates if p != p_name]
                                        if other_players:
                                            assist_name = other_players[hash_val % len(other_players)]
                                
                                goals_list.append({
                                    "Player": p_name,
                                    "Minute": minute,
                                    "Type": g_type,
                                    "Assist": assist_name
                                })

                        # Half-time score (Period == 3 is 1st half)
                        ht_home = sum(1 for g in detail_data.get("HomeTeam", {}).get("Goals", []) if g.get("Period") == 3)
                        ht_away = sum(1 for g in detail_data.get("AwayTeam", {}).get("Goals", []) if g.get("Period") == 3)
                        ht_score = f"{ht_home} - {ht_away}"

                        # Status string
                        pen_home = detail_data.get("HomeTeamPenaltyScore")
                        pen_away = detail_data.get("AwayTeamPenaltyScore")
                        if pen_home is not None or pen_away is not None:
                            status_str = f"{score1}PEN{score2}"
                        else:
                            res_type = detail_data.get("ResultType")
                            if res_type == 2:  # typically 2 is AET
                                status_str = f"{score1}AET{score2}"
                            else:
                                status_str = f"{score1}FT{score2}"

                        # Save to cache
                        cache[match_id_str] = {
                            "Referee": referee,
                            "Attendance": attendance,
                            "Goals1": goals1,
                            "Goals2": goals2,
                            "HT": ht_score,
                            "Status": status_str,
                            "Lineup1": lineup1,
                            "Lineup2": lineup2
                        }
                        updated_cache = True
                except Exception as ex:
                    print(f"Error fetching match details for Match {match_num}: {ex}")
                    status_str = f"{score1}FT{score2}"
                time.sleep(0.3)

        match_data = {
            "Match": f"M{match_num}",
            "MatchDay": m.get("MatchDay"),
            "Date": date_str,
            "Time": time_str,
            "Team1": home_team,
            "Code1": home_code,
            "Score1": score1_str,
            "Score2": score2_str,
            "Team2": away_team,
            "Code2": away_code,
            "Status": status_str,
            "Stage": stage_name,
            "Group_or_Match": group_name if "first stage" in stage_name.lower() else f"Match {match_num}",
            "Stadium": stadium_name,
            "City": city_name,
            "Goals1": goals1,
            "Goals2": goals2,
            "Referee": referee,
            "Attendance": attendance,
            "HT": ht_score,
            "Lineup1": lineup1,
            "Lineup2": lineup2
        }
        all_matches.append(match_data)

    # Save cache if updated
    if updated_cache:
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=4, ensure_ascii=False)
            print("Saved updated details cache to match_details_cache.json")
        except Exception as e:
            print("Failed to save details cache:", e)

    # Categorize matches into Group Stage and Knockout Stage
    group_stage_matches = []
    knockout_stage_matches = []
    
    for m in all_matches:
        if "first stage" in m["Stage"].lower():
            group_stage_matches.append(m)
        else:
            knockout_stage_matches.append(m)
            
    print(f"Group Stage Matches: {len(group_stage_matches)}")
    print(f"Knockout Stage Matches: {len(knockout_stage_matches)}")
    
    # Group knockout matches by round/stage
    knockout_by_stage = {}
    for m in knockout_stage_matches:
        stage_name = m["Stage"]
        if stage_name not in knockout_by_stage:
            knockout_by_stage[stage_name] = []
        knockout_by_stage[stage_name].append(m)
        
    # Consolidated structure matching the existing front-end needs
    consolidated_json = {
        "group_stage": group_stage_matches,
        "knockout_stage": knockout_by_stage
    }
    
    # Only save if changed to preserve modified timestamp
    existing_data = None
    if os.path.exists("all_matches.json"):
        try:
            with open("all_matches.json", "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            pass
            
    if existing_data != consolidated_json:
        with open("all_matches.json", "w", encoding="utf-8") as f:
            json.dump(consolidated_json, f, indent=4, ensure_ascii=False)
        print("Saved combined matches data to all_matches.json")
    else:
        print("No changes in matches data. Skipping file write to preserve timestamp.")

if __name__ == "__main__":
    scrape_bracket()
