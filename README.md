# Bookswagon Price Tracker Automation

A Python script that scrapes book prices from Bookswagon and sends notifications via Telegram, Discord, and Ntfy.
It runs completely automatically using GitHub Actions twice a day.

## How it works
1. **`books.json`**: This is where you configure which books to track. Just add a new object with `name` and `url`.
2. **`tracker.py`**: The main scraping script. It uses `requests` and `BeautifulSoup` to extract prices. It uses `cloudscraper` for local runs, and **ScraperAPI** when running on GitHub Actions to bypass IP blocking.
3. **`price_history.json`**: Auto-generated/updated by the script. Stores the last-seen price per book so it can detect drops. Committed back to the repo automatically after each run that changes a price.
4. **GitHub Actions (`.github/workflows/price-tracker.yml`)**: Runs the script automatically at 8:00 AM and 8:00 PM IST every day.

## Notification schedule
- **Any price drop** (price lower than the last recorded price) triggers an immediate alert on all configured channels, at either run.
- **8:00 PM IST run**: also sends the full digest (every tracked book's current price), regardless of whether anything dropped.
- **8:00 AM IST run**: digest is skipped — you only hear from it if something dropped.
- **Manual run** (`workflow_dispatch` from the Actions tab): always sends the full digest, same as the evening run.

## Setup Instructions

### 1. Add Books to Track
Simply edit `books.json` and add the books you want:
```json
[
  {
    "name": "Book Title",
    "url": "https://www.bookswagon.com/book/..."
  }
]
```

### 2. GitHub Secrets Configuration
To enable notifications and bypass anti-bot protections, configure the following secrets in your GitHub Repository under **Settings -> Secrets and variables -> Actions -> New repository secret**:

| Secret Name | Required? | Description |
|---|---|---|
| `SCRAPER_API_KEY` | **Yes** | Without this, GitHub's IP will be blocked. Get a free key (5,000 requests/month) from [ScraperAPI](https://www.scraperapi.com/). |
| `TELEGRAM_BOT_TOKEN` | Optional | Create a bot using [@BotFather](https://t.me/BotFather) on Telegram and paste the token. |
| `TELEGRAM_CHAT_ID` | Optional | Your Telegram Chat ID. (Find via `@userinfobot` or checking bot API updates). |
| `DISCORD_WEBHOOK_URL` | Optional | Create a webhook in your Discord Server's channel settings and paste the URL here. |
| `NTFY_TOPIC` | Optional | A unique topic string for free mobile push notifications using the [Ntfy app](https://ntfy.sh/). |

### 3. Note on GitHub Actions Cron
GitHub Actions automatically disables cron jobs if a repository hasn't had any activity (like a commit) for **60 days**.
Every run that records a price change already commits `price_history.json`, which resets that clock. As a backstop, if 45 days pass with no commit at all (e.g. prices never changed or every run failed), the workflow makes one empty "keepalive" commit — instead of committing on every single run. You don't need to do anything manually!

## Local Testing
If you want to run this locally on your own machine:
1. `pip install -r requirements.txt`
2. `python tracker.py`

*(Note: Local runs use `cloudscraper` and don't strictly require the ScraperAPI key, as your home IP is likely not blocked by Bookswagon).*
