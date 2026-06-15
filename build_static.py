"""
Build static index.html for GitHub Pages deployment.
Reads templates/index.html and creates a root-level static version
that loads data from data.json instead of the Flask /api/data endpoint.
"""

# Read the Flask template
with open("templates/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Change API endpoint to static data.json
content = content.replace(
    "const response = await fetch('/api/data');",
    "const response = await fetch('./data.json');"
)

# 2. Replace triggerScrape with static-mode version
old_fn_start = "        // Trigger Playwright Scraping\n        async function triggerScrape() {"
old_fn_end = "        }\n\n        // Tab Switching Logic"

start_idx = content.find(old_fn_start)
end_idx = content.find(old_fn_end)

if start_idx != -1 and end_idx != -1:
    new_scrape_fn = """        // Static mode: Live scraping not available on GitHub Pages
        async function triggerScrape() {
            alert('Live scraping is only available when running locally with Flask.\\n\\nThis GitHub Pages version shows a data snapshot.');
        }

        // Tab Switching Logic"""
    content = content[:start_idx] + new_scrape_fn + content[end_idx + len(old_fn_end):]
    print("triggerScrape replaced successfully.")
else:
    print(f"WARNING: triggerScrape not found! start={start_idx}, end={end_idx}")

# 3. Update subtitle
content = content.replace(
    "<p>Real-time group standings, match scores, and knockout stages</p>",
    "<p>Group standings, match scores &amp; knockout bracket &mdash; Snapshot: June 15, 2026</p>"
)

# 4. Update button label and icon
content = content.replace("Update Live Data", "Data Snapshot (Local Only)")

# Write to root index.html
with open("index.html", "w", encoding="utf-8") as f:
    f.write(content)

print("index.html created successfully in root directory!")
