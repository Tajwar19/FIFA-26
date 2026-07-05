import os
import json
import urllib.request

def scrape_standings():
    url = "https://api.fifa.com/api/v3/calendar/17/285023/289273/Standing?language=en"
    print(f"Fetching standings from FIFA API URL: {url}...")
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            data = json.loads(res.read().decode('utf-8'))
    except Exception as e:
        print(f"Failed to fetch standings from FIFA API: {e}")
        return

    results = data.get("Results", [])
    if not results:
        print("No standings returned from FIFA API.")
        return

    # Group standings dictionary
    groups_data = {}
    
    for m in results:
        # Group name e.g. "Group J"
        group_desc = m.get("Group", [{}])[0].get("Description") if m.get("Group") else "Unknown Group"
        
        # Team details
        team_info = m.get("Team", {})
        team_name = team_info.get("Name", [{}])[0].get("Description") if team_info.get("Name") else ""
        team_code = team_info.get("Abbreviation") or team_info.get("IdAssociation") or ""
        
        entry = {
            "Pos": m.get("Position", 0),
            "Team": team_name,
            "Code": team_code,
            "Played": m.get("Played", 0),
            "Won": m.get("Won", 0),
            "Drawn": m.get("Drawn", 0),
            "Lost": m.get("Lost", 0),
            "GF": m.get("For", 0),
            "GA": m.get("Against", 0),
            "GD": m.get("GoalsDiference", 0),
            "Points": m.get("Points", 0)
        }
        
        if group_desc not in groups_data:
            groups_data[group_desc] = []
        groups_data[group_desc].append(entry)
        
    # Sort teams inside each group by Position
    for gname in groups_data:
        groups_data[gname].sort(key=lambda x: x["Pos"])
        
    # Sort groups alphabetically
    all_standings = dict(sorted(groups_data.items()))

    # Print standings preview for console logs compatibility
    for group_name, teams in all_standings.items():
        print(f"\n--- {group_name} ---")
        print(f" Pos {'Team':<25} {'Code':<4} {'Pl':<2} {'W':<2} {'D':<2} {'L':<2} {'GF':<3} {'GA':<3} {'GD':<3} {'Pts':<3}")
        for t in teams:
            print(f"  {t['Pos']:>2} {t['Team']:<25} {t['Code']:<4} {t['Played']:>2} {t['Won']:>2} {t['Drawn']:>2} {t['Lost']:>2} {t['GF']:>3} {t['GA']:>3} {t['GD']:>3} {t['Points']:>3}")

    # Save to JSON file if different to preserve timestamp
    json_filename = "all_standings.json"
    existing_data = None
    if os.path.exists(json_filename):
        try:
            with open(json_filename, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            pass
            
    if existing_data != all_standings:
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(all_standings, f, indent=4, ensure_ascii=False)
        print(f"\nSaved all standings to {json_filename}")
    else:
        print("\nNo standings changes detected. Skipping file write to preserve timestamp.")

if __name__ == "__main__":
    scrape_standings()
