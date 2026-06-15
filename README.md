# FIFA World Cup 2026 Dashboard

A real-time interactive web dashboard for FIFA World Cup 2026, built with Python Flask and Playwright.

## Features

- **Knockout Bracket Tree** — Visual symmetrical bracket with SVG connector lines, showing all 9 columns (R32 → Final)
- **Group Standings** — All 12 groups (A–L) with automatic qualification highlights and third-placed team rankings
- **All Matches Playlist** — Searchable, filterable match list with 12-hour BST time display and clean status badges
- **Live Scraping** — One-click "Update Live Data" button scrapes FIFA's official website using Playwright

## Tech Stack

- **Backend**: Python + Flask
- **Scraper**: Playwright (headless Chromium)
- **Frontend**: Vanilla HTML/CSS/JS (glassmorphism design, Google Fonts)

## Setup

### 1. Install Dependencies

```bash
pip install flask playwright pandas
playwright install chromium
```

### 2. Run the App

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

### 3. Update Live Data

Click the **"Update Live Data"** button on the dashboard to scrape fresh data from FIFA's website.

## Project Structure

```
FIFA 26/
├── app.py                  # Flask server + data processing
├── scrape_standings.py     # Playwright scraper for group standings
├── scrape_bracket.py       # Playwright scraper for all matches
├── scrape_bracket_tree.py  # Playwright scraper for visual bracket tree
├── templates/
│   └── index.html          # Full frontend (HTML + CSS + JS)
└── requirements.txt        # Python dependencies
```

## Data Flow

1. Playwright scrapes FIFA's official website
2. Data saved as JSON files locally (`all_standings.json`, `all_matches.json`, `bracket_tree.json`)
3. Flask serves the data via `/api/data` endpoint
4. Frontend renders the dashboard dynamically

## License

MIT
