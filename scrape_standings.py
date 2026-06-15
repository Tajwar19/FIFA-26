import os
import json
import csv
import io
from playwright.sync_api import sync_playwright
import pandas as pd

URL = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/standings"

def parse_tables(html_content):
    """
    Attempt to read tables using pandas read_html.
    """
    try:
        dfs = pd.read_html(io.StringIO(html_content))
        return dfs
    except Exception as e:
        print(f"Pandas read_html failed: {e}")
        return []

def clean_dataframe(df):
    """
    Cleans the raw parsed DataFrame. Maps index-based columns to structured columns,
    splits team name and code, and cleans data types.
    """
    if df.shape[1] >= 11:
        cleaned_df = pd.DataFrame()
        
        # Position (Index 1)
        cleaned_df['Pos'] = pd.to_numeric(df.iloc[:, 1], errors='coerce').fillna(0).astype(int)
        
        # Team & Code (Index 2)
        team_strings = df.iloc[:, 2].astype(str)
        teams = []
        codes = []
        for s in team_strings:
            s = s.strip()
            # Country code is usually a 3-letter uppercase abbreviation at the end (e.g. MexicoMEX -> Mexico, MEX)
            if len(s) > 3 and s[-3:].isupper() and s[-3:].isalpha():
                teams.append(s[:-3].strip())
                codes.append(s[-3:])
            else:
                teams.append(s)
                codes.append("")
        
        cleaned_df['Team'] = teams
        cleaned_df['Code'] = codes
        cleaned_df['Played'] = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0).astype(int)
        cleaned_df['Won'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0).astype(int)
        cleaned_df['Drawn'] = pd.to_numeric(df.iloc[:, 5], errors='coerce').fillna(0).astype(int)
        cleaned_df['Lost'] = pd.to_numeric(df.iloc[:, 6], errors='coerce').fillna(0).astype(int)
        cleaned_df['GF'] = pd.to_numeric(df.iloc[:, 7], errors='coerce').fillna(0).astype(int)
        cleaned_df['GA'] = pd.to_numeric(df.iloc[:, 8], errors='coerce').fillna(0).astype(int)
        cleaned_df['GD'] = pd.to_numeric(df.iloc[:, 9], errors='coerce').fillna(0).astype(int)
        cleaned_df['Points'] = pd.to_numeric(df.iloc[:, 10], errors='coerce').fillna(0).astype(int)
        
        return cleaned_df
    return df

def scrape_standings():
    print(f"Navigating to {URL}...")
    with sync_playwright() as p:
        # Launch headless chromium
        browser = p.chromium.launch(headless=True)
        # Create a new page context with a realistic user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Navigate to the FIFA standings URL
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for either a table or table-like class to appear
        try:
            print("Waiting for standings table to appear...")
            page.wait_for_selector("table, [class*='standings'], [class*='table']", timeout=25000)
        except Exception as e:
            print(f"Wait for selector timed out: {e}. Proceeding anyway...")
        
        # Wait a bit more for JavaScript rendering to complete
        page.wait_for_timeout(3000)
        
        print("Page loaded. Searching for standings elements...")
        
        # Check if there are tables
        tables = page.query_selector_all("table")
        print(f"Found {len(tables)} table elements.")
        
        # Capture the full HTML content to inspect
        html_content = page.content()
        
        # If no tables are found, let's inspect the page structure
        if len(tables) == 0:
            print("No <table> elements found. Checking if there are custom grid/flex elements...")
            # Let's search for elements that might contain standings text
            standings_container = page.query_selector(".standings-container, [class*='standings'], [class*='table']")
            if standings_container:
                print("Found standings container using class selector!")
                print("Text content sample:")
                print(standings_container.text_content()[:500])
            else:
                print("Could not find common standings class selectors. Text of body sample:")
                body_text = page.query_selector("body").text_content()
                print(body_text[:1000])
            
            # Save the HTML page source for debugging
            debug_path = "page_source_debug.html"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Saved page source to {debug_path} for inspection.")
            browser.close()
            return
        
        # If tables are found, let's extract them
        print("Extracting standings from tables...")
        dfs = parse_tables(html_content)
        
        if not dfs:
            print("Failed to parse tables using Pandas. Attempting manual parsing...")
            # Manual table parsing
            for i, table in enumerate(tables):
                headers = [th.text_content().strip() for th in table.query_selector_all("thead th, tr th")]
                if not headers:
                    # Try to get first row of table as header if thead isn't used
                    first_row = table.query_selector("tr")
                    if first_row:
                        headers = [td.text_content().strip() for td in first_row.query_selector_all("td, th")]
                
                rows = []
                for tr in table.query_selector_all("tbody tr, tr"):
                    cells = [td.text_content().strip() for td in tr.query_selector_all("td, th")]
                    if cells:
                        # Skip if it is the header row itself
                        if len(cells) == len(headers) and all(c == h for c, h in zip(cells, headers)):
                            continue
                        if len(cells) > len(headers):
                            cells = cells[:len(headers)]
                        elif len(cells) < len(headers):
                            cells = cells + [""] * (len(headers) - len(cells))
                        rows.append(cells)
                
                if headers and rows:
                    df = pd.DataFrame(rows, columns=headers)
                    dfs.append(df)
        
        # Let's look for headings/group names above each table
        headings = page.query_selector_all("h2, h3, h4, h5, h6, [class*='group'], [class*='title'], [class*='header']")
        heading_texts = [h.text_content().strip() for h in headings if h.text_content().strip()]
        
        # Filter for headings containing "group" (case-insensitive)
        group_headings = []
        for h in heading_texts:
            h_clean = " ".join(h.split()) # normalize spaces
            if "group" in h_clean.lower() and len(h_clean) < 30 and h_clean not in group_headings:
                group_headings.append(h_clean)
        
        # Fallback to standard Group A-L if we don't have enough matching headings
        if len(group_headings) < len(dfs):
            fallback_groups = [f"Group {c}" for c in "ABCDEFGHIJKL"]
            for idx in range(len(dfs)):
                if idx >= len(group_headings):
                    group_headings.append(fallback_groups[idx])
        
        print(f"Group headings detected/used: {group_headings}")
        
        # Clean and save the data
        all_standings = {}
        for idx, df in enumerate(dfs):
            group_name = group_headings[idx] if idx < len(group_headings) else f"Group_{idx + 1}"
            
            # Clean DataFrame before processing
            cleaned_df = clean_dataframe(df)
            
            print(f"\n--- {group_name} ---")
            print(cleaned_df.to_string(index=False))
            
            # Convert to dictionary format
            all_standings[group_name] = cleaned_df.to_dict(orient="records")
            
        # Save all standings to JSON
        json_filename = "all_standings.json"
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(all_standings, f, indent=4, ensure_ascii=False)
        print(f"\nSaved all standings to {json_filename}")
        
        browser.close()

if __name__ == "__main__":
    scrape_standings()
