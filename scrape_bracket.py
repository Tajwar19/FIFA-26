import os
import json
import csv
from playwright.sync_api import sync_playwright
import pandas as pd

URL = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures"

def scrape_bracket():
    print(f"Navigating to {URL}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for matches list to render
        try:
            print("Waiting for matches content to load...")
            page.wait_for_selector("[class*='matchRowContainer']", timeout=25000)
        except Exception as e:
            print(f"Timed out waiting for match rows: {e}")
            
        page.wait_for_timeout(3000)
        
        # Dismiss cookies banner
        page.evaluate('() => document.getElementById("onetrust-accept-btn-handler")?.click()')
        page.wait_for_timeout(2000)
        
        print("Extracting elements from the DOM...")
        
        # Query date headers and match containers in DOM order
        elements = page.query_selector_all("[class*='matches-container_title'], [class*='matchRowContainer']")
        print(f"Found {len(elements)} relevant DOM elements.")
        
        current_date = "Unknown Date"
        all_matches = []
        
        for el in elements:
            class_name = el.get_attribute("class") or ""
            
            # If it's a date header
            if "matches-container_title" in class_name:
                date_txt = el.text_content().strip()
                # Clean up any trailing link text in headers
                current_date = date_txt.replace("View groups", "").replace("View brackets", "").strip()
            
            # If it's a match card
            elif "matchRowContainer" in class_name:
                try:
                    # Teams and abbreviations
                    teams = el.query_selector_all(".d-none.d-md-block")
                    team1 = teams[0].text_content().strip() if len(teams) > 0 else ""
                    team2 = teams[1].text_content().strip() if len(teams) > 1 else ""
                    
                    codes = el.query_selector_all("[class*='team-abbreviations_container'] span")
                    code1 = codes[0].text_content().strip() if len(codes) > 0 else ""
                    code2 = codes[1].text_content().strip() if len(codes) > 1 else ""
                    
                    # Scores
                    scores = el.query_selector_all("[class*='match-row_score']")
                    score1 = scores[0].text_content().strip() if len(scores) > 0 else ""
                    score2 = scores[1].text_content().strip() if len(scores) > 1 else ""
                    
                    # Match status
                    status_el = el.query_selector("[class*='matchRowStatus'], [class*='match-row_statusLabel'], [class*='match-row_status']")
                    status = status_el.text_content().strip() if status_el else ""
                    
                    time_el = el.query_selector("[class*='matchTime']")
                    time = time_el.text_content().strip() if time_el else ""
                    
                    # Details (Stage, Group/Match #, Stadium, City)
                    stage_el = el.query_selector("[class*='match-row_bottomLabelWrapper'] > span")
                    stage = stage_el.text_content().strip() if stage_el else ""
                    
                    group_el = el.query_selector("[class*='statiumCityWrapper'] > span[class*='match-row_bottomLabel']")
                    group_info = group_el.text_content().strip() if group_el else ""
                    
                    stadium_el = el.query_selector("[class*='match-row_stadiumCityLabels'] span:nth-child(1)")
                    city_el = el.query_selector("[class*='match-row_stadiumCityLabels'] span:nth-child(2)")
                    stadium = stadium_el.text_content().strip() if stadium_el else ""
                    city = city_el.text_content().strip().replace("(", "").replace(")", "") if city_el else ""
                    
                    # Fill placeholder team names for knockouts if name is empty
                    if not team1 and code1:
                        team1 = code1
                    if not team2 and code2:
                        team2 = code2
                        
                    match_data = {
                        "Date": current_date,
                        "Time": time,
                        "Team1": team1,
                        "Code1": code1,
                        "Score1": score1,
                        "Score2": score2,
                        "Team2": team2,
                        "Code2": code2,
                        "Status": status,
                        "Stage": stage,
                        "Group_or_Match": group_info,
                        "Stadium": stadium,
                        "City": city
                    }
                    all_matches.append(match_data)
                except Exception as e:
                    print(f"Error parsing match row: {e}")
                    
        browser.close()
        
    total_scraped = len(all_matches)
    print(f"\nScraping complete. Total matches collected: {total_scraped}")
    
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
        
    # Print Knockout Bracket matches
    print("\n========================================================")
    print("               FIFA WORLD CUP 2026 BRACKET              ")
    print("========================================================")
    for stage_name, matches in knockout_by_stage.items():
        print(f"\n--- {stage_name} ---")
        for m in matches:
            score_line = f"{m['Score1']} - {m['Score2']}" if m['Score1'] or m['Score2'] else " vs "
            status_line = f" ({m['Status']})" if m['Status'] else ""
            print(f"  {m['Date']}: {m['Team1']} ({m['Code1']}){score_line}{m['Team2']} ({m['Code2']}){status_line}")
            print(f"     Venue: {m['Stadium']}, {m['City']}")
            
    # Save files
    # 1. Combined JSON structure
    consolidated_json = {
        "group_stage": group_stage_matches,
        "knockout_stage": knockout_by_stage
    }
    with open("all_matches.json", "w", encoding="utf-8") as f:
        json.dump(consolidated_json, f, indent=4, ensure_ascii=False)
    print("\nSaved combined data to all_matches.json")
    
    pass

if __name__ == "__main__":
    scrape_bracket()
